
import psutil
import datetime
import platform
import asyncio
import time
from typing import Dict, Any, Optional, List, Set, Union
from dataclasses import dataclass, field
import json
import os
import logging

from astrbot.api.star import Star, register, Context
from astrbot.api.event import filter as event_filter, AstrMessageEvent
from astrbot.api import logger, AstrBotConfig

# --- Mocking for standalone testing ---
class MockLogger:
    def info(self, msg, *args): print(f"INFO: {msg}" % args)
    def warning(self, msg, *args): print(f"WARNING: {msg}" % args)
    def error(self, msg, *args, **kwargs): print(f"ERROR: {msg}" % args)
    def debug(self, msg, *args): print(f"DEBUG: {msg}" % args)
logger = MockLogger()
# --- End Mocking ---


# --- 工具函数 (无变化) ---
def safe_disk_path(path: Any) -> bool:
    if not isinstance(path, str) or not path or len(path) > 1024:
        return False
    if not os.path.isabs(path):
        return False
    for c in ['..', '~', '\0', '*', '?', '|', '<', '>', '"']:
        if c in path:
            return False
    return True

def is_running_in_container() -> bool:
    if os.path.exists('/.dockerenv'):
        return True
    try:
        with open('/proc/1/cgroup', 'rt') as f:
            for line in f:
                if 'docker' in line or 'kubepods' in line or 'containerd' in line:
                    return True
    except FileNotFoundError:
        pass
    return False

# --- 数据契约 (升级) ---
@dataclass(frozen=True)
class DiskUsage:
    """表示单个磁盘分区的使用情况指标。"""
    path: str
    display_path: str  # [新增] 用于显示的路径或别名
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
    is_container_uptime: bool  # [新增] 标记uptime是容器还是宿主机
    disks: List[DiskUsage] = field(default_factory=list)


# --- 数据采集器 (升级) ---
class MetricsCollector:
    """收集系统指标，如 CPU、内存、磁盘和网络使用情况。"""
    MAX_DISK_COUNT = 10
    CPU_TEMP_KEYS: List[str] = ['coretemp', 'k10temp', 'cpu_thermal', 'acpitz']
    # [升级] 根据操作系统决定忽略类型，对 Windows 无操作
    IGNORED_FS_TYPES: Set[str] = (
        {'nfs', 'nfs4', 'smbfs', 'cifs', 'tmpfs', 'devtmpfs', 'proc', 'sysfs', 'fuse.gvfsd-fuse', 'overlay', 'squashfs'}
        if platform.system() != "Windows" else set()
    )

    def __init__(self, disk_config: List[Dict[str, str]], show_temp: bool):
        """
        初始化采集器。
        :param disk_config: [升级] 清洗和验证后的磁盘配置列表。
        :param show_temp: 是否显示 CPU 温度的布尔标志。
        """
        self.disk_config = disk_config
        self.show_temp = show_temp
        self.is_containerized = is_running_in_container()
        
        # [升级] 优先获取容器启动时间，否则回退到宿主机启动时间
        self.boot_time: Optional[datetime.datetime] = None
        self.is_container_uptime = False
        try:
            if self.is_containerized:
                try:
                    # 尝试获取PID 1进程的创建时间，作为容器的启动时间
                    self.boot_time = datetime.datetime.fromtimestamp(psutil.Process(1).create_time())
                    self.is_container_uptime = True
                    logger.info("[StatusPlugin] 检测到容器环境，运行时间将从容器启动时计算。")
                except (psutil.NoSuchProcess, psutil.AccessDenied, FileNotFoundError):
                    logger.warning("[StatusPlugin] 无法获取容器启动时间，将回退到宿主机启动时间。")
            
            if not self.boot_time:
                self.boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
                self.is_container_uptime = False

        except Exception as e:
            logger.error("[StatusPlugin] 获取系统或容器启动时间失败: %s", e)

    def _get_disk_usages(self) -> List[DiskUsage]:
        disks = []
        paths_to_check_config = self.disk_config

        if not paths_to_check_config:
            try:
                all_parts = psutil.disk_partitions(all=False)
                discovered_paths = []
                for part in all_parts:
                    if part.fstype.lower() in self.IGNORED_FS_TYPES:
                        continue
                    if safe_disk_path(part.mountpoint):
                        # 自动发现时，路径和显示名相同
                        discovered_paths.append({'path': part.mountpoint, 'display': part.mountpoint})
                
                paths_to_check_config = discovered_paths[:self.MAX_DISK_COUNT]
            except Exception as e:
                logger.warning("[StatusPlugin] 自动发现磁盘分区失败，将使用默认根路径: %s", e)
                default_path = 'C:\\' if platform.system() == "Windows" else '/'
                paths_to_check_config = [{'path': default_path, 'display': default_path}]
        
        for cfg in paths_to_check_config:
            path, display_path = cfg['path'], cfg['display']
            try:
                usage = psutil.disk_usage(path)
                disks.append(DiskUsage(path=path, display_path=display_path, total=usage.total, used=usage.used, percent=usage.percent))
            except (PermissionError, FileNotFoundError):
                logger.warning("[StatusPlugin] 无法访问磁盘路径 '%s'，已忽略。", path)
            except Exception as e:
                logger.error("[StatusPlugin] 获取磁盘路径 '%s' 信息失败: %s", path, e, exc_info=True)
        return disks

    def collect(self) -> Optional[SystemMetrics]:
        try:
            # 增加采集间隔以降低瞬时CPU尖峰影响，使其更平滑
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
                for key in self.CPU_TEMP_KEYS:
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
            uptime=current_uptime, is_container_uptime=self.is_container_uptime,
            disks=self._get_disk_usages()
        )

