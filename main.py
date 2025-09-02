"""
AstrBot Server Status Plugin v3.0 - 优化升级版
工业级服务器状态监控插件，支持多格式输出和智能缓存
"""

import asyncio
import datetime
import logging
import os
import platform
import psutil
import time
from typing import Dict, List, Optional, Set, Tuple, Union, Any
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

from astrbot.api.star import Star, register, Context
from astrbot.api.event import filter as event_filter, AstrMessageEvent
from astrbot.api import logger as astr_logger, AstrBotConfig

# 配置插件日志
logger = logging.getLogger(__name__)

# --- 数据契约定义 ---

@dataclass(frozen=True)
class DiskUsage:
    """磁盘使用情况"""
    display_path: str
    total: int
    used: int
    free: int
    percent: float

@dataclass(frozen=True)
class SystemMetrics:
    """系统指标快照"""
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
    warnings: List[str] = field(default_factory=list)

# --- 工具函数 ---

def safe_disk_path(path: Any) -> bool:
    """检查磁盘路径是否安全"""
    if not isinstance(path, str) or not path or len(path) > 1024:
        return False
        
    normalized = path.replace('\\', '/')
    
    # 安全检查
    forbidden = ['..', '~', '\0', '*', '?', '|', '<', '>', '"', '//', '\\\\']
    if any(pattern in path for pattern in forbidden):
        return False
        
    if '../' in normalized or '/..' in normalized:
        return False
        
    # Windows特定检查
    if platform.system() == "Windows":
        if normalized.startswith('//') and '..' in normalized:
            return False
        if ':' in path and path.index(':') > 1:
            return False
            
    return os.path.isabs(path)

def is_running_in_container() -> bool:
    """检测是否运行在容器中"""
    # 容器检测逻辑
    indicators = ['/.dockerenv', '/.dockerinit']
    
    # 检查文件系统指示器
    for indicator in indicators:
        if os.path.exists(indicator):
            return True
            
    # 检查cgroup
    if platform.system() != "Windows":
        try:
            cgroup_paths = ['/proc/1/cgroup', '/proc/self/cgroup']
            for cgroup_path in cgroup_paths:
                if os.path.exists(cgroup_path):
                    with open(cgroup_path, 'rt', encoding='utf-8') as f:
                        content = f.read()
                        if any(keyword in content for keyword in ['docker', 'kubepods', 'containerd', 'lxc']):
                            return True
        except (FileNotFoundError, PermissionError, UnicodeDecodeError):
            pass
            
    # 检查环境变量
    env_keys = os.environ.keys()
    container_env_vars = ['KUBERNETES_SERVICE_HOST', 'DOCKER_CONTAINER']
    if any(key in env_keys for key in container_env_vars):
        return True
        
    return False

# --- 核心组件 ---

