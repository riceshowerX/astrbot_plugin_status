"""数据采集器模块 - 负责系统指标的采集和监控"""
import asyncio
import datetime
import logging
import os
import platform
import psutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Union, Any
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class DiskUsage:
    """磁盘使用情况数据类"""
    display_path: str
    total: int
    used: int
    free: int
    percent: float
    fs_type: str = "unknown"
    mount_point: str = ""

@dataclass(frozen=True)
class NetworkStats:
    """网络统计信息"""
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    errin: int
    errout: int
    dropin: int
    dropout: int

@dataclass(frozen=True)
class ProcessStats:
    """进程统计信息"""
    total: int
    running: int
    sleeping: int
    idle: int
    stopped: int
    zombie: int

@dataclass(frozen=True)
class SystemMetrics:
    """系统指标快照"""
    # CPU相关
    cpu_percent: Optional[float]
    cpu_temp: Optional[float]
    cpu_freq: Optional[float]
    cpu_cores: Optional[int]
    cpu_load_avg: Optional[Tuple[float, float, float]]
    
    # 内存相关
    mem_total: Optional[int]
    mem_used: Optional[int]
    mem_free: Optional[int]
    mem_percent: Optional[float]
    swap_total: Optional[int]
    swap_used: Optional[int]
    swap_percent: Optional[float]
    
    # 磁盘相关
    disks: List[DiskUsage]
    
    # 网络相关
    network: Optional[NetworkStats]
    
    # 进程相关
    processes: Optional[ProcessStats]
    
    # 系统信息
    uptime: Optional[datetime.timedelta]
    boot_time: Optional[datetime.datetime]
    is_containerized: bool
    platform_info: Dict[str, str]
    
    # 错误信息
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # 时间戳
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)

