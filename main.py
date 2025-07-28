
import psutil
import datetime
import platform
import asyncio
import time
from typing import Dict, Any, Optional, List, Set, Union, Tuple
from dataclasses import dataclass, field
import json
import os
import logging

# --- Mocking for standalone testing ---
# This block allows the script to be run directly for testing without the full bot framework.
class MockLogger:
    def info(self, msg, *args): print(f"INFO: {msg}" % args)
    def warning(self, msg, *args): print(f"WARNING: {msg}" % args)
    def error(self, msg, *args, **kwargs): print(f"ERROR: {msg}" % args)
    def debug(self, msg, *args): print(f"DEBUG: {msg}" % args)

class MockContext: pass
class MockAstrBotConfig(dict): pass
class MockAstrMessageEvent:
    def plain_result(self, text): return f"--- BOT OUTPUT ---\n{text}\n------------------"

# Faking decorators and base class for standalone execution
def register(**kwargs): return lambda cls: cls
class Star:
    def __init__(self, context): pass
class event_filter:
    @staticmethod
    def command(*args, **kwargs): return lambda func: func

logger = MockLogger()
Context = MockContext
AstrBotConfig = MockAstrBotConfig
AstrMessageEvent = MockAstrMessageEvent
# --- End Mocking ---


# --- 工具函数 (Utility Functions) ---

def safe_disk_path(path: Any) -> bool:
    """
    Validates if the given path is a safe, absolute path for disk usage checks.
    [v2.1] Note: On Windows, os.path.isabs() correctly handles both drive letters and UNC paths (e.g., \\share\disk).
    """
    if not isinstance(path, str) or not path or len(path) > 1024:
        return False
    if not os.path.isabs(path):
        return False
    for c in ['..', '~', '\0', '*', '?', '|', '<', '>', '"']:
        if c in path:
            return False
    return True

def is_running_in_container() -> bool:
    """Heuristic check for containerized environments like Docker."""
    if os.path.exists('/.dockerenv'):
        return True
    try:
        with open('/proc/1/cgroup', 'rt') as f:
            for line in f:
                if 'docker' in line or 'kubepods' in line or 'containerd' in line:
                    return True
    except FileNotFoundError:
        pass # Not a Linux-based system with /proc
    return False

# --- 数据契约 (Data Contracts with Fault Tolerance) ---

@dataclass(frozen=True)
class DiskUsage:
    """Represents usage metrics for a single disk partition."""
    display_path: str
    total: int
    used: int
    percent: float

@dataclass(frozen=True)
class SystemMetrics:
    """
    [v2.1] System metrics snapshot, now supporting partial data.
    Metrics that fail to be collected will be None, with details in the 'errors' list.
    """
    cpu_percent: Optional[float]
    cpu_temp: Optional[float]
    mem_total: Optional[int]
    mem_used: Optional[int]
    mem_percent: Optional[float]
    net_sent: Optional[int]
    net_recv: Optional[int]
    uptime: Optional[datetime.timedelta]
    is_container_uptime: bool
    disks: Optional[List[DiskUsage]]
    errors: List[str] = field(default_factory=list)


# --- 数据采集器 (Data Collector with Graceful Degradation) ---