class MetricsCollector:
    """系统指标采集器"""
    
    MAX_DISK_COUNT = 10
    CPU_TEMP_KEYS = ['coretemp', 'k10temp', 'cpu_thermal', 'acpitz']
    IGNORED_FS_TYPES = {'nfs', 'nfs4', 'smbfs', 'cifs', 'tmpfs', 'devtmpfs', 'proc', 'sysfs'}

    def __init__(self, disk_config: List[Dict[str, str]], show_temp: bool):
        self.disk_config = disk_config
        self.show_temp = show_temp
        self.boot_time, self.is_container_uptime = self._get_boot_time()
        self.executor = ThreadPoolExecutor(max_workers=3)

    def _get_boot_time(self) -> Tuple[Optional[datetime.datetime], bool]:
        """获取启动时间"""
        try:
            if is_running_in_container():
                proc_one_creation = psutil.Process(1).create_time()
                return datetime.datetime.fromtimestamp(proc_one_creation), True
        except (psutil.Error, FileNotFoundError, PermissionError):
            pass
            
        try:
            return datetime.datetime.fromtimestamp(psutil.boot_time()), False
        except Exception as e:
            logger.error("Failed to get boot time: %s", e)
            return None, False

    async def collect_metrics(self) -> SystemMetrics:
        """异步收集系统指标"""
        try:
            return await asyncio.get_event_loop().run_in_executor(
                self.executor, self._collect_sync
            )
        except Exception as e:
            logger.error("Metrics collection failed: %s", e)
            return SystemMetrics(
                cpu_percent=None, cpu_temp=None, mem_total=None, mem_used=None,
                mem_percent=None, net_sent=None, net_recv=None, uptime=None,
                is_container_uptime=False, disks=[], errors=[f"Collection failed: {str(e)}"]
            )

    def _collect_sync(self) -> SystemMetrics:
        """同步收集系统指标"""
        errors = []
        warnings = []
        cpu_p, cpu_t, mem_data, net_data = None, None, None, None

        try:
            cpu_p = psutil.cpu_percent(interval=1)
        except Exception as e:
            errors.append("CPU Usage Failed")
            logger.warning("Failed to collect CPU Usage: %s", e)

        if self.show_temp and hasattr(psutil, "sensors_temperatures"):
            try:
                temps = psutil.sensors_temperatures()
                all_temps = []
                for key in self.CPU_TEMP_KEYS:
                    if key in temps and temps[key]:
                        all_temps.extend([t.current for t in temps[key] if t.current is not None])
                if all_temps:
                    cpu_t = sum(all_temps) / len(all_temps)
            except Exception as e:
                errors.append("CPU Temp Failed")
                logger.warning("Failed to collect CPU Temp: %s", e)

        try:
            mem_data = psutil.virtual_memory()
        except Exception as e:
            errors.append("Memory Usage Failed")
            logger.warning("Failed to collect Memory Usage: %s", e)
        
        try:
            net_data = psutil.net_io_counters()
        except Exception as e:
            errors.append("Network I/O Failed")
            logger.warning("Failed to collect Network I/O: %s", e)

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
            disks=disks, errors=errors, warnings=warnings
        )

    def _get_disk_usages(self, errors: List[str]) -> Optional[List[DiskUsage]]:
        """获取磁盘使用情况"""
        disks = []
        paths_to_check = self.disk_config

        if not paths_to_check:
            try:
                all_parts = psutil.disk_partitions(all=False)
                discovered_paths = []
                for part in all_parts:
                    if part.fstype.lower() in self.IGNORED_FS_TYPES:
                        continue
                    if safe_disk_path(part.mountpoint):
                        discovered_paths.append({'path': part.mountpoint, 'display': part.mountpoint})
                paths_to_check = discovered_paths[:self.MAX_DISK_COUNT]
            except Exception as e:
                errors.append("Disk Discovery Failed")
                logger.error("Disk auto-discovery failed: %s", e)
                return None
        
        for cfg in paths_to_check:
            path, display_path = cfg.get('path'), cfg.get('display')
            if not path or not display_path:
                continue

            try:
                usage = psutil.disk_usage(path)
                disks.append(DiskUsage(
                    display_path=display_path,
                    total=usage.total,
                    used=usage.used,
                    free=usage.free,
                    percent=usage.percent
                ))
            except Exception as e:
                errors.append(f"Disk '{display_path}' Failed")
                logger.warning("Failed to get disk usage for '%s': %s", path, e)
        
        return disks

    def close(self):
        """关闭采集器"""
        self.executor.shutdown(wait=False)

