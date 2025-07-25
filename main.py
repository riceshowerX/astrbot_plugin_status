# main.py

import psutil
import datetime
import platform
import asyncio
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

# 导入 AstrBot 官方 API
from astrbot.api.star import Star, register, Context
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger, AstrBotConfig

# ===================================================================
# 模块1: 数据契约 (Data Contracts)
# 定义清晰、类型安全的数据结构，作为各逻辑层之间的契约。
# ===================================================================
@dataclass(frozen=True)
class DiskUsage:
    """封装单个磁盘分区的使用情况"""
    path: str; total: int; used: int; percent: float

@dataclass(frozen=True)
class SystemMetrics:
    """插件内部传递的核心数据对象"""
    cpu_percent: float; cpu_temp: Optional[float]
    mem_total: int; mem_used: int; mem_percent: float
    net_sent: int; net_recv: int
    uptime: datetime.timedelta
    disks: List[DiskUsage] = field(default_factory=list)

# ===================================================================
# 模块2: 数据采集器 (Metrics Collector)
# 负责所有与操作系统和 psutil 的交互，采集系统指标。
# ===================================================================
class MetricsCollector:
    def __init__(self, config: AstrBotConfig):
        self.config = config
        try:
            self.boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        except Exception as e:
            logger.error(f"获取系统启动时间失败: {e}"); self.boot_time = datetime.datetime.now()

    def _get_disk_usages(self) -> List[DiskUsage]:
        """获取所有目标磁盘分区的使用情况。"""
        disks = []
        paths_to_check = self.config.get('disk_paths', [])
        if not paths_to_check:
            try: paths_to_check = [p.mountpoint for p in psutil.disk_partitions(all=False)]
            except Exception as e: logger.warning(f"自动发现磁盘分区失败: {e}"); paths_to_check = ['C:\\' if platform.system() == "Windows" else '/']
        for path in paths_to_check:
            try:
                usage = psutil.disk_usage(path)
                disks.append(DiskUsage(path=path, total=usage.total, used=usage.used, percent=usage.percent))
            except Exception as e:
                logger.warning(f"获取磁盘路径 '{path}' 信息失败: {e}")
        return disks

    def collect(self) -> Optional[SystemMetrics]:
        """执行所有采集任务，如果核心数据失败则返回 None。"""
        try:
            cpu_p, mem, net = psutil.cpu_percent(interval=1), psutil.virtual_memory(), psutil.net_io_counters()
        except Exception as e:
            logger.error(f"获取核心系统指标失败: {e}", exc_info=True); return None
            
        cpu_t = None
        if self.config.get("show_temp", True) and platform.system() == "Linux":
            try:
                temps = psutil.sensors_temperatures()
                for key in ['coretemp', 'k10temp', 'cpu_thermal']:
                    if key in temps and temps[key]: cpu_t = temps[key][0].current; break
            except Exception: pass

        return SystemMetrics(
            cpu_percent=cpu_p, cpu_temp=cpu_t,
            mem_total=mem.total, mem_used=mem.used, mem_percent=mem.percent,
            net_sent=net.bytes_sent, net_recv=net.bytes_recv,
            uptime=datetime.datetime.now() - self.boot_time,
            disks=self._get_disk_usages()
        )

