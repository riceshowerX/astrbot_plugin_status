import psutil
import datetime
import platform
import asyncio
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import json
import os

# 统一使用框架提供的 logger
from astrbot.api.star import Star, register, Context
from astrbot.api.event import filter as event_filter, AstrMessageEvent
from astrbot.api import logger, AstrBotConfig

# --- 工具函数 ---
def safe_disk_path(path: Any) -> bool:
    """
    验证给定的路径是否为用于磁盘使用情况检查的安全、绝对路径。
    防止路径遍历和其他不安全的模式。
    """
    if not isinstance(path, str) or not path or len(path) > 1024:
        return False
    if not os.path.isabs(path):
        return False
    # 禁止包含不安全的字符或序列
    for c in ['..', '~', '\0', '*', '?', '|', '<', '>', '"']:
        if c in path:
            return False
    return True

# --- 数据契约 ---
@dataclass(frozen=True)
class DiskUsage:
    """表示单个磁盘分区的使用情况指标。"""
    path: str
    total: int
    used: int
    percent: float

@dataclass(frozen=True)
class SystemMetrics:
    """系统性能指标的快照。"""
    cpu_percent: float
    cpu_temp: Optional[float]
    mem_total: int
    mem_used: int
    mem_percent: float
    net_sent: int
    net_recv: int
    # 允许 uptime 为 None 以处理获取失败的情况
    uptime: Optional[datetime.timedelta]
    disks: List[DiskUsage] = field(default_factory=list)

# --- 数据采集器 ---
class MetricsCollector:
    """收集系统指标，如 CPU、内存、磁盘和网络使用情况。"""
    MAX_DISK_COUNT = 10

    def __init__(self, disk_paths_to_check: List[str], show_temp: bool):
        """
        初始化采集器。
        :param disk_paths_to_check: 经过验证和清洗的磁盘路径列表。
        :param show_temp: 是否显示 CPU 温度的布尔标志。
        """
        self.disk_paths_to_check = disk_paths_to_check
        self.show_temp = show_temp
        try:
            # 如果获取失败，boot_time 将为 None
            self.boot_time: Optional[datetime.datetime] = datetime.datetime.fromtimestamp(psutil.boot_time())
        except Exception as e:
            logger.error("[StatusPlugin] 获取系统启动时间失败: %s", e)
            self.boot_time = None

    def _get_disk_usages(self) -> List[DiskUsage]:
        """获取所有已配置或自动发现的磁盘的使用情况。"""
        disks = []
        paths_to_check = self.disk_paths_to_check

        # 如果配置的路径为空, 则自动发现
        if not paths_to_check:
            try:
                all_parts = [p.mountpoint for p in psutil.disk_partitions(all=False)]
                paths_to_check = [p for p in all_parts if safe_disk_path(p)][:self.MAX_DISK_COUNT]
            except Exception as e:
                logger.warning("[StatusPlugin] 自动发现磁盘分区失败，将使用默认路径: %s", e)
                paths_to_check = ['C:\\' if platform.system() == "Windows" else '/']
        
        for path in paths_to_check:
            try:
                usage = psutil.disk_usage(path)
                disks.append(DiskUsage(
                    path=path, total=usage.total, used=usage.used, percent=usage.percent
                ))
            except (PermissionError, FileNotFoundError) as e:
                logger.warning("[StatusPlugin] 无法访问磁盘路径 '%s' (%s)，已忽略。", path, e.__class__.__name__)
            except Exception as e:
                logger.warning("[StatusPlugin] 获取磁盘路径 '%s' 信息失败: %s", path, e)
        return disks

    def collect(self) -> Optional[SystemMetrics]:
        """
        一次性收集所有系统指标。这是一个阻塞操作。
        :return: 成功时返回 SystemMetrics 对象，若核心指标获取失败则返回 None。
        """
        try:
            cpu_p = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            net = psutil.net_io_counters()
        except Exception as e:
            logger.error("[StatusPlugin] 获取核心系统指标失败: %s", e, exc_info=True)
            return None

        cpu_t = None
        if self.show_temp and hasattr(psutil, "sensors_temperatures"):
            try:
                temps = psutil.sensors_temperatures()
                for key in ['coretemp', 'k10temp', 'cpu_thermal', 'acpitz']:
                    if key in temps and temps[key]:
                        cpu_t = temps[key][0].current
                        break
            except Exception as e:
                logger.warning("[StatusPlugin] 获取CPU温度失败: %s", e)
        
        # 如果 boot_time 为 None，则 uptime 也为 None
        current_uptime = (datetime.datetime.now() - self.boot_time) if self.boot_time else None

        return SystemMetrics(
            cpu_percent=cpu_p, cpu_temp=cpu_t,
            mem_total=mem.total, mem_used=mem.used, mem_percent=mem.percent,
            net_sent=net.bytes_sent, net_recv=net.bytes_recv,
            uptime=current_uptime,
            disks=self._get_disk_usages()
        )

