import psutil
import datetime
import platform
import asyncio
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import json
import os

from astrbot.api.star import Star, register, Context
from astrbot.api.event import filter as event_filter, AstrMessageEvent
from astrbot.api import logger, AstrBotConfig

from image_renderer import render_status_image

def safe_disk_path(path: Any) -> bool:
    if not isinstance(path, str) or not path or len(path) > 1024:
        return False
    if not os.path.isabs(path):
        return False
    for c in ['..', '~', '\0', '*', '?', '|', '<', '>', '"']:
        if c in path:
            return False
    return True

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
    uptime: Optional[datetime.timedelta]
    disks: List[DiskUsage] = field(default_factory=list)

class MetricsCollector:
    MAX_DISK_COUNT = 10

    def __init__(self, disk_paths_to_check: List[str], show_temp: bool):
        self.disk_paths_to_check = disk_paths_to_check
        self.show_temp = show_temp
        try:
            self.boot_time: Optional[datetime.datetime] = datetime.datetime.fromtimestamp(psutil.boot_time())
        except Exception as e:
            logger.error("[StatusPlugin] 获取系统启动时间失败: %s", e)
            self.boot_time = None

    def _get_disk_usages(self) -> List[DiskUsage]:
        disks = []
        paths_to_check = self.disk_paths_to_check
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

        current_uptime = (datetime.datetime.now() - self.boot_time) if self.boot_time else None

        return SystemMetrics(
            cpu_percent=cpu_p, cpu_temp=cpu_t,
            mem_total=mem.total, mem_used=mem.used, mem_percent=mem.percent,
            net_sent=net.bytes_sent, net_recv=net.bytes_recv,
            uptime=current_uptime,
            disks=self._get_disk_usages()
        )

@register(
    name="astrabot_plugin_status",
    author="riceshowerx & AstrBot Assistant",
    desc="以图片形式查询服务器的实时状态",
    version="2.0",
    repo="https://github.com/riceshowerX/astrbot_plugin_status"
)
class ServerStatusPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.context = context
        self.plugin_config: Dict[str, Any] = self._validate_config(config)
        self.collector: Optional[MetricsCollector] = None
        self._cache: Optional[bytes] = None
        self._cache_timestamp: float = 0.0
        self.cache_duration: int = self.plugin_config.get('cache_duration', 5)
        self._lock = asyncio.Lock()
        self._font_path = self.plugin_config.get('font_path', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')

    def _validate_config(self, config: AstrBotConfig) -> Dict[str, Any]:
        checked: Dict[str, Any] = {}
        try:
            cache_duration = int(config.get('cache_duration', 5))
            checked['cache_duration'] = cache_duration if 0 <= cache_duration <= 3600 else 5
        except (ValueError, TypeError):
            checked['cache_duration'] = 5
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
        checked['font_path'] = config.get('font_path', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
        return checked

    @event_filter.command("status", alias={"服务器状态", "状态", "zt", "s"})
    async def handle_server_status(self, event, *args, **kwargs):
        now = time.time()
        async with self._lock:
            if self.cache_duration > 0 and self._cache and (now - self._cache_timestamp < self.cache_duration):
                yield event.image_result(self._cache, image_type="png")
                return

            yield event.plain_result("正在重新获取服务器状态，请稍候...")

            try:
                if self.collector is None:
                    self.collector = MetricsCollector(
                        disk_paths_to_check=self.plugin_config['disk_paths'],
                        show_temp=self.plugin_config['show_temp']
                    )
                metrics = await asyncio.wait_for(asyncio.to_thread(self.collector.collect), timeout=20)
                if metrics is None:
                    yield event.plain_result("抱歉，获取核心服务器指标时发生错误，请检查日志。")
                    return

                img_buffer = render_status_image(metrics, font_path=self._font_path)
                buf_bytes = img_buffer.getvalue()
                self._cache, self._cache_timestamp = buf_bytes, now
                yield event.image_result(buf_bytes, image_type="png")

            except asyncio.TimeoutError:
                logger.error("[StatusPlugin] 采集服务器状态超时")
                yield event.plain_result("抱歉，服务器状态采集超时，请联系管理员。")
            except Exception as e:
                logger.error("[StatusPlugin] 处理 status 指令时发生未知错误: %s", e, exc_info=True)
                yield event.plain_result("抱歉，获取状态时出现未知错误，请联系管理员。")
