# -*- coding: utf-8 -*-
import psutil
import datetime
import platform
import asyncio
import time
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
import json
import os
import logging # 导入 logging 以检查 handler 类型

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
    # 在 Windows 上，允许 'C:\' 这样的路径。os.path.isabs 会正确处理。
    if not os.path.isabs(path):
        return False
    for c in ['..', '~', '\0', '*', '?', '|', '<', '>', '"']:
        if c in path:
            return False
    return True

def is_running_in_container() -> bool:
    """
    [新增] 一个启发式方法，用于检测是否在容器环境中运行 (如 Docker, Podman)。
    这对于生成准确的警告信息至关重要。
    """
    # 方法1: 检查 /.dockerenv 文件
    if os.path.exists('/.dockerenv'):
        return True
    # 方法2: 检查 cgroup 信息，这是更通用的方法
    try:
        with open('/proc/1/cgroup', 'rt') as f:
            for line in f:
                # 检查常见的容器指示符
                if 'docker' in line or 'kubepods' in line or 'containerd' in line:
                    return True
    except FileNotFoundError:
        # 如果不是Linux系统，或者/proc文件系统不可用
        pass
    return False


# --- 数据契约 (无变化) ---
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
    uptime: Optional[datetime.timedelta]
    disks: List[DiskUsage] = field(default_factory=list)


# --- 数据采集器 ---
class MetricsCollector:
    """收集系统指标，如 CPU、内存、磁盘和网络使用情况。"""
    MAX_DISK_COUNT = 10
    # [新增] CPU 温度传感器的检查顺序列表
    CPU_TEMP_KEYS: List[str] = ['coretemp', 'k10temp', 'cpu_thermal', 'acpitz']
    # [新增] 在自动发现磁盘时要忽略的文件系统类型，防止网络IO阻塞
    IGNORED_FS_TYPES: Set[str] = {
        'nfs', 'nfs4', 'smbfs', 'cifs',  # 网络文件系统
        'tmpfs', 'devtmpfs', 'proc', 'sysfs', 'fuse.gvfsd-fuse', 'overlay', 'squashfs' # 虚拟/特殊文件系统
    }

    def __init__(self, disk_paths_to_check: List[str], show_temp: bool):
        """
        初始化采集器。
        :param disk_paths_to_check: 经过验证和清洗的磁盘路径列表。
        :param show_temp: 是否显示 CPU 温度的布尔标志。
        """
        self.disk_paths_to_check = disk_paths_to_check
        self.show_temp = show_temp
        try:
            self.boot_time: Optional[datetime.datetime] = datetime.datetime.fromtimestamp(psutil.boot_time())
        except Exception as e:
            logger.error("[StatusPlugin] 获取系统启动时间失败: %s", e)
            self.boot_time = None

    def _get_disk_usages(self) -> List[DiskUsage]:
        """获取所有已配置或自动发现的磁盘的使用情况。"""
        disks = []
        paths_to_check = self.disk_paths_to_check

        if not paths_to_check:
            try:
                # [升级] 自动发现逻辑增加文件系统类型过滤
                all_parts = psutil.disk_partitions(all=False)
                filtered_mountpoints = []
                for part in all_parts:
                    if part.fstype.lower() in self.IGNORED_FS_TYPES:
                        logger.debug(f"[StatusPlugin] 自动发现时，已忽略类型为'{part.fstype}'的挂载点: {part.mountpoint}")
                        continue
                    if safe_disk_path(part.mountpoint):
                        filtered_mountpoints.append(part.mountpoint)

                paths_to_check = filtered_mountpoints[:self.MAX_DISK_COUNT]
            except Exception as e:
                logger.warning("[StatusPlugin] 自动发现磁盘分区失败，将使用默认根路径: %s", e)
                paths_to_check = ['C:\\' if platform.system() == "Windows" else '/']
        
        for path in paths_to_check:
            try:
                usage = psutil.disk_usage(path)
                disks.append(DiskUsage(path=path, total=usage.total, used=usage.used, percent=usage.percent))
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
                for key in self.CPU_TEMP_KEYS: # [升级] 使用常量列表
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