# --- 文本格式化器 (升级) ---
class MetricsFormatter:
    _BYTE_LABELS: Dict[int, str] = {0: ' B', 1: ' KB', 2: ' MB', 3: ' GB', 4: ' TB'}
    SEPARATOR = "--------------------"

    # [升级] 新增 privacy_level 参数控制输出内容
    def format(self, metrics: SystemMetrics, is_containerized: bool, privacy_level: str) -> str:
        """
        根据隐私级别格式化指标。
        :param metrics: 系统指标数据对象。
        :param is_containerized: 是否在容器中运行。
        :param privacy_level: 'full' 或 'minimal'。
        """
        parts = ["💻 **服务器实时状态**"]
        
        if is_containerized:
            parts.append("⚠️ **在容器中运行，指标可能仅反映容器限制。**")

        if privacy_level == 'minimal':
            parts.extend([
                self.SEPARATOR,
                self._format_cpu(metrics),
                self._format_memory(metrics),
            ])
            if metrics.disks: # 即使是 minimal，如果配置了磁盘，也显示摘要
                parts.append(self._format_disks(metrics.disks, minimal_view=True))
            return "\n".join(filter(None, parts))

        # 默认 full 视图
        parts.extend([
            self.SEPARATOR,
            self._format_uptime(metrics.uptime, metrics.is_container_uptime),
            self._format_cpu(metrics),
            self._format_memory(metrics),
            self._format_disks(metrics.disks, minimal_view=False),
            self._format_network(metrics),
        ])
        return "\n".join(filter(None, parts))

    def _format_uptime(self, uptime: Optional[datetime.timedelta], is_container_uptime: bool) -> str:
        uptime_title = "⏱️ **容器运行时间**" if is_container_uptime else "⏱️ **系统稳定运行**"
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
    
    # [升级] 增加 minimal_view，并使用 display_path
    def _format_disks(self, disks: List[DiskUsage], minimal_view: bool) -> str:
        if not disks:
            return ""
        if minimal_view:
            disk_parts = [
                f"""💿 **磁盘 ({self._escape_path(d.display_path)})**: {d.percent:.1f}%"""
                for d in disks
            ]
            return f"{self.SEPARATOR}\n" + "\n   - ".join(disk_parts)

        disk_parts = [
            f"""💿 **磁盘 ({self._escape_path(d.display_path)})**\n   - **使用率**: {d.percent:.1f}%\n   - **已使用**: {self._format_bytes(d.used)} / {self._format_bytes(d.total)}"""
            for d in disks
        ]
        return f"{self.SEPARATOR}\n" + f"\n{self.SEPARATOR}\n".join(disk_parts)

    def _format_network(self, m: SystemMetrics) -> str:
        return (f"{self.SEPARATOR}\n🌐 **网络I/O (自启动总计)**\n"
                f"   - **总上传**: {self._format_bytes(m.net_sent)}\n"
                f"   - **总下载**: {self._format_bytes(m.net_recv)}")

    @classmethod
    def _format_bytes(cls, byte_count: int) -> str:
        # ... (无变化)
        if byte_count is None: return "N/A"
        power, n = 1024, 0
        while byte_count >= power and n < len(cls._BYTE_LABELS) - 1:
            byte_count /= power
            n += 1
        return f"{byte_count:.2f}{cls._BYTE_LABELS[n]}"


    @staticmethod
    def _escape_path(path: str) -> str:
        # ... (无变化)
        return path.replace('`', '').replace('*', '').replace('\n', '').replace('\r', '')


# --- AstrBot 插件主类 (全面升级) ---
# [升级] desc 包含给运维人员的安全警告
@register(name="astrabot_plugin_status", author="riceshowerx & AstrBot Assistant",
          desc="[安全加固版] 查询服务器状态。警告: 请务必配置命令权限, 并锁定psutil依赖版本!", version="2.0",
          repo="https://github.com/riceshowerX/astrbot_plugin_status")
