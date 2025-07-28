import psutil
import datetime
import platform
import asyncio
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import logging

from astrbot.api.star import Star, register, Context
from astrbot.api.event import filter as event_filter, AstrMessageEvent
from astrbot.api import logger, AstrBotConfig

import json

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
py_logger = logging.getLogger("StatusPlugin")

def safe_disk_path(path: str) -> bool:
    # 更严格的路径安全检查
    if not isinstance(path, str):
        return False
    if len(path) > 256:
        return False
    # 禁止特殊字符等
    for c in ['..', '~', '\0', '*', '?', '|', '<', '>', '"', ':']:
        if c in path:
            return False
    if path.startswith(' '):
        return False
    # 路径必须为绝对路径
    if not (path.startswith('/') or (':' in path and '\\' in path)):
        return False
    return True

class MetricsCollector:
    MAX_DISK_COUNT = 10

    def __init__(self, config: AstrBotConfig):
        self.config = config
        try:
            self.boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        except Exception as e:
            py_logger.error("[StatusPlugin] 获取系统启动时间失败: %s", e)
            self.boot_time = datetime.datetime.now()

    def _get_disk_usages(self) -> List[DiskUsage]:
        disks = []
        try:
            paths_to_check = self.config.get('disk_paths', [])
            if isinstance(paths_to_check, str):
                try:
                    paths_to_check = json.loads(paths_to_check)
                except Exception:
                    paths_to_check = []
            if not isinstance(paths_to_check, list):
                paths_to_check = []
        except Exception:
            paths_to_check = []

        if not paths_to_check:
            try:
                all_parts = [p.mountpoint for p in psutil.disk_partitions(all=False)]
                paths_to_check = all_parts[:self.MAX_DISK_COUNT]
            except Exception as e:
                py_logger.warning("[StatusPlugin] 自动发现磁盘分区失败，将使用默认路径: %s", e)
                paths_to_check = ['C:\\' if platform.system() == "Windows" else '/']

        checked = []
        for path in paths_to_check:
            if safe_disk_path(path):
                checked.append(path)
            else:
                py_logger.warning("[StatusPlugin] 非法磁盘路径被忽略: %r", path)
        paths_to_check = checked[:self.MAX_DISK_COUNT]

        for path in paths_to_check:
            try:
                usage = psutil.disk_usage(path)
                disks.append(DiskUsage(
                    path=path,
                    total=usage.total,
                    used=usage.used,
                    percent=usage.percent
                ))
            except PermissionError:
                py_logger.warning("[StatusPlugin] 无权限访问磁盘路径 '%s'，已忽略。", path)
            except FileNotFoundError:
                py_logger.warning("[StatusPlugin] 磁盘路径不存在 '%s'，已忽略。", path)
            except Exception as e:
                py_logger.warning("[StatusPlugin] 获取磁盘路径 '%s' 信息失败: %s", path, e)
        return disks

    def collect(self) -> Optional[SystemMetrics]:
        try:
            cpu_p = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            net = psutil.net_io_counters()
        except Exception as e:
            py_logger.error("[StatusPlugin] 获取核心系统指标失败: %s", e, exc_info=True)
            return None

        cpu_t = None
        try:
            if self.config.get("show_temp", True) and hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                for key in ['coretemp', 'k10temp', 'cpu_thermal', 'acpitz']:
                    if key in temps and temps[key]:
                        cpu_t = temps[key][0].current
                        break
        except Exception as e:
            py_logger.warning("[StatusPlugin] 获取CPU温度失败: %s", e)

        try:
            disks = self._get_disk_usages()
        except Exception as e:
            py_logger.error("[StatusPlugin] 获取磁盘信息时发生异常: %s", e)
            disks = []

        return SystemMetrics(
            cpu_percent=cpu_p, cpu_temp=cpu_t,
            mem_total=mem.total, mem_used=mem.used, mem_percent=mem.percent,
            net_sent=net.bytes_sent, net_recv=net.bytes_recv,
            uptime=datetime.datetime.now() - self.boot_time,
            disks=disks
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
        temp_str = f" ({m.cpu_temp:.1f}°C)" if m.cpu_temp is not None else ""
        return f"--------------------\n🖥️ **CPU**{temp_str}\n   - **使用率**: {m.cpu_percent:.1f}%"

    def _format_memory(self, m: SystemMetrics) -> str:
        used_formatted = self._format_bytes(m.mem_used)
        total_formatted = self._format_bytes(m.mem_total)
        return (
            "--------------------\n💾 **内存**\n"
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
        return "--------------------\n" + "\n--------------------\n".join(disk_parts)

    def _format_network(self, m: SystemMetrics) -> str:
        return (
            "--------------------\n🌐 **网络I/O (自启动)**\n"
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
        # 防止路径中出现格式污染字符
        return path.replace('`', '').replace('*', '').replace('\n', '').replace('\r', '')

# --- AstrBot 插件主类 ---
@register(
    name="astrabot_plugin_status",
    author="riceshowerx & AstrBot Assistant",
    desc="以文本形式查询服务器的实时状态 (已加固安全性)",
    version="3.1.5",
    repo="https://github.com/riceshowerX/astrbot_plugin_status"
)
class ServerStatusPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.context = context
        self.config = self._validate_config(config)
        self.collector = None
        self.formatter = MetricsFormatter()
        self._cache: Optional[str] = None
        self._cache_timestamp: float = 0.0
        self.cache_duration = self.config.get('cache_duration', 5)
        self._lock = asyncio.Lock()

    def _validate_config(self, config: AstrBotConfig) -> AstrBotConfig:
        checked = {}
        try:
            checked['cache_duration'] = int(config.get('cache_duration', 5))
            if checked['cache_duration'] < 0 or checked['cache_duration'] > 3600:
                checked['cache_duration'] = 5
        except Exception:
            checked['cache_duration'] = 5

        try:
            disk_paths = config.get('disk_paths', [])
            if isinstance(disk_paths, str):
                try:
                    disk_paths = json.loads(disk_paths)
                except Exception:
                    disk_paths = []
            if not isinstance(disk_paths, list):
                disk_paths = []
            checked['disk_paths'] = [p for p in disk_paths if safe_disk_path(p)]
        except Exception:
            checked['disk_paths'] = []

        try:
            checked['show_temp'] = bool(config.get('show_temp', True))
        except Exception:
            checked['show_temp'] = True

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
                if self.collector is None:
                    self.collector = MetricsCollector(self.config)
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