class MetricsCollector:
    """系统指标采集器"""
    
    # 常量定义
    MAX_DISK_COUNT = 15
    CPU_TEMP_KEYS = ['coretemp', 'k10temp', 'cpu_thermal', 'acpitz', 'zenpower']
    IGNORED_FS_TYPES = {
        'nfs', 'nfs4', 'smbfs', 'cifs', 'tmpfs', 'devtmpfs', 
        'proc', 'sysfs', 'fuse.gvfsd-fuse', 'overlay', 'squashfs',
        'autofs', 'mqueue', 'devpts', 'hugetlbfs', 'configfs'
    }
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.executor = ThreadPoolExecutor(max_workers=3)
        self._last_network_stats = None
        self._last_collection_time = None
        
    async def collect_metrics(self) -> SystemMetrics:
        """异步收集系统指标"""
        try:
            return await asyncio.get_event_loop().run_in_executor(
                self.executor, self._collect_sync
            )
        except Exception as e:
            logger.error(f"指标收集失败: {e}")
            return self._create_error_metrics([f"收集失败: {str(e)}"])
    
    def _collect_sync(self) -> SystemMetrics:
        """同步收集系统指标"""
        errors = []
        warnings = []
        
        # 收集各项指标
        cpu_info = self._collect_cpu_info(errors)
        memory_info = self._collect_memory_info(errors)
        disk_info = self._collect_disk_info(errors, warnings)
        network_info = self._collect_network_info(errors)
        process_info = self._collect_process_info(errors)
        system_info = self._collect_system_info(errors)
        
        return SystemMetrics(
            # CPU信息
            cpu_percent=cpu_info.get('percent'),
            cpu_temp=cpu_info.get('temp'),
            cpu_freq=cpu_info.get('freq'),
            cpu_cores=cpu_info.get('cores'),
            cpu_load_avg=cpu_info.get('load_avg'),
            
            # 内存信息
            mem_total=memory_info.get('total'),
            mem_used=memory_info.get('used'),
            mem_free=memory_info.get('free'),
            mem_percent=memory_info.get('percent'),
            swap_total=memory_info.get('swap_total'),
            swap_used=memory_info.get('swap_used'),
            swap_percent=memory_info.get('swap_percent'),
            
            # 磁盘信息
            disks=disk_info,
            
            # 网络信息
            network=network_info,
            
            # 进程信息
            processes=process_info,
            
            # 系统信息
            uptime=system_info.get('uptime'),
            boot_time=system_info.get('boot_time'),
            is_containerized=system_info.get('is_containerized', False),
            platform_info=system_info.get('platform_info', {}),
            
            # 错误和警告
            errors=errors,
            warnings=warnings
        )
    
    def _collect_cpu_info(self, errors: List[str]) -> Dict[str, Any]:
        """收集CPU信息"""
        info = {}
        try:
            # CPU使用率
            info['percent'] = psutil.cpu_percent(interval=0.5)
            
            # CPU频率
            try:
                freq = psutil.cpu_freq()
                if freq:
                    info['freq'] = freq.current
            except Exception:
                info['freq'] = None
            
            # CPU核心数
            info['cores'] = psutil.cpu_count(logical=False) or psutil.cpu_count()
            
            # 系统负载
            if hasattr(os, 'getloadavg'):
                try:
                    info['load_avg'] = os.getloadavg()
                except OSError:
                    info['load_avg'] = None
            
            # CPU温度
            if self.config.get('show_temp', True):
                info['temp'] = self._get_cpu_temperature()
                
        except Exception as e:
            errors.append(f"CPU信息收集失败: {str(e)}")
            logger.error(f"CPU信息收集错误: {e}")
            
        return info
    
    def _collect_memory_info(self, errors: List[str]) -> Dict[str, Any]:
        """收集内存信息"""
        info = {}
        try:
            # 物理内存
            mem = psutil.virtual_memory()
            info.update({
                'total': mem.total,
                'used': mem.used,
                'free': mem.free,
                'percent': mem.percent
            })
            
            # 交换内存
            swap = psutil.swap_memory()
            info.update({
                'swap_total': swap.total,
                'swap_used': swap.used,
                'swap_percent': swap.percent
            })
            
        except Exception as e:
            errors.append(f"内存信息收集失败: {str(e)}")
            logger.error(f"内存信息收集错误: {e}")
            
        return info
    
    def _collect_disk_info(self, errors: List[str], warnings: List[str]) -> List[DiskUsage]:
        """收集磁盘信息"""
        disks = []
        disk_config = self.config.get('disk_config', [])
        
        try:
            # 获取所有分区
            partitions = psutil.disk_partitions(all=False)
            
            # 处理配置的磁盘路径
            for cfg in disk_config:
                path = cfg.get('path')
                display = cfg.get('display', path)
                
                if not path or not self._is_safe_disk_path(path):
                    warnings.append(f"跳过不安全或无效的磁盘路径: {path}")
                    continue
                
                try:
                    usage = psutil.disk_usage(path)
                    disks.append(DiskUsage(
                        display_path=display,
                        total=usage.total,
                        used=usage.used,
                        free=usage.free,
                        percent=usage.percent,
                        mount_point=path
                    ))
                except Exception as e:
                    errors.append(f"磁盘 {display} 访问失败: {str(e)}")
            
            # 自动发现磁盘（如果配置允许）
            if not disk_config or self.config.get('auto_discover_disks', True):
                discovered = self._discover_disks(partitions, warnings)
                disks.extend(discovered)
                
        except Exception as e:
            errors.append(f"磁盘信息收集失败: {str(e)}")
            logger.error(f"磁盘信息收集错误: {e}")
            
        return disks[:self.MAX_DISK_COUNT]
    
    def _collect_network_info(self, errors: List[str]) -> Optional[NetworkStats]:
        """收集网络信息"""
        try:
            stats = psutil.net_io_counters()
            return NetworkStats(
                bytes_sent=stats.bytes_sent,
                bytes_recv=stats.bytes_recv,
                packets_sent=stats.packets_sent,
                packets_recv=stats.packets_recv,
                errin=stats.errin,
                errout=stats.errout,
                dropin=stats.dropin,
                dropout=stats.dropout
            )
        except Exception as e:
            errors.append(f"网络信息收集失败: {str(e)}")
            return None
    
    def _collect_process_info(self, errors: List[str]) -> Optional[ProcessStats]:
        """收集进程信息"""
        try:
            procs = []
            for proc in psutil.process_iter(['status']):
                try:
                    procs.append(proc.info['status'])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            status_count = {
                'running': 0,
                'sleeping': 0,
                'idle': 0,
                'stopped': 0,
                'zombie': 0
            }
            
            for status in procs:
                status_lower = status.lower()
                if status_lower in status_count:
                    status_count[status_lower] += 1
            
            return ProcessStats(
                total=len(procs),
                running=status_count['running'],
                sleeping=status_count['sleeping'],
                idle=status_count['idle'],
                stopped=status_count['stopped'],
                zombie=status_count['zombie']
            )
            
        except Exception as e:
            errors.append(f"进程信息收集失败: {str(e)}")
            return None
    
    def _collect_system_info(self, errors: List[str]) -> Dict[str, Any]:
        """收集系统信息"""
        info = {}
        try:
            # 启动时间和运行时间
            boot_time = psutil.boot_time()
            info['boot_time'] = datetime.datetime.fromtimestamp(boot_time)
            info['uptime'] = datetime.datetime.now() - info['boot_time']
            
            # 容器检测
            info['is_containerized'] = self._is_running_in_container()
            
            # 平台信息
            info['platform_info'] = {
                'system': platform.system(),
                'release': platform.release(),
                'version': platform.version(),
                'machine': platform.machine(),
                'processor': platform.processor(),
                'python_version': platform.python_version()
            }
            
        except Exception as e:
            errors.append(f"系统信息收集失败: {str(e)}")
            
        return info
    
    def _get_cpu_temperature(self) -> Optional[float]:
        """获取CPU温度"""
        try:
            if not hasattr(psutil, "sensors_temperatures"):
                return None
                
            temps = psutil.sensors_temperatures()
            all_temps = []
            
            for key in self.CPU_TEMP_KEYS:
                if key in temps and temps[key]:
                    valid_temps = [t.current for t in temps[key] if t.current is not None]
                    all_temps.extend(valid_temps)
            
            if all_temps:
                return sum(all_temps) / len(all_temps)
                
        except Exception:
            pass
            
        return None
    
    def _discover_disks(self, partitions: List, warnings: List[str]) -> List[DiskUsage]:
        """自动发现磁盘"""
        disks = []
        count = 0
        
        for part in partitions:
            if count >= self.MAX_DISK_COUNT:
                break
                
            if part.fstype.lower() in self.IGNORED_FS_TYPES:
                continue
                
            if not self._is_safe_disk_path(part.mountpoint):
                warnings.append(f"跳过不安全的自动发现磁盘: {part.mountpoint}")
                continue
                
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks.append(DiskUsage(
                    display_path=part.mountpoint,
                    total=usage.total,
                    used=usage.used,
                    free=usage.free,
                    percent=usage.percent,
                    fs_type=part.fstype,
                    mount_point=part.mountpoint
                ))
                count += 1
            except Exception:
                continue
                
        return disks
    
    def _is_safe_disk_path(self, path: Any) -> bool:
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
    
    def _is_running_in_container(self) -> bool:
        """检测是否运行在容器中"""
        # 容器检测逻辑
        indicators = [
            '/.dockerenv', '/.dockerinit',
            '/var/run/secrets/kubernetes.io', '/run/secrets/kubernetes.io'
        ]
        
        # 检查文件系统指示器
        for indicator in indicators[:2]:
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
    
    def _create_error_metrics(self, errors: List[str]) -> SystemMetrics:
        """创建错误指标"""
        return SystemMetrics(
            cpu_percent=None,
            cpu_temp=None,
            cpu_freq=None,
            cpu_cores=None,
            cpu_load_avg=None,
            mem_total=None,
            mem_used=None,
            mem_free=None,
            mem_percent=None,
            swap_total=None,
            swap_used=None,
            swap_percent=None,
            disks=[],
            network=None,
            processes=None,
            uptime=None,
            boot_time=None,
            is_containerized=False,
            platform_info={},
            errors=errors,
            warnings=[]
        )
    
    def close(self):
        """关闭采集器"""
        self.executor.shutdown(wait=False)