# main.py (V3.1.3 修复初始化属性错误)

import psutil
import datetime
import platform
import asyncio
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

# 导入 AstrBot 官方 API
from astrbot.api.star import Star, register, Context
from astrbot.api.event import filter as event_filter, AstrMessageEvent
from astrbot.api import logger, AstrBotConfig

# --- Data Models ---
@dataclass(frozen=True)
class DiskUsage:
    """封装单个磁盘分区的使用情况。"""
    path: str; total: int; used: int; percent: float

@dataclass(frozen=True)
class SystemMetrics:
    """封装插件内部流转的核心系统指标数据。"""
    cpu_percent: float; cpu_temp: Optional[float]
    mem_total: int; mem_used: int; mem_percent: float
    net_sent: int; net_recv: int
    uptime: datetime.timedelta
    disks: List[DiskUsage] = field(default_factory=list)

# --- Logic Modules ---
class MetricsCollector:
    """负责所有与操作系统交互的数据采集任务。"""
    def __init__(self, config: AstrBotConfig):
        self.config = config
        try: self.boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        except Exception as e: logger.error(f"获取系统启动时间失败: {e}"); self.boot_time = datetime.datetime.now()

    def _get_disk_usages(self) -> List[DiskUsage]:
        disks = []; paths_to_check = self.config.get('disk_paths', [])
        if not paths_to_check:
            try: paths_to_check = [p.mountpoint for p in psutil.disk_partitions(all=False)]
            except Exception as e: logger.warning(f"自动发现磁盘分区失败: {e}"); paths_to_check = ['C:\\' if platform.system() == "Windows" else '/']
        for path in paths_to_check:
            try:
                usage = psutil.disk_usage(path)
                disks.append(DiskUsage(path=path, total=usage.total, used=usage.used, percent=usage.percent))
            except Exception as e: logger.warning(f"获取磁盘路径 '{path}' 信息失败: {e}")
        return disks

    def collect(self) -> Optional[SystemMetrics]:
        try: cpu_p, mem, net = psutil.cpu_percent(interval=1), psutil.virtual_memory(), psutil.net_io_counters()
        except Exception as e: logger.error(f"获取核心系统指标失败: {e}", exc_info=True); return None
        cpu_t = None
        if self.config.get("show_temp", True) and platform.system() == "Linux":
            try:
                temps = psutil.sensors_temperatures()
                for key in ['coretemp', 'k10temp', 'cpu_thermal']:
                    if key in temps and temps[key]: cpu_t = temps[key][0].current; break
            except Exception: pass
        return SystemMetrics(
            cpu_percent=cpu_p, cpu_temp=cpu_t, mem_total=mem.total, mem_used=mem.used, mem_percent=mem.percent,
            net_sent=net.bytes_sent, net_recv=net.bytes_recv, uptime=datetime.datetime.now() - self.boot_time,
            disks=self._get_disk_usages()
        )

class MetricsFormatter:
    """负责将 SystemMetrics 数据对象格式化为人类可读的文本。"""
    _BYTE_LABELS: Dict[int, str] = {0: ' B', 1: ' KB', 2: ' MB', 3: ' GB', 4: ' TB'}

    def format(self, metrics: SystemMetrics) -> str:
        parts = ["💻 **服务器实时状态**", "--------------------", self._format_uptime(metrics.uptime), self._format_cpu(metrics),
                 self._format_memory(metrics), self._format_disks(metrics.disks), self._format_network(metrics)]
        return "\n".join(filter(None, parts))

    def _format_uptime(self, uptime: datetime.timedelta) -> str:
        days, rem = divmod(uptime.total_seconds(), 86400); hours, rem = divmod(rem, 3600); minutes, _ = divmod(rem, 60)
        return f"⏱️ **已稳定运行**: {int(days)}天 {int(hours)}小时 {int(minutes)}分钟"
    def _format_cpu(self, m: SystemMetrics) -> str:
        temp = f"({m.cpu_temp:.1f}°C)" if m.cpu_temp else ""; return f"--------------------\n🖥️ **CPU** {temp}\n   - **使用率**: {m.cpu_percent:.1f}%"
    def _format_memory(self, m: SystemMetrics) -> str:
        return f"""--------------------
💾 **内存**
   - **使用率**: {m.mem_percent:.1f}%
   - **已使用**: {self._format_bytes(m.mem_used)} / {self._format_bytes(m.mem_total)}"""
    def _format_disks(self, disks: List[DiskUsage]) -> str:
        if not disks: return ""
        disk_parts = [f"""💿 **磁盘 ({d.path})**\n   - **使用率**: {d.percent:.1f}%\n   - **已使用**: {self._format_bytes(d.used)} / {self._format_bytes(d.total)}""" for d in disks]
        return "--------------------\n" + "\n--------------------\n".join(disk_parts)
    def _format_network(self, m: SystemMetrics) -> str:
        return f"""--------------------
🌐 **网络I/O (自启动)**\n   - **总上传**: {self._format_bytes(m.net_sent)}\n   - **总下载**: {self._format_bytes(m.net_recv)}"""
    @classmethod
    def _format_bytes(cls, byte_count: int) -> str:
        if byte_count is None: return "N/A"
        power, n = 1024, 0
        while byte_count >= power and n < len(cls._BYTE_LABELS) - 1: byte_count /= power; n += 1
        return f"{byte_count:.2f}{cls._BYTE_LABELS[n]}"

# --- Plugin Entry Point ---
@register(
    name="astrabot_plugin_status", 
    author="riceshowerx", 
    desc="以文本形式查询服务器的实时状态。", 
    version="3.1.3",
    repo="https://github.com/riceshowerX/astrbot_plugin_status"
)
class ServerStatusPlugin(Star):
    """主插件类，作为协调器粘合数据采集和格式化模块，并与 AstrBot 框架交互。"""
    CACHE_DURATION: int = 5

    def __init__(self, context: Context, config: Optional[AstrBotConfig] = None):
        super().__init__(context)
        self.context = context
        self.config = config if config is not None else AstrBotConfig({})
        self.collector = MetricsCollector(self.config)
        self.formatter = MetricsFormatter()
        self._cache: Optional[str] = None
        self._cache_timestamp: float = 0.0
        # ===================================================================
        # 核心修正：移除导致加载失败的日志行
        # logger.info(f"插件 {self.name} (v{self.version}) 已成功加载。")
        # ===================================================================

    @event_filter.command("status", alias={"服务器状态", "状态", "zt", "s"})
    async def handle_server_status(self, event: AstrMessageEvent):
        """处理用户的状态查询指令。"""
        now = time.time()
        if self._cache and (now - self._cache_timestamp < self.CACHE_DURATION):
            logger.info("从缓存中提供服务器状态。")
            await event.send(event.plain_result(self._cache))
            return
            
        await event.send(event.plain_result("正在重新获取服务器状态，请稍候..."))
        try:
            metrics = await asyncio.to_thread(self.collector.collect)
            if metrics is None:
                await event.send(event.plain_result("抱歉，获取核心服务器指标时发生错误，请检查日志。"))
                return
            
            text_message = self.formatter.format(metrics)
            self._cache, self._cache_timestamp = text_message, now
            await event.send(event.plain_result(text_message))
        except Exception as e:
            logger.error(f"处理 status 指令时发生未知错误: {e}", exc_info=True)
            await event.send(event.plain_result("抱歉，在处理指令时发生未知错误。"))