class MetricsCollector:
    """[v2.1] Collects system metrics with high fault tolerance."""
    MAX_DISK_COUNT = 10
    CPU_TEMP_KEYS: List[str] = ['coretemp', 'k10temp', 'cpu_thermal', 'acpitz']
    IGNORED_FS_TYPES: Set[str] = (
        {'nfs', 'nfs4', 'smbfs', 'cifs', 'tmpfs', 'devtmpfs', 'proc', 'sysfs', 'fuse.gvfsd-fuse', 'overlay', 'squashfs'}
        if platform.system() != "Windows" else set()
    )

    def __init__(self, disk_config: List[Dict[str, str]], show_temp: bool):
        self.disk_config = disk_config
        self.show_temp = show_temp
        self.boot_time, self.is_container_uptime = self._get_boot_time()

    def _get_boot_time(self) -> Tuple[Optional[datetime.datetime], bool]:
        """[v2.1] Get system or container boot time, establishing the uptime reference."""
        # English: Tries to get container boot time first by checking PID 1's creation time.
        # If it fails or not in a container, it gracefully falls back to the host's boot time.
        try:
            if is_running_in_container():
                proc_one_creation = psutil.Process(1).create_time()
                return datetime.datetime.fromtimestamp(proc_one_creation), True
        except (psutil.Error, FileNotFoundError, PermissionError):
            pass # Fallback to host boot time.
        
        try:
            return datetime.datetime.fromtimestamp(psutil.boot_time()), False
        except Exception as e:
            logger.error("[StatusPlugin] CRITICAL: Failed to get any system boot time: %s", e)
            return None, False

    def _get_disk_usages(self, errors: List[str]) -> Optional[List[DiskUsage]]:
        """[v2.1] Safely gets disk usages, appending errors on failure for graceful degradation."""
        disks: List[DiskUsage] = []
        paths_to_check_config = self.disk_config

        if not paths_to_check_config:
            try:
                all_parts = psutil.disk_partitions(all=False)
                if len(all_parts) > self.MAX_DISK_COUNT * 2: # Check before filtering
                    logger.warning("[StatusPlugin] Discovered %d partitions, will limit to %d. "
                                   "Please configure 'disk_paths' explicitly in production.",
                                   len(all_parts), self.MAX_DISK_COUNT)
                
                discovered_paths = []
                for part in all_parts:
                    if part.fstype.lower() in self.IGNORED_FS_TYPES: continue
                    if safe_disk_path(part.mountpoint):
                        discovered_paths.append({'path': part.mountpoint, 'display': part.mountpoint})
                paths_to_check_config = discovered_paths[:self.MAX_DISK_COUNT]
            except Exception as e:
                errors.append("Disk Discovery Failed")
                logger.error("[StatusPlugin] Disk auto-discovery failed: %s", e)
                return None
        
        for cfg in paths_to_check_config:
            # Using .get() for safety against malformed config dicts
            path, display_path = cfg.get('path'), cfg.get('display')
            if not path or not display_path: continue

            try:
                usage = psutil.disk_usage(path)
                disks.append(DiskUsage(display_path=display_path, total=usage.total, used=usage.used, percent=usage.percent))
            except (PermissionError, FileNotFoundError) as e:
                errors.append(f"Disk '{display_path}' Inaccessible")
                logger.warning("[StatusPlugin] Cannot access disk path '%s': %s", path, e.__class__.__name__)
            except Exception as e:
                errors.append(f"Disk '{display_path}' Failed")
                logger.warning("[StatusPlugin] Failed to get disk usage for '%s': %s", path, e)
        return disks

    def collect(self) -> SystemMetrics:
        """
        [v2.1] Collects all metrics with partial failure support. Never returns None.
        Gathers all possible data and reports errors for any failed parts.
        """
        errors: List[str] = []
        cpu_p, cpu_t, mem_data, net_data = None, None, None, None

        try:
            cpu_p = psutil.cpu_percent(interval=1)
        except Exception as e:
            errors.append("CPU Usage Failed")
            logger.warning("[StatusPlugin] Failed to collect CPU Usage: %s", e)

        if self.show_temp and hasattr(psutil, "sensors_temperatures"):
            try:
                temps = psutil.sensors_temperatures()
                all_temps = []
                for key in self.CPU_TEMP_KEYS:
                    if key in temps and temps[key]:
                        # [v2.1] Averages temperatures from all sensors/cores under the same key.
                        all_temps.extend([t.current for t in temps[key] if t.current is not None])
                if all_temps:
                    cpu_t = sum(all_temps) / len(all_temps)
            except Exception as e:
                errors.append("CPU Temp Failed")
                logger.warning("[StatusPlugin] Failed to collect CPU Temp: %s", e)

        try:
            mem_data = psutil.virtual_memory()
        except Exception as e:
            errors.append("Memory Usage Failed")
            logger.warning("[StatusPlugin] Failed to collect Memory Usage: %s", e)
        
        try:
            net_data = psutil.net_io_counters()
        except Exception as e:
            errors.append("Network I/O Failed")
            logger.warning("[StatusPlugin] Failed to collect Network I/O: %s", e)

        disks = self._get_disk_usages(errors)
        uptime = (datetime.datetime.now() - self.boot_time) if self.boot_time else None
        
        return SystemMetrics(
            cpu_percent=cpu_p, cpu_temp=cpu_t,
            mem_total=getattr(mem_data, 'total', None),
            mem_used=getattr(mem_data, 'used', None),
            mem_percent=getattr(mem_data, 'percent', None),
            net_sent=getattr(net_data, 'bytes_sent', None),
            net_recv=getattr(net_data, 'bytes_recv', None),
            uptime=uptime, is_container_uptime=self.is_container_uptime,
            disks=disks, errors=errors
        )

# --- 文本格式化器 (Formatter with Degradation Handling) ---