class ServerStatusPlugin(Star):
    
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.context = context
        # [升级] 配置验证与解析
        self.plugin_config: Dict[str, Any] = self._validate_and_parse_config(config)
        
        self.formatter = MetricsFormatter()
        self._lock = asyncio.Lock()
        self._cache: Optional[str] = None
        self._cache_timestamp: float = 0.0
        
        # --- [升级] 启动时进行重要检查和初始化 ---
        logger.info("="*50)
        logger.info("[StatusPlugin] 正在初始化服务器状态插件 v2.0...")
        
        self.is_containerized = is_running_in_container()
        if self.is_containerized:
            logger.info("[StatusPlugin] ✔️ 检测到在容器环境中运行。")

        # [升级] 实例化采集器，提前暴露问题
        try:
            self.collector = MetricsCollector(
                disk_config=self.plugin_config['disk_config'],
                show_temp=self.plugin_config['show_temp']
            )
            logger.info("[StatusPlugin] ✔️ 数据采集器初始化成功。")
        except Exception as e:
            logger.error("[StatusPlugin] ❌ 数据采集器初始化失败! 插件将不可用。错误: %s", e, exc_info=True)
            self.collector = None

        # [升级] 关键安全和运维警告
        logger.warning("\n\n"
                       "!!!!!!!!!!!!!!!!!!!!!!!!!! 安全与运维警告 !!!!!!!!!!!!!!!!!!!!!!!!!!\n"
                       "[StatusPlugin] 1. [高危] 访问控制: 请务必在机器人框架中为此'status'命令设置严格的访问权限!\n"
                       "[StatusPlugin] 2. [高危] 供应链安全: 请使用 requirements.txt 或 poetry.lock 锁定 psutil 库的版本。\n"
                       "[StatusPlugin] 3. [建议] 日志轮转: 确认已为机器人配置日志轮转，以防日志文件过大。\n"
                       "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n")
        logger.info("[StatusPlugin] ✨ 插件已加载。当前缓存时间: %ds, 隐私级别: '%s'",
                    self.plugin_config['cache_duration'], self.plugin_config['privacy_level'])
        logger.info("="*50)


    def _validate_and_parse_config(self, config: AstrBotConfig) -> Dict[str, Any]:
        """[重构] 验证、解析和规范化插件配置，返回干净的字典。"""
        cfg = {}
        
        # 缓存和超时
        cfg['cache_duration'] = int(config.get('cache_duration', 10))
        cfg['collect_timeout'] = int(config.get('collect_timeout', 25))

        # 隐私级别
        privacy_level = config.get('privacy_level', 'full').lower()
        cfg['privacy_level'] = privacy_level if privacy_level in ['full', 'minimal'] else 'full'

        # 磁盘路径配置解析 (支持别名)
        disk_paths_raw = config.get('disk_paths', [])
        final_disk_config: List[Dict[str, str]] = []
        if isinstance(disk_paths_raw, list):
            for item in disk_paths_raw:
                if isinstance(item, str) and safe_disk_path(item):
                    final_disk_config.append({'path': item, 'display': item})
                elif isinstance(item, dict) and 'path' in item and safe_disk_path(item['path']):
                    display_name = item.get('display', item['path'])
                    final_disk_config.append({'path': item['path'], 'display': display_name})
        cfg['disk_config'] = final_disk_config

        if final_disk_config:
            logger.info(f"[StatusPlugin] 将监控用户配置的磁盘: {final_disk_config}")
        else:
            logger.warning("[StatusPlugin] 未配置 'disk_paths'，将自动发现。在生产环境中强烈建议显式配置以避免意外IO阻塞。")
        
        cfg['show_temp'] = bool(config.get('show_temp', True))
        return cfg

    @event_filter.command("status", alias={"服务器状态", "状态", "zt", "s"})
    async def handle_server_status(self, event: AstrMessageEvent):
        # 检查采集器是否成功初始化
        if self.collector is None:
            yield event.plain_result("抱歉，状态插件未正确初始化，请检查日志。")
            return

        now = time.time()
        # 尝试从缓存中获取
        cache_duration = self.plugin_config['cache_duration']
        if cache_duration > 0 and self._cache and (now - self._cache_timestamp < cache_duration):
            yield event.plain_result(self._cache)
            return

        # 缓存未命中，加锁并重新获取
        async with self._lock:
            # 双重检查锁定，防止在等待锁时缓存已被其他协程更新
            if cache_duration > 0 and self._cache and (now - self._cache_timestamp < cache_duration):
                yield event.plain_result(self._cache)
                return

            yield event.plain_result("正在重新获取服务器状态，请稍候...")

            try:
                # [升级] 使用可配置的超时时间
                timeout = self.plugin_config['collect_timeout']
                metrics = await asyncio.wait_for(asyncio.to_thread(self.collector.collect), timeout=timeout)
                
                if metrics is None:
                    yield event.plain_result("抱歉，获取核心服务器指标时发生错误，请检查日志。")
                    return

                # [升级] 传递隐私级别和容器标志给格式化器
                text_message = self.formatter.format(
                    metrics, 
                    self.is_containerized, 
                    self.plugin_config['privacy_level']
                )
                self._cache, self._cache_timestamp = text_message, now
                yield event.plain_result(text_message)

            except asyncio.TimeoutError:
                logger.error(f"[StatusPlugin] 采集服务器状态超时({timeout}s)。请检查是否存在不稳定的网络磁盘(NFS/SMB)或硬件问题。")
                yield event.plain_result(f"抱歉，服务器状态采集超时({timeout}s)，请联系管理员。")
            except Exception as e:
                logger.error("[StatusPlugin] 处理 status 指令时发生未知错误: %s", e, exc_info=True)
                yield event.plain_result("抱歉，获取状态时出现未知错误，请联系管理员。")