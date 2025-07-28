# main.py (V3.1.3 - 修正加载时序问题)

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

# --- 数据契约 ---
@dataclass(frozen=True)
class DiskUsage:
    path: str
    total: int
    used: int
    percent: float

@dataclass(frozen=True)
class SystemMetrics:
    cpu_percent: float
    cpu_temp: Optional[float]
    mem_total: int
    mem_used: int
    mem_percent: float
    net_sent: int
    net_recv: int
    uptime: datetime.timedelta
    disks: List[DiskUsage] = field(default_factory=list)

# --- 数据采集器 ---
class MetricsCollector:
    def __init__(self, config: AstrBotConfig):
        self.config = config
        try:
            self.boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        except Exception as e:
            logger.error(f"[StatusPlugin] 获取系统启动时间失败: {e}")
            self.boot_time = datetime.datetime.now()

    def _get_disk_usages(self) -> List[DiskUsage]:
        disks = []
        paths_to_check = self.config.get('disk_paths', [])
        
        # 如果配置为空，则自动发现分区
        if not paths_to_check:
            try:
                paths_to_check = [p.mountpoint for p in psutil.disk_partitions(all=False)]
            except Exception as e:
                logger.warning(f"[StatusPlugin] 自动发现磁盘分区失败，将使用默认路径: {e}")
                paths_to_check = ['C:\\' if platform.system() == "Windows" else '/']
        
        for path in paths_to_check:
            try:
                usage = psutil.disk_usage(path)
                disks.append(DiskUsage(path=path, total=usage.total, used=usage.used, percent=usage.percent))
            except Exception as e:
                logger.warning(f"[StatusPlugin] 获取磁盘路径 '{path}' 信息失败: {e}")
        return disks

    def collect(self) -> Optional[SystemMetrics]:
        try:
            # psutil 的一些调用是阻塞的，将在异步任务中运行
            cpu_p = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            net = psutil.net_io_counters()
        except Exception as e:
            logger.error(f"[StatusPlugin] 获取核心系统指标失败: {e}", exc_info=True)
            return None

        cpu_t = None
        if self.config.get("show_temp", True) and hasattr(psutil, "sensors_temperatures"):
            try:
                temps = psutil.sensors_temperatures()
                # 遍历常见的CPU温度键
                for key in ['coretemp', 'k10temp', 'cpu_thermal', 'acpitz']:
                    if key in temps and temps[key]:
                        cpu_t = temps[key][0].current
                        break
            except Exception:
                pass  # 获取温度失败是常见情况，静默处理

        return SystemMetrics(
            cpu_percent=cpu_p, cpu_temp=cpu_t,
            mem_total=mem.total, mem_used=mem.used, mem_percent=mem.percent,
            net_sent=net.bytes_sent, net_recv=net.bytes_recv,
            uptime=datetime.datetime.now() - self.boot_time,
            disks=self._get_disk_usages()
        )

# --- 文本格式化器 ---
class MetricsFormatter:
    _BYTE_LABELS: Dict[int, str] = {0: ' B', 1: ' KB', 2: ' MB', 3: ' GB', 4: ' TB'}

    def format(self, metrics: SystemMetrics) -> str:
        parts = [
            "💻 **服务器实时状态**",
            "--------------------",
            self._format_uptime(metrics.uptime),
            self._format_cpu(metrics),
            self._format_memory(metrics),
            self._format_disks(metrics.disks),
            self._format_network(metrics),
        ]
        return "\n".join(filter(None, parts))

    def _format_uptime(self, uptime: datetime.timedelta) -> str:
        days, rem = divmod(uptime.total_seconds(), 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        return f"⏱️ **已稳定运行**: {int(days)}天 {int(hours)}小时 {int(minutes)}分钟"

    def _format_cpu(self, m: SystemMetrics) -> str:
        temp_str = f" ({m.cpu_temp:.1f}°C)" if m.cpu_temp else ""
        return f"--------------------\n🖥️ **CPU**{temp_str}\n   - **使用率**: {m.cpu_percent:.1f}%"

    def _format_memory(self, m: SystemMetrics) -> str:
        used_formatted = self._format_bytes(m.mem_used)
        total_formatted = self._format_bytes(m.mem_total)
        return f"""--------------------\n💾 **内存**\n   - **使用率**: {m.mem_percent:.1f}%\n   - **已使用**: {used_formatted} / {total_formatted}"""

    def _format_disks(self, disks: List[DiskUsage]) -> str:
        if not disks:
            return ""
        disk_parts = [
            f"""💿 **磁盘 ({d.path})**\n   - **使用率**: {d.percent:.1f}%\n   - **已使用**: {self._format_bytes(d.used)} / {self._format_bytes(d.total)}"""
            for d in disks
        ]
        return "--------------------\n" + "\n--------------------\n".join(disk_parts)

    def _format_network(self, m: SystemMetrics) -> str:
        return f"""--------------------\n🌐 **网络I/O (自启动)**\n   - **总上传**: {self._format_bytes(m.net_sent)}\n   - **总下载**: {self._format_bytes(m.net_recv)}"""

    @classmethod
    def _format_bytes(cls, byte_count: int) -> str:
        if byte_count is None: return "N/A"
        power, n = 1024, 0
        while byte_count >= power and n < len(cls._BYTE_LABELS) - 1:
            byte_count /= power
            n += 1
        return f"{byte_count:.2f}{cls._BYTE_LABELS[n]}"

# --- AstrBot 插件主类 (协调器) ---
@register(
    name="astrabot_plugin_status",
    author="riceshowerx & AstrBot Assistant",
    desc="以文本形式查询服务器的实时状态 (已按规范修复)",
    version="3.1.3",  # 版本号提升
    repo="https://github.com/riceshowerX/astrbot_plugin_status"
)
class ServerStatusPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.context = context
        self.config = config
        self.collector = MetricsCollector(self.config)
        self.formatter = MetricsFormatter()

        self._cache: Optional[str] = None
        self._cache_timestamp: float = 0.0
        # 从配置中读取缓存时间，如果未配置，则默认为 5 秒
        self.cache_duration = self.config.get('cache_duration', 5)

    @event_filter.command("status", alias={"服务器状态", "状态", "zt", "s"})
    async def handle_server_status(self, event: AstrMessageEvent):
        """
        消息处理函数。
        遵循 AstrBot 框架规范，使用 'yield' 范式返回结果。
        """
        now = time.time()
        
        # 检查缓存
        if self.cache_duration > 0 and self._cache and (now - self._cache_timestamp < self.cache_duration):
            # logger.info("从缓存中提供服务器状态。")  # 可选：如果需要，可以在handler中记录日志
            yield event.plain_result(self._cache)
            return

        yield event.plain_result("正在重新获取服务器状态，请稍候...")
        
        try:
            # 将阻塞的I/O操作移至线程中执行，避免阻塞主事件循环
            metrics = await asyncio.to_thread(self.collector.collect)
            
            if metrics is None:
                yield event.plain_result("抱歉，获取核心服务器指标时发生错误，请检查日志。")
                return

            text_message = self.formatter.format(metrics)
            
            # 更新缓存
            self._cache, self._cache_timestamp = text_message, now
            
            yield event.plain_result(text_message)
            
        except Exception as e:
            logger.error(f"[StatusPlugin] 处理 status 指令时发生未知错误: {e}", exc_info=True)
            yield event.plain_result(f"抱歉，获取状态时出现未知错误，请联系管理员。")
