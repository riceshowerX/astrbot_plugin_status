"""格式化器模块 - 负责将系统指标格式化为可读文本"""
import datetime
from typing import Dict, List, Optional, Union, Any
from .collector import SystemMetrics, DiskUsage, NetworkStats, ProcessStats

class MetricsFormatter:
    """系统指标格式化器"""
    
    # 常量定义
    BYTE_LABELS = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB', 5: 'PB'}
    SEPARATOR = "─" * 40
    EMOJI_MAP = {
        'cpu': '🖥️',
        'memory': '💾', 
        'disk': '💿',
        'network': '🌐',
        'process': '📊',
        'system': '⚙️',
        'warning': '⚠️',
        'error': '❌',
        'success': '✅',
        'info': 'ℹ️'
    }
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
    def format(self, metrics: SystemMetrics) -> str:
        """格式化系统指标为可读文本"""
        privacy_level = self.config.get('privacy_level', 'full')
        output_format = self.config.get('output_format', 'markdown')
        
        if output_format == 'json':
            return self._format_json(metrics)
        elif output_format == 'plain':
            return self._format_plain(metrics, privacy_level)
        else:
            return self._format_markdown(metrics, privacy_level)
    
    def _format_markdown(self, metrics: SystemMetrics, privacy_level: str) -> str:
        """Markdown格式输出"""
        parts = [f"# {self.EMOJI_MAP['system']} 服务器实时状态"]
        
        # 容器警告
        if metrics.is_containerized:
            parts.append(f"{self.EMOJI_MAP['warning']} **在容器环境中运行，指标反映容器限制**")
        
        # 系统信息
        parts.extend([
            self.SEPARATOR,
            self._format_system_info(metrics, privacy_level),
            self._format_cpu_info(metrics, privacy_level),
            self._format_memory_info(metrics, privacy_level),
            self._format_disk_info(metrics.disks, privacy_level),
            self._format_network_info(metrics.network, privacy_level),
            self._format_process_info(metrics.processes, privacy_level)
        ])
        
        # 错误和警告信息
        if metrics.errors or metrics.warnings:
            parts.append(self.SEPARATOR)
            if metrics.warnings:
                parts.append(f"{self.EMOJI_MAP['warning']} **警告**: {', '.join(metrics.warnings)}")
            if metrics.errors:
                parts.append(f"{self.EMOJI_MAP['error']} **错误**: {', '.join(metrics.errors)}")
        
        # 时间戳
        parts.append(f"{self.SEPARATOR}\n📅 **数据更新时间**: {metrics.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        
        return "\n".join(filter(None, parts))
    
    def _format_plain(self, metrics: SystemMetrics, privacy_level: str) -> str:
        """纯文本格式输出"""
        parts = ["服务器状态报告:"]
        
        if metrics.is_containerized:
            parts.append("[警告] 在容器环境中运行")
        
        parts.extend([
            self.SEPARATOR,
            self._format_system_info(metrics, privacy_level, plain=True),
            self._format_cpu_info(metrics, privacy_level, plain=True),
            self._format_memory_info(metrics, privacy_level, plain=True),
            self._format_disk_info(metrics.disks, privacy_level, plain=True),
            self._format_network_info(metrics.network, privacy_level, plain=True),
            self._format_process_info(metrics.processes, privacy_level, plain=True)
        ])
        
        if metrics.errors:
            parts.append(f"[错误] {', '.join(metrics.errors)}")
        if metrics.warnings:
            parts.append(f"[警告] {', '.join(metrics.warnings)}")
            
        parts.append(f"更新时间: {metrics.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        
        return "\n".join(filter(None, parts))
    
    def _format_json(self, metrics: SystemMetrics) -> str:
        """JSON格式输出"""
        import json
        return json.dumps({
            'system_info': self._get_system_info_dict(metrics),
            'cpu_info': self._get_cpu_info_dict(metrics),
            'memory_info': self._get_memory_info_dict(metrics),
            'disk_info': [self._get_disk_info_dict(disk) for disk in metrics.disks],
            'network_info': self._get_network_info_dict(metrics.network),
            'process_info': self._get_process_info_dict(metrics.processes),
            'errors': metrics.errors,
            'warnings': metrics.warnings,
            'timestamp': metrics.timestamp.isoformat()
        }, indent=2, ensure_ascii=False)
    
    def _format_system_info(self, metrics: SystemMetrics, privacy_level: str, plain: bool = False) -> str:
        """格式化系统信息"""
        if metrics.uptime is None:
            return ""
            
        uptime_str = self._format_timedelta(metrics.uptime)
        uptime_title = "容器运行时间" if metrics.is_containerized else "系统运行时间"
        
        if plain:
            return f"{uptime_title}: {uptime_str}"
        else:
            return f"⏱️ **{uptime_title}**: {uptime_str}"
    
    def _format_cpu_info(self, metrics: SystemMetrics, privacy_level: str, plain: bool = False) -> str:
        """格式化CPU信息"""
        cpu_parts = []
        
        # CPU使用率
        if metrics.cpu_percent is not None:
            usage_str = f"{metrics.cpu_percent:.1f}%"
            cpu_parts.append(f"使用率: {usage_str}")
        
        # CPU温度
        if metrics.cpu_temp is not None and privacy_level != 'minimal':
            temp_str = f"{metrics.cpu_temp:.1f}°C"
            cpu_parts.append(f"温度: {temp_str}")
        
        # CPU频率
        if metrics.cpu_freq is not None and privacy_level != 'minimal':
            freq_str = f"{metrics.cpu_freq:.0f}MHz"
            cpu_parts.append(f"频率: {freq_str}")
        
        # CPU核心数
        if metrics.cpu_cores is not None and privacy_level != 'minimal':
            cores_str = f"{metrics.cpu_cores}核"
            cpu_parts.append(f"核心: {cores_str}")
        
        # 系统负载
        if metrics.cpu_load_avg is not None and privacy_level != 'minimal':
            load_str = f"{metrics.cpu_load_avg[0]:.2f}, {metrics.cpu_load_avg[1]:.2f}, {metrics.cpu_load_avg[2]:.2f}"
            cpu_parts.append(f"负载: {load_str}")
        
        if not cpu_parts:
            return ""
            
        cpu_info = " | ".join(cpu_parts)
        
        if plain:
            return f"CPU: {cpu_info}"
        else:
            return f"{self.EMOJI_MAP['cpu']} **CPU**\n   - {cpu_info.replace(' | ', '\n   - ')}"
    
    def _format_memory_info(self, metrics: SystemMetrics, privacy_level: str, plain: bool = False) -> str:
        """格式化内存信息"""
        mem_parts = []
        
        # 物理内存
        if metrics.mem_percent is not None:
            percent_str = f"{metrics.mem_percent:.1f}%"
            mem_parts.append(f"使用率: {percent_str}")
            
            if privacy_level != 'minimal':
                if metrics.mem_used is not None and metrics.mem_total is not None:
                    used_str = self._format_bytes(metrics.mem_used)
                    total_str = self._format_bytes(metrics.mem_total)
                    mem_parts.append(f"已使用: {used_str}/{total_str}")
        
        # 交换内存
        if metrics.swap_percent is not None and privacy_level != 'minimal':
            swap_str = f"{metrics.swap_percent:.1f}%"
            mem_parts.append(f"交换空间: {swap_str}")
        
        if not mem_parts:
            return ""
            
        mem_info = " | ".join(mem_parts)
        
        if plain:
            return f"内存: {mem_info}"
        else:
            return f"{self.EMOJI_MAP['memory']} **内存**\n   - {mem_info.replace(' | ', '\n   - ')}"
    
    def _format_disk_info(self, disks: List[DiskUsage], privacy_level: str, plain: bool = False) -> str:
        """格式化磁盘信息"""
        if not disks:
            return ""
            
        disk_parts = []
        
        for disk in disks:
            if privacy_level == 'minimal':
                disk_info = f"{disk.percent:.1f}%"
            else:
                used_str = self._format_bytes(disk.used)
                total_str = self._format_bytes(disk.total)
                disk_info = f"{disk.percent:.1f}% ({used_str}/{total_str})"
            
            display_name = self._sanitize_display_name(disk.display_path)
            disk_parts.append(f"{display_name}: {disk_info}")
        
        if plain:
            return f"磁盘: {' | '.join(disk_parts)}"
        else:
            disk_lines = [f"   - 💿 {part}" for part in disk_parts]
            return f"{self.EMOJI_MAP['disk']} **磁盘**\n" + "\n".join(disk_lines)
    
    def _format_network_info(self, network: Optional[NetworkStats], privacy_level: str, plain: bool = False) -> str:
        """格式化网络信息"""
        if network is None or privacy_level == 'minimal':
            return ""
            
        sent_str = self._format_bytes(network.bytes_sent)
        recv_str = self._format_bytes(network.bytes_recv)
        
        if plain:
            return f"网络: 上传 {sent_str} | 下载 {recv_str}"
        else:
            return f"{self.EMOJI_MAP['network']} **网络**\n   - 总上传: {sent_str}\n   - 总下载: {recv_str}"
    
    def _format_process_info(self, processes: Optional[ProcessStats], privacy_level: str, plain: bool = False) -> str:
        """格式化进程信息"""
        if processes is None or privacy_level == 'minimal':
            return ""
            
        proc_info = f"总数: {processes.total} | 运行: {processes.running} | 睡眠: {processes.sleeping}"
        
        if plain:
            return f"进程: {proc_info}"
        else:
            return f"{self.EMOJI_MAP['process']} **进程**\n   - {proc_info.replace(' | ', '\n   - ')}"
    
    def _format_timedelta(self, td: datetime.timedelta) -> str:
        """格式化时间差"""
        total_seconds = int(td.total_seconds())
        days, remainder = divmod(total_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days}天")
        if hours > 0:
            parts.append(f"{hours}小时")
        if minutes > 0:
            parts.append(f"{minutes}分")
        if seconds > 0 or not parts:
            parts.append(f"{seconds}秒")
            
        return " ".join(parts)
    
    def _format_bytes(self, byte_count: Optional[Union[int, float]]) -> str:
        """格式化字节大小"""
        if byte_count is None:
            return "N/A"
            
        byte_count = int(byte_count)
        if byte_count == 0:
            return "0B"
            
        power, n = 1024, 0
        while byte_count >= power and n < len(self.BYTE_LABELS) - 1:
            byte_count /= power
            n += 1
            
        if n == 0:
            return f"{byte_count}{self.BYTE_LABELS[n]}"
        else:
            return f"{byte_count:.2f}{self.BYTE_LABELS[n]}"
    
    def _sanitize_display_name(self, name: str) -> str:
        """清理显示名称"""
        # 移除Markdown特殊字符
        escape_chars = ['`', '*', '_', '{', '}', '[', ']', '(', ')', '#', '+', '-', '.', '!', '|']
        for char in escape_chars:
            name = name.replace(char, '')
            
        # 清理换行和多余空格
        name = name.replace('\n', ' ').replace('\r', ' ').strip()
        
        # 长度限制
        if len(name) > 30:
            name = name[:27] + '...'
            
        return name
    
    # JSON格式辅助方法
    def _get_system_info_dict(self, metrics: SystemMetrics) -> Dict[str, Any]:
        return {
            'uptime': self._format_timedelta(metrics.uptime) if metrics.uptime else None,
            'boot_time': metrics.boot_time.isoformat() if metrics.boot_time else None,
            'is_containerized': metrics.is_containerized,
            'platform': metrics.platform_info
        }
    
    def _get_cpu_info_dict(self, metrics: SystemMetrics) -> Dict[str, Any]:
        return {
            'percent': metrics.cpu_percent,
            'temperature': metrics.cpu_temp,
            'frequency': metrics.cpu_freq,
            'cores': metrics.cpu_cores,
            'load_avg': metrics.cpu_load_avg
        }
    
    def _get_memory_info_dict(self, metrics: SystemMetrics) -> Dict[str, Any]:
        return {
            'total': metrics.mem_total,
            'used': metrics.mem_used,
            'free': metrics.mem_free,
            'percent': metrics.mem_percent,
            'swap_total': metrics.swap_total,
            'swap_used': metrics.swap_used,
            'swap_percent': metrics.swap_percent
        }
    
    def _get_disk_info_dict(self, disk: DiskUsage) -> Dict[str, Any]:
        return {
            'display_path': disk.display_path,
            'mount_point': disk.mount_point,
            'total': disk.total,
            'used': disk.used,
            'free': disk.free,
            'percent': disk.percent,
            'fs_type': disk.fs_type
        }
    
    def _get_network_info_dict(self, network: Optional[NetworkStats]) -> Dict[str, Any]:
        if network is None:
            return {}
        return {
            'bytes_sent': network.bytes_sent,
            'bytes_recv': network.bytes_recv,
            'packets_sent': network.packets_sent,
            'packets_recv': network.packets_recv,
            'errors_in': network.errin,
            'errors_out': network.errout,
            'drops_in': network.dropin,
            'drops_out': network.dropout
        }
    
    def _get_process_info_dict(self, processes: Optional[ProcessStats]) -> Dict[str, Any]:
        if processes is None:
            return {}
        return {
            'total': processes.total,
            'running': processes.running,
            'sleeping': processes.sleeping,
            'idle': processes.idle,
            'stopped': processes.stopped,
            'zombie': processes.zombie
        }