class MetricsFormatter:
    """系统指标格式化器"""
    
    BYTE_LABELS = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    SEPARATOR = "─" * 40
    EMOJI_MAP = {'cpu': '🖥️', 'memory': '💾', 'disk': '💿', 'network': '🌐'}

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
    def format(self, metrics: SystemMetrics, is_containerized: bool, privacy_level: str) -> str:
        """格式化系统指标"""
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
        else:
            parts.extend([
                self.SEPARATOR,
                self._format_uptime(metrics),
                self._format_cpu(metrics),
                self._format_memory(metrics),
                self._format_disks(metrics.disks or [], minimal_view=False),
                self._format_network(metrics),
            ])

        if metrics.errors:
            parts.append(f"{self.SEPARATOR}\n⚠️ **注意: 部分指标采集失败 ({', '.join(metrics.errors)})**")

        return "\n".join(filter(None, parts))

    def _format_uptime(self, m: SystemMetrics) -> str:
        uptime_title = "⏱️ **容器运行时间**" if m.is_container_uptime else "⏱️ **系统稳定运行**"
        if m.uptime is None:
            return f"{uptime_title}: N/A"
        
        days, rem = divmod(m.uptime.total_seconds(), 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        return f"{uptime_title}: {int(days)}天 {int(hours)}小时 {int(minutes)}分钟"

    def _format_cpu(self, m: SystemMetrics) -> str:
        cpu_usage = f"{m.cpu_percent:.1f}%" if m.cpu_percent is not None else "N/A"
        temp_str = f" (温度: {m.cpu_temp:.1f}°C)" if m.cpu_temp is not None else ""
        return f"{self.SEPARATOR}\n{self.EMOJI_MAP['cpu']} **CPU**{temp_str}\n   - 使用率: {cpu_usage}"

    def _format_memory(self, m: SystemMetrics) -> str:
        mem_percent = f"{m.mem_percent:.1f}%" if m.mem_percent is not None else "N/A"
        used_mem = self._format_bytes(m.mem_used)
        total_mem = self._format_bytes(m.mem_total)
        return (f"{self.SEPARATOR}\n{self.EMOJI_MAP['memory']} **内存**\n   - 使用率: {mem_percent}\n"
                f"   - 已使用: {used_mem} / {total_mem}")

    def _format_disks(self, disks: List[DiskUsage], minimal_view: bool) -> str:
        if not disks:
            return ""
        if minimal_view:
            disk_parts = [f"   - {self.EMOJI_MAP['disk']} **磁盘 ({self._escape_path(d.display_path)})**: {d.percent:.1f}%" for d in disks]
            return f"{self.SEPARATOR}\n" + "\n".join(disk_parts)

        disk_parts = [
            f"{self.EMOJI_MAP['disk']} **磁盘 ({self._escape_path(d.display_path)})**\n   - 使用率: {d.percent:.1f}%\n   - 已使用: {self._format_bytes(d.used)} / {self._format_bytes(d.total)}"
            for d in disks
        ]
        return f"{self.SEPARATOR}\n" + f"\n{self.SEPARATOR}\n".join(disk_parts)

    def _format_network(self, m: SystemMetrics) -> str:
        return (f"{self.SEPARATOR}\n{self.EMOJI_MAP['network']} **网络I/O (自进程启动后总计)**\n"
                f"   - 总上传: {self._format_bytes(m.net_sent)}\n"
                f"   - 总下载: {self._format_bytes(m.net_recv)}")

    def _format_bytes(self, byte_count: Optional[Union[int, float]]) -> str:
        if byte_count is None:
            return "N/A"
        byte_count = int(byte_count)
        power, n = 1024, 0
        while byte_count >= power and n < len(self.BYTE_LABELS) - 1:
            byte_count /= power
            n += 1
        return f"{byte_count:.2f}{self.BYTE_LABELS[n]}"

    @staticmethod
    def _escape_path(path: str) -> str:
        escape_chars = ['`', '*', '_', '{', '}', '[', ']', '(', ')', '#', '+', '-', '.', '!', '|']
        for char in escape_chars:
            path = path.replace(char, '')
        path = path.replace('\n', ' ').replace('\r', ' ').strip()
        if len(path) > 50:
            path = path[:47] + '...'
        return path

# --- 主插件类 ---

@register(
    name="astrbot_plugin_status",
    author="riceshowerx & AstrBot Assistant",
    desc="[v3.0] 工业级服务器状态监控插件",
    version="3.0.0",
    repo="https://github.com/riceshowerX/astrbot_plugin_status"
)
class ServerStatusPlugin(Star):
    
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.context = context
        self.plugin_config = self._validate_and_parse_config(config)
        self.formatter = MetricsFormatter(self.plugin_config)
        self._lock = asyncio.Lock()
        self._cache: Optional[str] = None
        self._cache_timestamp: float = 0.0
        self.is_containerized = is_running_in_container()
        
        # 初始化采集器
        try:
            self.collector = MetricsCollector(
                disk_config=self.plugin_config['disk_config'],
                show_temp=self.plugin_config['show_temp']
            )
            logger.info("✅ Data Collector initialized successfully")
        except Exception as e:
            logger.error("❌ Data Collector initialization failed: %s", e)
            self.collector = None

        # 记录启动信息
        self._log_startup_info()

    def _validate_and_parse_config(self, config: AstrBotConfig) -> Dict[str, Any]:
        """验证和解析配置"""
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

    def _log_startup_info(self):
        """记录启动信息"""
        config = self.plugin_config
        astr_logger.info("=" * 50)
        astr_logger.info("[StatusPlugin] Initializing Server Status Plugin v3.0...")
        astr_logger.info("[StatusPlugin] Cache: %ds, Privacy: '%s', Timeout: %ds",
                        config['cache_duration'], config['privacy_level'], config['collect_timeout'])
        astr_logger.info("=" * 50)

    @event_filter.command("status", alias={"服务器状态", "状态", "zt", "s"})
    async def handle_server_status(self, event: AstrMessageEvent):
        """处理服务器状态查询"""
        if not self.collector:
            yield event.plain_result("❌ 状态插件未正确初始化，请联系管理员检查日志。")
            return

        # 检查缓存
        now = time.time()
        cache_duration = self.plugin_config['cache_duration']
        
        async with self._lock:
            if cache_duration > 0 and self._cache and (now - self._cache_timestamp < cache_duration):
                yield event.plain_result(self._cache)
                return

            yield event.plain_result("🔄 正在重新获取服务器状态，请稍候...")

            try:
                # 采集指标
                timeout = self.plugin_config['collect_timeout']
                metrics = await asyncio.wait_for(
                    self.collector.collect_metrics(), 
                    timeout=timeout
                )
                
                # 格式化输出
                text_message = self.formatter.format(
                    metrics, 
                    self.is_containerized, 
                    self.plugin_config['privacy_level']
                )
                
                # 缓存成功的结果
                if not metrics.errors:
                    self._cache, self._cache_timestamp = text_message, now
                
                yield event.plain_result(text_message)

            except asyncio.TimeoutError:
                error_msg = f"⏰ 数据采集超时 ({timeout}s)，请稍后重试或联系管理员。"
                logger.error("Data collection timed out")
                yield event.plain_result(error_msg)
            except Exception as e:
                error_msg = "❌ 处理状态请求时出现未知错误，请联系管理员。"
                logger.error("Status handling error: %s", e)
                yield event.plain_result(error_msg)

    @event_filter.command("status_help", alias={"状态帮助", "help"})
    async def handle_help(self, event: AstrMessageEvent):
        """显示帮助信息"""
        help_text = """📖 **服务器状态插件帮助**

**命令别名:**
- `/status` / `状态` / `zt` / `s`

**功能特性:**
- ✅ 实时系统监控 (CPU/内存/磁盘/网络)
- ✅ 智能缓存机制
- ✅ 容器环境支持
- ✅ 隐私保护模式

**配置选项:**
- 隐私级别 (full/minimal)
- 缓存时间 (0-3600秒)
- 磁盘路径监控
- CPU温度显示

需要更多帮助？请查看项目文档。"""
        
        yield event.plain_result(help_text)

# 插件入口
if __name__ == "__main__":
    print("AstrBot Server Status Plugin v3.0")
    print("This plugin must be loaded within AstrBot environment.")