# ===================================================================
# 模块3: 文本格式化器 (Metrics Formatter)
# 负责将标准的 SystemMetrics 对象格式化为人类可读的字符串。
# ===================================================================
class MetricsFormatter:
    _BYTE_LABELS: Dict[int, str] = {0: ' B', 1: ' KB', 2: ' MB', 3: ' GB', 4: ' TB'}

    def format(self, metrics: SystemMetrics) -> str:
        """将 SystemMetrics 对象格式化为最终的文本消息。"""
        parts = [
            "💻 **服务器实时状态**", "--------------------",
            self._format_uptime(metrics.uptime),
            self._format_cpu(metrics),
            self._format_memory(metrics),
            self._format_disks(metrics.disks),
            self._format_network(metrics),
        ]
        return "\n".join(filter(None, parts))

    def _format_uptime(self, uptime: datetime.timedelta) -> str:
        days, rem = divmod(uptime.total_seconds(), 86400); hours, rem = divmod(rem, 3600); minutes, _ = divmod(rem, 60)
        return f"⏱️ **已稳定运行**: {int(days)}天 {int(hours)}小时 {int(minutes)}分钟"

    def _format_cpu(self, m: SystemMetrics) -> str:
        temp = f"({m.cpu_temp:.1f}°C)" if m.cpu_temp else ""
        return f"--------------------\n🖥️ **CPU** {temp}\n   - **使用率**: {m.cpu_percent:.1f}%"

    def _format_memory(self, m: SystemMetrics) -> str:
        return f"""--------------------
💾 **内存**
   - **使用率**: {m.mem_percent:.1f}%
   - **已使用**: {self._format_bytes(m.mem_used)} / {self._format_bytes(m.mem_total)}"""

    def _format_disks(self, disks: List[DiskUsage]) -> str:
        if not disks: return ""
        disk_parts = [f"""💿 **磁盘 ({d.path})**
   - **使用率**: {d.percent:.1f}%
   - **已使用**: {self._format_bytes(d.used)} / {self._format_bytes(d.total)}""" for d in disks]
        return "--------------------\n" + "\n--------------------\n".join(disk_parts)

    def _format_network(self, m: SystemMetrics) -> str:
        return f"""--------------------
🌐 **网络I/O (自启动)**
   - **总上传**: {self._format_bytes(m.net_sent)}
   - **总下载**: {self._format_bytes(m.net_recv)}"""

    @classmethod
    def _format_bytes(cls, byte_count: int) -> str:
        if byte_count is None: return "N/A"
        power, n = 1024, 0
        while byte_count >= power and n < len(cls._BYTE_LABELS) - 1:
            byte_count /= power; n += 1
        return f"{byte_count:.2f}{cls._BYTE_LABELS[n]}"

# ===================================================================
# 模块4: AstrBot 插件主类 (Plugin/Orchestrator)
# 作为轻量级的协调器，粘合其他逻辑模块并与 AstrBot 框架交互。
# ===================================================================
@register(
    name="astrabot_plugin_status", 
    author="riceshowerx", 
    desc="以文本形式查询服务器的实时状态 (单文件S级架构)", 
    version="3.1.0", # 版本号提升
    repo="https://github.com/riceshowerX/astrbot_plugin_status"
)
class ServerStatusPlugin(Star):
    # 定义缓存有效期（秒）
    CACHE_DURATION: int = 5

    def __init__(self, context: Context, config: Optional[AstrBotConfig] = None):
        super().__init__(context)
        self.context = context
        self.config = config if config is not None else AstrBotConfig({})
        
        # 依赖注入思想：在初始化时创建并持有依赖的实例
        self.collector = MetricsCollector(self.config)
        self.formatter = MetricsFormatter()
        
        # 初始化缓存
        self._cache: Optional[str] = None
        self._cache_timestamp: float = 0.0
        
        logger.info("服务器状态插件(v3.1.0)已成功加载。")

    @filter.command("status", alias={"服务器状态", "状态", "zt", "s"})
    async def handle_server_status(self, event: AstrMessageEvent):
        '''查询并显示当前服务器的详细运行状态'''
        # 高性能缓存检查
        now = time.time()
        if self._cache and (now - self._cache_timestamp < self.CACHE_DURATION):
            logger.info("从缓存中提供服务器状态。")
            await event.send(event.plain_result(self._cache))
            return

        await event.send(event.plain_result("正在重新获取服务器状态，请稍候..."))
        
        try:
            # 使用 asyncio.to_thread 运行阻塞的采集任务
            metrics = await asyncio.to_thread(self.collector.collect)

            if metrics is None:
                await event.send(event.plain_result("抱歉，获取核心服务器指标时发生错误，请检查日志。"))
                return

            text_message = self.formatter.format(metrics)
            
            # 更新缓存
            self._cache = text_message
            self._cache_timestamp = now
            
            await event.send(event.plain_result(text_message))
            
        except Exception as e:
            logger.error(f"处理 status 指令时发生未知错误: {e}", exc_info=True)
            await event.send(event.plain_result(f"抱歉，获取状态时出现未知错误，请联系管理员。"))