# --- 文本格式化器 ---
class MetricsFormatter:
    """将 SystemMetrics 格式化为人类可读的文本字符串。"""
    _BYTE_LABELS: Dict[int, str] = {0: ' B', 1: ' KB', 2: ' MB', 3: ' GB', 4: ' TB'}
    SEPARATOR = "--------------------"

    def format(self, metrics: SystemMetrics) -> str:
        parts = [
            "💻 **服务器实时状态**",
            self.SEPARATOR,
            self._format_uptime(metrics.uptime),
            self._format_cpu(metrics),
            self._format_memory(metrics),
            self._format_disks(metrics.disks),
            self._format_network(metrics),
        ]
        return "\n".join(filter(None, parts))

    def _format_uptime(self, uptime: Optional[datetime.timedelta]) -> str:
        """格式化运行时间，处理 None 的情况。"""
        if uptime is None:
            return "⏱️ **已稳定运行**: 未知"
        days, rem = divmod(uptime.total_seconds(), 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        return f"⏱️ **已稳定运行**: {int(days)}天 {int(hours)}小时 {int(minutes)}分钟"

    def _format_cpu(self, m: SystemMetrics) -> str:
        temp_str = f" ({m.cpu_temp:.1f}°C)" if m.cpu_temp is not None else ""
        return f"{self.SEPARATOR}\n🖥️ **CPU**{temp_str}\n   - **使用率**: {m.cpu_percent:.1f}%"

    def _format_memory(self, m: SystemMetrics) -> str:
        used_formatted = self._format_bytes(m.mem_used)
        total_formatted = self._format_bytes(m.mem_total)
        return (
            f"{self.SEPARATOR}\n💾 **内存**\n"
            f"   - **使用率**: {m.mem_percent:.1f}%\n"
            f"   - **已使用**: {used_formatted} / {total_formatted}"
        )

    def _format_disks(self, disks: List[DiskUsage]) -> str:
        if not disks:
            return ""
        disk_parts = [
            f"""💿 **磁盘 ({self._escape_path(d.path)})**\n   - **使用率**: {d.percent:.1f}%\n   - **已使用**: {self._format_bytes(d.used)} / {self._format_bytes(d.total)}"""
            for d in disks
        ]
        return f"{self.SEPARATOR}\n" + f"\n{self.SEPARATOR}\n".join(disk_parts)

    def _format_network(self, m: SystemMetrics) -> str:
        return (
            f"{self.SEPARATOR}\n🌐 **网络I/O (自启动)**\n"
            f"   - **总上传**: {self._format_bytes(m.net_sent)}\n"
            f"   - **总下载**: {self._format_bytes(m.net_recv)}"
        )

    @classmethod
    def _format_bytes(cls, byte_count: int) -> str:
        if byte_count is None: return "N/A"
        power, n = 1024, 0
        while byte_count >= power and n < len(cls._BYTE_LABELS) - 1:
            byte_count /= power
            n += 1
        return f"{byte_count:.2f}{cls._BYTE_LABELS[n]}"

    @staticmethod
    def _escape_path(path: str) -> str:
        return path.replace('`', '').replace('*', '').replace('\n', '').replace('\r', '')

# --- AstrBot 插件主类 ---
@register(
    name="astrabot_plugin_status",
    author="riceshowerx & AstrBot Assistant",
    desc="以文本形式查询服务器的实时状态",
    version="1.0",
    repo="https://github.com/riceshowerX/astrbot_plugin_status"
)
class ServerStatusPlugin(Star):
    """一个通过缓存和安全加固来报告实时服务器状态的插件。"""
    
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.context = context
        # 使用独立的 plugin_config 属性存储经过校验的配置字典
        self.plugin_config: Dict[str, Any] = self._validate_config(config)
        
        self.collector: Optional[MetricsCollector] = None
        self.formatter = MetricsFormatter()
        
        self._cache: Optional[str] = None
        self._cache_timestamp: float = 0.0
        self.cache_duration: int = self.plugin_config.get('cache_duration', 5)
        self._lock = asyncio.Lock()

    def _validate_config(self, config: AstrBotConfig) -> Dict[str, Any]:
        """验证原始配置并返回一个干净的字典。"""
        checked: Dict[str, Any] = {}
        
        try:
            cache_duration = int(config.get('cache_duration', 5))
            checked['cache_duration'] = cache_duration if 0 <= cache_duration <= 3600 else 5
        except (ValueError, TypeError):
            checked['cache_duration'] = 5
        
        # 将 disk_paths 的解析和验证逻辑集中于此
        disk_paths_raw = config.get('disk_paths', [])
        final_disk_paths: List[str] = []
        if isinstance(disk_paths_raw, str):
            try:
                disk_paths_raw = json.loads(disk_paths_raw)
            except json.JSONDecodeError:
                disk_paths_raw = []
        
        if isinstance(disk_paths_raw, list):
            final_disk_paths = [p for p in disk_paths_raw if safe_disk_path(p)]
        checked['disk_paths'] = final_disk_paths

        checked['show_temp'] = bool(config.get('show_temp', True))
        
        return checked

    @event_filter.command("status", alias={"服务器状态", "状态", "zt", "s"})
    async def handle_server_status(self, event: AstrMessageEvent):
        now = time.time()
        async with self._lock:
            if self.cache_duration > 0 and self._cache and (now - self._cache_timestamp < self.cache_duration):
                yield event.plain_result(self._cache)
                return

            yield event.plain_result("正在重新获取服务器状态，请稍候...")

            try:
                # 延迟加载 Collector，仅在需要时实例化
                if self.collector is None:
                    self.collector = MetricsCollector(
                        disk_paths_to_check=self.plugin_config['disk_paths'],
                        show_temp=self.plugin_config['show_temp']
                    )
                    
                metrics = await asyncio.wait_for(asyncio.to_thread(self.collector.collect), timeout=20)
                if metrics is None:
                    yield event.plain_result("抱歉，获取核心服务器指标时发生错误，请检查日志。")
                    return

                text_message = self.formatter.format(metrics)
                self._cache, self._cache_timestamp = text_message, now
                yield event.plain_result(text_message)

            except asyncio.TimeoutError:
                logger.error("[StatusPlugin] 采集服务器状态超时")
                yield event.plain_result("抱歉，服务器状态采集超时，请联系管理员。")
            except Exception as e:
                logger.error("[StatusPlugin] 处理 status 指令时发生未知错误: %s", e, exc_info=True)
                yield event.plain_result("抱歉，获取状态时出现未知错误，请联系管理员。")
