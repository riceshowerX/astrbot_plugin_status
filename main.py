# main.py (V2.0.0 现代化重构版)

import psutil
import datetime
import platform
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

# 导入 AstrBot 官方 API
from astrbot.api.star import Star, register, Context
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger, AstrBotConfig

# ===================================================================
# 1. 使用数据类 (Dataclasses) 定义清晰的数据结构
# ===================================================================
@dataclass(frozen=True)
class DiskUsage:
    """封装单个磁盘分区的使用情况"""
    path: str
    total: int
    used: int
    percent: float

@dataclass(frozen=True)
class SystemMetrics:
    """定义一个清晰、类型安全的数据契约，替代字典"""
    cpu_percent: float
    cpu_temp: Optional[float]
    mem_total: int
    mem_used: int
    mem_percent: float
    net_sent: int
    net_recv: int
    uptime: datetime.timedelta
    disks: List[DiskUsage] = field(default_factory=list)

# --- 插件主类 ---
@register(
    name="astrabot_plugin_status", 
    author="riceshowerx", 
    desc="以文本形式查询服务器的实时状态 (重构版)", 
    version="2.0.0", # 主版本号提升，代表重大重构
    repo="https://github.com/riceshowerX/astrbot_plugin_status"
)
class ServerStatusPlugin(Star):
    # 类级别的常量
    _BYTE_LABELS: Dict[int, str] = {0: ' B', 1: ' KB', 2: ' MB', 3: ' GB', 4: ' TB'}

    def __init__(self, context: Context, config: Optional[AstrBotConfig] = None):
        super().__init__(context)
        self.context = context
        self.config = config if config is not None else AstrBotConfig({})
        try:
            self.boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        except Exception as e:
            logger.error(f"获取系统启动时间失败: {e}"); self.boot_time = datetime.datetime.now()
        
        logger.info("服务器状态插件(v2.0.0)已成功加载，代码已现代化重构。")

    # ===================================================================
    # 2. 将庞大的 get_system_stats 分解为多个职责单一的辅助方法
    # ===================================================================
    def _get_disk_usages(self) -> List[DiskUsage]:
        """获取所有目标磁盘分区的使用情况。"""
        disks = []
        paths_to_check = self.config.get('disk_paths', [])
        if not paths_to_check:
            try:
                paths_to_check = [p.mountpoint for p in psutil.disk_partitions(all=False)]
            except Exception as e:
                logger.warning(f"自动发现磁盘分区失败: {e}"); paths_to_check = ['C:\\' if platform.system() == "Windows" else '/']
        
        for path in paths_to_check:
            try:
                usage = psutil.disk_usage(path)
                disks.append(DiskUsage(path=path, total=usage.total, used=usage.used, percent=usage.percent))
            except Exception as e:
                logger.warning(f"获取磁盘路径 '{path}' 信息失败: {e}")
        return disks

    def get_system_metrics(self) -> SystemMetrics:
        """获取并组装所有系统指标，返回一个类型安全的数据对象。"""
        # 每个指标的获取都封装在自己的 try-except 中，保证健壮性
        try: cpu_p = psutil.cpu_percent(interval=1)
        except Exception: cpu_p = 0.0
        
        cpu_t = None
        if self.config.get("show_temp", True) and platform.system() == "Linux":
            try:
                temps = psutil.sensors_temperatures()
                for key in ['coretemp', 'k10temp', 'cpu_thermal']:
                    if key in temps and temps[key]: cpu_t = temps[key][0].current; break
            except Exception: pass # 温度获取失败是正常情况，无需日志

        try: mem = psutil.virtual_memory(); mem_total, mem_used, mem_percent = mem.total, mem.used, mem.percent
        except Exception: mem_total, mem_used, mem_percent = 0, 0, 0.0

        try: net = psutil.net_io_counters(); net_sent, net_recv = net.bytes_sent, net.bytes_recv
        except Exception: net_sent, net_recv = 0, 0
        
        return SystemMetrics(
            cpu_percent=cpu_p,
            cpu_temp=cpu_t,
            mem_total=mem_total,
            mem_used=mem_used,
            mem_percent=mem_percent,
            net_sent=net_sent,
            net_recv=net_recv,
            uptime=datetime.datetime.now() - self.boot_time,
            disks=self._get_disk_usages()
        )

    # ===================================================================
    # 3. 将庞大的 format_text_message 分解，并使用数据类
    # ===================================================================
    def format_text_message(self, metrics: SystemMetrics) -> str:
        """将 SystemMetrics 对象格式化为对用户友好的文本消息。"""
        parts = [
            self._format_header(),
            self._format_uptime(metrics.uptime),
            self._format_cpu(metrics),
            self._format_memory(metrics),
        ]
        parts.extend(self._format_disks(metrics.disks))
        parts.append(self._format_network(metrics))
        
        return "\n".join(parts)

    def _format_header(self) -> str: return "💻 **服务器实时状态**\n" + "--------------------"
    def _format_uptime(self, uptime: datetime.timedelta) -> str:
        days, rem = divmod(uptime.total_seconds(), 86400); hours, rem = divmod(rem, 3600); minutes, _ = divmod(rem, 60)
        return f"⏱️ **已稳定运行**: {int(days)}天 {int(hours)}小时 {int(minutes)}分钟"
    def _format_cpu(self, m: SystemMetrics) -> str:
        temp = f"({m.cpu_temp:.1f}°C)" if m.cpu_temp else ""
        return f"--------------------\n🖥️ **CPU** {temp}\n   - **使用率**: {m.cpu_percent:.1f}%"
    def _format_memory(self, m: SystemMetrics) -> str:
        return (f"--------------------\n💾 **内存**\n   - **使用率**: {m.mem_percent:.1f}%\n"
                f"   - **已使用**: {self._format_bytes(m.mem_used)} / {self._format_bytes(m.mem_total)}")
    def _format_disks(self, disks: List[DiskUsage]) -> List[str]:
        disk_parts = []
        for disk in disks:
            disk_parts.append(f"--------------------\n💿 **磁盘 ({disk.path})**\n   - **使用率**: {disk.percent:.1f}%\n"
                              f"   - **已使用**: {self._format_bytes(disk.used)} / {self._format_bytes(disk.total)}")
        return disk_parts
    def _format_network(self, m: SystemMetrics) -> str:
        return (f"--------------------\n🌐 **网络I/O (自启动)**\n"
                f"   - **总上传**: {self._format_bytes(m.net_sent)}\n"
                f"   - **总下载**: {self._format_bytes(m.net_recv)}")

    @filter.command("status", alias={"服务器状态", "状态", "zt", "s"})
    async def handle_server_status(self, event: AstrMessageEvent):
        '''查询并显示当前服务器的详细运行状态 (文本版)'''
        try:
            await event.send(event.plain_result("正在获取服务器状态，请稍候..."))
            
            # ===================================================================
            # 4. 使用 Python 3.9+ 的 asyncio.to_thread 简化异步调用
            # ===================================================================
            metrics = await asyncio.to_thread(self.get_system_metrics)
            
            text_message = self.format_text_message(metrics)
            await event.send(event.plain_result(text_message))

        except Exception as e:
            logger.error(f"处理 status 指令时发生未知错误: {e}", exc_info=True)
            await event.send(event.plain_result(f"抱歉，获取状态时出现错误，请联系管理员。"))
    
    @classmethod
    def _format_bytes(cls, byte_count: int) -> str:
        if byte_count is None: return "N/A"
        power, n = 1024, 0
        while byte_count >= power and n < len(cls._BYTE_LABELS) - 1:
            byte_count /= power; n += 1
        return f"{byte_count:.2f}{cls._BYTE_LABELS[n]}"