# --- 文本格式化器 ---
class MetricsFormatter:
    """将 SystemMetrics 格式化为人类可读的文本字符串。"""
    _BYTE_LABELS: Dict[int, str] = {0: ' B', 1: ' KB', 2: ' MB', 3: ' GB', 4: ' TB'}
    SEPARATOR = "--------------------"

    # [升级] 新增 is_containerized 参数以控制输出
    def format(self, metrics: SystemMetrics, is_containerized: bool = False) -> str:
        """
        格式化指标。
        :param metrics: 系统指标数据对象。
        :param is_containerized: 是否在容器中运行的标志。
        """
        parts = ["💻 **服务器实时状态**"]
        
        # [新增] 如果在容器中，添加警告信息
        if is_containerized:
            parts.append("⚠️ **在容器中运行，指标可能仅反映容器限制而非宿主机。**")
        
        parts.extend([
            self.SEPARATOR,
            self._format_uptime(metrics.uptime, is_containerized), # [升级] 传递容器标志
            self._format_cpu(metrics),
            self._format_memory(metrics),
            self._format_disks(metrics.disks),
            self._format_network(metrics),
        ])
        return "\n".join(filter(None, parts))

    # [升级] 增加 is_containerized 参数来改变文本
    def _format_uptime(self, uptime: Optional[datetime.timedelta], is_containerized: bool) -> str:
        """格式化运行时间，并根据环境提供上下文。"""
        # [升级] 根据是否在容器内，修改标题以提供更准确的上下文
        uptime_title = "⏱️ **运行时间**" if is_containerized else "⏱️ **已稳定运行 (宿主机)**"
        if uptime is None:
            return f"{uptime_title}: 未知"
            
        days, rem = divmod(uptime.total_seconds(), 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        return f"{uptime_title}: {int(days)}天 {int(hours)}小时 {int(minutes)}分钟"

    def _format_cpu(self, m: SystemMetrics) -> str:
        temp_str = f" (温度: {m.cpu_temp:.1f}°C)" if m.cpu_temp is not None else ""
        return f"{self.SEPARATOR}\n🖥️ **CPU**{temp_str}\n   - **使用率**: {m.cpu_percent:.1f}%"

    def _format_memory(self, m: SystemMetrics) -> str:
        used_formatted = self._format_bytes(m.mem_used)
        total_formatted = self._format_bytes(m.mem_total)
        return (f"{self.SEPARATOR}\n💾 **内存**\n   - **使用率**: {m.mem_percent:.1f}%\n"
                f"   - **已使用**: {used_formatted} / {total_formatted}")

    def _format_disks(self, disks: List[DiskUsage]) -> str:
        if not disks:
            return ""
        disk_parts = [
            f"""💿 **磁盘 ({self._escape_path(d.path)})**\n   - **使用率**: {d.percent:.1f}%\n   - **已使用**: {self._format_bytes(d.used)} / {self._format_bytes(d.total)}"""
            for d in disks
        ]
        return f"{self.SEPARATOR}\n" + f"\n{self.SEPARATOR}\n".join(disk_parts)

    def _format_network(self, m: SystemMetrics) -> str:
        # [升级] 修改标题以明确这是宿主机自启动以来的总计
        return (f"{self.SEPARATOR}\n🌐 **网络I/O (宿主机自启动总计)**\n"
                f"   - **总上传**: {self._format_bytes(m.net_sent)}\n"
                f"   - **总下载**: {self._format_bytes(m.net_recv)}")

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
@register(name="astrabot_plugin_status", author="riceshowerx & AstrBot Assistant",
          desc="以文本形式查询服务器的实时状态（生产环境加固版）", version="1.1",
          repo="https://github.com/riceshowerX/astrbot_plugin_status")
class ServerStatusPlugin(Star):
    """一个通过缓存和安全加固来报告实时服务器状态的插件。"""
    
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.context = context
        self.plugin_config: Dict[str, Any] = self._validate_config(config)
        
        self.collector: Optional[MetricsCollector] = None
        self.formatter = MetricsFormatter()
        
        self._cache: Optional[str] = None
        self._cache_timestamp: float = 0.0
        self.cache_duration: int = self.plugin_config.get('cache_duration', 5)
        self._lock = asyncio.Lock()
        
        # [新增] 启动时检测环境
        self.is_containerized = is_running_in_container()
        if self.is_containerized:
            logger.info("[StatusPlugin] 检测到在容器环境中运行，状态报告将包含提示。")
        
        # [新增] 启动时给予运维提示
        logger.info("[StatusPlugin] 插件已加载。建议检查机器人框架的日志轮转(rotation)配置，以防长期运行导致日志文件过大。")


    def _validate_config(self, config: AstrBotConfig) -> Dict[str, Any]:
        """验证原始配置并返回一个干净的字典。"""
        checked: Dict[str, Any] = {}
        try:
            cache_duration = int(config.get('cache_duration', 5))
            checked['cache_duration'] = cache_duration if 0 <= cache_duration <= 3600 else 5
        except (ValueError, TypeError):
            checked['cache_duration'] = 5
        
        disk_paths_raw = config.get('disk_paths', [])
        final_disk_paths: List[str] = []
        if isinstance(disk_paths_raw, str):
            try: disk_paths_raw = json.loads(disk_paths_raw)
            except json.JSONDecodeError: disk_paths_raw = []
        
        if isinstance(disk_paths_raw, list):
            final_disk_paths = [p for p in disk_paths_raw if safe_disk_path(p)]
        checked['disk_paths'] = final_disk_paths

        # 如果用户显式配置了 disk_paths，则打印一条 info 日志
        if final_disk_paths:
            logger.info(f"[StatusPlugin] 将监控用户配置的磁盘路径: {final_disk_paths}")
        else:
            logger.info("[StatusPlugin] 未配置 'disk_paths'，将自动发现本地磁盘。为避免IO阻塞，强烈建议在生产环境中显式配置。")

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
                if self.collector is None:
                    self.collector = MetricsCollector(
                        disk_paths_to_check=self.plugin_config['disk_paths'],
                        show_temp=self.plugin_config['show_temp']
                    )
                    
                metrics = await asyncio.wait_for(asyncio.to_thread(self.collector.collect), timeout=20)
                if metrics is None:
                    yield event.plain_result("抱歉，获取核心服务器指标时发生错误，请检查日志。")
                    return

                # [升级] 传递 is_containerized 标志给格式化器
                text_message = self.formatter.format(metrics, self.is_containerized)
                self._cache, self._cache_timestamp = text_message, now
                yield event.plain_result(text_message)

            except asyncio.TimeoutError:
                # [升级] 提供更详细的超时错误日志
                logger.error("[StatusPlugin] 采集服务器状态超时(20s)。这可能由系统调用无响应导致，请检查是否存在不稳定的网络磁盘(NFS/SMB)或硬件问题。")
                yield event.plain_result("抱歉，服务器状态采集超时，请联系管理员。")
            except Exception as e:
                logger.error("[StatusPlugin] 处理 status 指令时发生未知错误: %s", e, exc_info=True)
                yield event.plain_result("抱歉，获取状态时出现未知错误，请联系管理员。")