class MetricsFormatter:
    """[v2.1] Formats SystemMetrics into human-readable text, gracefully handling partial data."""
    _BYTE_LABELS: Dict[int, str] = {0: ' B', 1: ' KB', 2: ' MB', 3: ' GB', 4: ' TB'}
    SEPARATOR = "--------------------"

    def format(self, metrics: SystemMetrics, is_containerized: bool, privacy_level: str) -> str:
        parts = ["💻 **服务器实时状态**"]
        
        if is_containerized:
            parts.append("⚠️ **在容器中运行, 指标可能仅反映容器限制。**")

        if privacy_level == 'minimal':
            parts.extend([
                self.SEPARATOR,
                self._format_cpu(metrics),
                self._format_memory(metrics),
            ])
            if metrics.disks:
                parts.append(self._format_disks(metrics.disks, minimal_view=True))
        else: # 'full' view
            parts.extend([
                self.SEPARATOR,
                self._format_uptime(metrics),
                self._format_cpu(metrics),
                self._format_memory(metrics),
                self._format_disks(metrics.disks or [], minimal_view=False),
                self._format_network(metrics),
            ])

        # [v2.1] Append error summary if any errors occurred during collection.
        if metrics.errors:
            parts.append(f"{self.SEPARATOR}\n⚠️ **注意: 部分指标采集失败 ({', '.join(metrics.errors)})**")

        return "\n".join(filter(None, parts))

    def _format_uptime(self, m: SystemMetrics) -> str:
        uptime_title = "⏱️ **容器运行时间**" if m.is_container_uptime else "⏱️ **系统稳定运行**"
        if m.uptime is None: return f"{uptime_title}: N/A"
        
        days, rem = divmod(m.uptime.total_seconds(), 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        return f"{uptime_title}: {int(days)}天 {int(hours)}小时 {int(minutes)}分钟"

    def _format_cpu(self, m: SystemMetrics) -> str:
        cpu_usage = f"{m.cpu_percent:.1f}%" if m.cpu_percent is not None else "N/A"
        temp_str = f" (温度: {m.cpu_temp:.1f}°C)" if m.cpu_temp is not None else ""
        return f"{self.SEPARATOR}\n🖥️ **CPU**{temp_str}\n   - 使用率: {cpu_usage}"

    def _format_memory(self, m: SystemMetrics) -> str:
        mem_percent = f"{m.mem_percent:.1f}%" if m.mem_percent is not None else "N/A"
        used_mem = self._format_bytes(m.mem_used)
        total_mem = self._format_bytes(m.mem_total)
        return (f"{self.SEPARATOR}\n💾 **内存**\n   - 使用率: {mem_percent}\n"
                f"   - 已使用: {used_mem} / {total_mem}")

    def _format_disks(self, disks: List[DiskUsage], minimal_view: bool) -> str:
        if not disks: return ""
        if minimal_view:
            # Consistent formatting for minimal view.
            disk_parts = [f"   - 💿 **磁盘 ({self._escape_path(d.display_path)})**: {d.percent:.1f}%" for d in disks]
            return f"{self.SEPARATOR}\n" + "\n".join(disk_parts)

        disk_parts = [
            f"💿 **磁盘 ({self._escape_path(d.display_path)})**\n   - 使用率: {d.percent:.1f}%\n   - 已使用: {self._format_bytes(d.used)} / {self._format_bytes(d.total)}"
            for d in disks
        ]
        return f"{self.SEPARATOR}\n" + f"\n{self.SEPARATOR}\n".join(disk_parts)

    def _format_network(self, m: SystemMetrics) -> str:
        # [v2.1] Clarifies that stats are since process/bot start, not host boot.
        return (f"{self.SEPARATOR}\n🌐 **网络I/O (自进程启动后总计)**\n"
                f"   - 总上传: {self._format_bytes(m.net_sent)}\n"
                f"   - 总下载: {self._format_bytes(m.net_recv)}")

    @classmethod
    def _format_bytes(cls, byte_count: Optional[Union[int, float]]) -> str:
        """[v2.1] Safely formats bytes, handling None and float inputs."""
        if byte_count is None: return "N/A"
        byte_count = int(byte_count) # Ensure integer for calculations
        power, n = 1024, 0
        while byte_count >= power and n < len(cls._BYTE_LABELS) - 1:
            byte_count /= power
            n += 1
        return f"{byte_count:.2f}{cls._BYTE_LABELS[n]}"

    @staticmethod
    def _escape_path(path: str) -> str:
        # Simple sanitization for display. For stronger security, use a proper library.
        return path.replace('`', '').replace('*', '').replace('_', r'\_').replace('\n', '')


# --- AstrBot Plugin Main Class (Final Version) ---
@register(name="astrabot_plugin_status", author="riceshowerx & AstrBot Assistant",
          desc="[v2.1] 工业级状态插件. 警告: 请务必配置命令权限, 并锁定psutil版本!", version="2.1",
          repo="...") # Add your repo link here
class ServerStatusPlugin(Star):
    
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.context = context
        self.plugin_config = self._validate_and_parse_config(config)
        self.formatter = MetricsFormatter()
        self._lock = asyncio.Lock()
        self._cache: Optional[str] = None
        self._cache_timestamp: float = 0.0
        
        # --- Critical startup checks and initialization ---
        logger.info("="*50)
        logger.info("[StatusPlugin] Initializing Server Status Plugin v2.1...")
        self.is_containerized = is_running_in_container()

        try:
            self.collector = MetricsCollector(
                disk_config=self.plugin_config['disk_config'],
                show_temp=self.plugin_config['show_temp']
            )
            logger.info("[StatusPlugin] ✔️ Data Collector initialized successfully.")
        except Exception as e:
            logger.error("[StatusPlugin] ❌ Data Collector initialization failed! Plugin will be disabled. Error: %s", e, exc_info=True)
            self.collector = None # Disable plugin if collector fails to start

        logger.warning("\n\n"
                       "!!!!!!!!!!!!!!!!!!!!!!!!!! SECURITY & OPS WARNING !!!!!!!!!!!!!!!!!!!!!!!!!!\n"
                       "[StatusPlugin] 1. [CRITICAL] ACL: Ensure this 'status' command has strict access control!\n"
                       "[StatusPlugin] 2. [CRITICAL] DEPS: Pin the 'psutil' library version for supply chain security.\n"
                       "[StatusPlugin] 3. [RECOMMENDED] LOGS: Confirm log rotation is configured for the bot.\n"
                       "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n")
        logger.info("[StatusPlugin] ✨ Plugin loaded. Cache: %ds, Privacy: '%s', Timeout: %ds",
                    self.plugin_config['cache_duration'], self.plugin_config['privacy_level'], self.plugin_config['collect_timeout'])
        logger.info("="*50)

    def _validate_and_parse_config(self, config: AstrBotConfig) -> Dict[str, Any]:
        cfg = {}
        cfg['cache_duration'] = int(config.get('cache_duration', 10))
        cfg['collect_timeout'] = int(config.get('collect_timeout', 25))
        privacy_level = config.get('privacy_level', 'full').lower()
        cfg['privacy_level'] = privacy_level if privacy_level in ['full', 'minimal'] else 'full'
        
        final_disk_config: List[Dict[str, str]] = []
        disk_paths_raw = config.get('disk_paths', [])
        if isinstance(disk_paths_raw, list):
            for item in disk_paths_raw:
                if isinstance(item, str) and safe_disk_path(item):
                    final_disk_config.append({'path': item, 'display': item})
                elif isinstance(item, dict) and 'path' in item and safe_disk_path(item['path']):
                    display_name = item.get('display', item['path'])
                    final_disk_config.append({'path': item['path'], 'display': display_name})
        cfg['disk_config'] = final_disk_config
        cfg['show_temp'] = bool(config.get('show_temp', True))
        return cfg

    @event_filter.command("status", alias={"服务器状态", "状态", "zt", "s"})
    async def handle_server_status(self, event: AstrMessageEvent):
        if not self.collector:
            yield event.plain_result("抱歉, 状态插件未正确初始化, 请联系管理员检查日志。")
            return

        now = time.time()
        cache_duration = self.plugin_config['cache_duration']
        
        async with self._lock:
            # Double-check cache inside the lock
            if cache_duration > 0 and self._cache and (now - self._cache_timestamp < cache_duration):
                yield event.plain_result(self._cache)
                return

            yield event.plain_result("正在重新获取服务器状态, 请稍候...")

            try:
                timeout = self.plugin_config['collect_timeout']
                metrics = await asyncio.wait_for(asyncio.to_thread(self.collector.collect), timeout=timeout)
                
                # [v2.1] Logic is simpler now, as collect() never returns None.
                # It always returns a metrics object, possibly with partial data and an error list.
                text_message = self.formatter.format(
                    metrics, 
                    self.is_containerized, 
                    self.plugin_config['privacy_level']
                )
                
                # Only cache if there are no collection errors to avoid caching failure states.
                if not metrics.errors:
                    self._cache, self._cache_timestamp = text_message, now
                
                yield event.plain_result(text_message)

            except asyncio.TimeoutError:
                logger.error("[StatusPlugin] Data collection timed out after %ds.", timeout)
                yield event.plain_result(f"抱歉, 服务器状态采集超时 ({timeout}s), 请联系管理员。")
            except Exception as e:
                logger.error("[StatusPlugin] Unknown error during status handling: %s", e, exc_info=True)
                yield event.plain_result("抱歉, 处理状态指令时出现未知错误, 请联系管理员。")