"""配置管理模块 - 负责配置验证和解析"""
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class PluginConfig:
    """插件配置数据类"""
    # 基本配置
    privacy_level: str = "full"
    cache_duration: int = 10
    collect_timeout: int = 25
    show_temp: bool = True
    output_format: str = "markdown"
    
    # 磁盘配置
    disk_config: List[Dict[str, str]] = field(default_factory=list)
    auto_discover_disks: bool = True
    max_disk_count: int = 10
    
    # 高级配置
    enable_network_stats: bool = True
    enable_process_stats: bool = True
    enable_system_info: bool = True
    enable_detailed_errors: bool = True
    
    # 性能配置
    max_thread_workers: int = 3
    collection_interval: int = 30
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'PluginConfig':
        """从字典创建配置对象"""
        config = cls()
        
        # 基本配置
        if 'privacy_level' in config_dict:
            config.privacy_level = cls._validate_privacy_level(config_dict['privacy_level'])
        
        if 'cache_duration' in config_dict:
            config.cache_duration = cls._validate_int(config_dict['cache_duration'], 0, 3600, 10)
        
        if 'collect_timeout' in config_dict:
            config.collect_timeout = cls._validate_int(config_dict['collect_timeout'], 5, 120, 25)
        
        if 'show_temp' in config_dict:
            config.show_temp = bool(config_dict['show_temp'])
        
        if 'output_format' in config_dict:
            config.output_format = cls._validate_output_format(config_dict['output_format'])
        
        # 磁盘配置
        if 'disk_paths' in config_dict:
            config.disk_config = cls._parse_disk_config(config_dict['disk_paths'])
        
        if 'auto_discover_disks' in config_dict:
            config.auto_discover_disks = bool(config_dict['auto_discover_disks'])
        
        if 'max_disk_count' in config_dict:
            config.max_disk_count = cls._validate_int(config_dict['max_disk_count'], 1, 50, 10)
        
        # 高级配置
        if 'enable_network_stats' in config_dict:
            config.enable_network_stats = bool(config_dict['enable_network_stats'])
        
        if 'enable_process_stats' in config_dict:
            config.enable_process_stats = bool(config_dict['enable_process_stats'])
        
        if 'enable_system_info' in config_dict:
            config.enable_system_info = bool(config_dict['enable_system_info'])
        
        if 'enable_detailed_errors' in config_dict:
            config.enable_detailed_errors = bool(config_dict['enable_detailed_errors'])
        
        # 性能配置
        if 'max_thread_workers' in config_dict:
            config.max_thread_workers = cls._validate_int(config_dict['max_thread_workers'], 1, 10, 3)
        
        if 'collection_interval' in config_dict:
            config.collection_interval = cls._validate_int(config_dict['collection_interval'], 5, 300, 30)
        
        return config
    
    @staticmethod
    def _validate_privacy_level(level: Any) -> str:
        """验证隐私级别"""
        if isinstance(level, str):
            level = level.lower().strip()
            if level in ['full', 'minimal']:
                return level
        return "full"
    
    @staticmethod
    def _validate_output_format(format_str: Any) -> str:
        """验证输出格式"""
        if isinstance(format_str, str):
            format_str = format_str.lower().strip()
            if format_str in ['markdown', 'plain', 'json']:
                return format_str
        return "markdown"
    
    @staticmethod
    def _validate_int(value: Any, min_val: int, max_val: int, default: int) -> int:
        """验证整数值"""
        try:
            num = int(value)
            if min_val <= num <= max_val:
                return num
        except (ValueError, TypeError):
            pass
        return default
    
    @staticmethod
    def _parse_disk_config(disk_config: Any) -> List[Dict[str, str]]:
        """解析磁盘配置"""
        result = []
        
        if not isinstance(disk_config, list):
            return result
        
        for item in disk_config:
            if isinstance(item, str):
                # 简单字符串路径
                if ConfigValidator.is_safe_disk_path(item):
                    result.append({'path': item, 'display': item})
                else:
                    logger.warning("跳过不安全的磁盘路径: %s", item)
            
            elif isinstance(item, dict):
                # 带别名的磁盘配置
                path = item.get('path')
                display = item.get('display', path)
                
                if path and ConfigValidator.is_safe_disk_path(path):
                    result.append({'path': path, 'display': display})
                else:
                    logger.warning("跳过无效的磁盘配置: %s", item)
        
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'privacy_level': self.privacy_level,
            'cache_duration': self.cache_duration,
            'collect_timeout': self.collect_timeout,
            'show_temp': self.show_temp,
            'output_format': self.output_format,
            'disk_config': self.disk_config,
            'auto_discover_disks': self.auto_discover_disks,
            'max_disk_count': self.max_disk_count,
            'enable_network_stats': self.enable_network_stats,
            'enable_process_stats': self.enable_process_stats,
            'enable_system_info': self.enable_system_info,
            'enable_detailed_errors': self.enable_detailed_errors,
            'max_thread_workers': self.max_thread_workers,
            'collection_interval': self.collection_interval
        }

class ConfigValidator:
    """配置验证器"""
    
    @staticmethod
    def is_safe_disk_path(path: Any) -> bool:
        """检查磁盘路径是否安全"""
        import os
        import platform
        
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
    
    @staticmethod
    def validate_config(config_dict: Dict[str, Any]) -> List[str]:
        """验证配置并返回错误列表"""
        errors = []
        
        # 验证隐私级别
        privacy_level = config_dict.get('privacy_level', 'full')
        if privacy_level not in ['full', 'minimal']:
            errors.append(f"无效的隐私级别: {privacy_level}")
        
        # 验证缓存时间
        cache_duration = config_dict.get('cache_duration', 10)
        if not isinstance(cache_duration, int) or not (0 <= cache_duration <= 3600):
            errors.append(f"无效的缓存时间: {cache_duration}")
        
        # 验证采集超时
        collect_timeout = config_dict.get('collect_timeout', 25)
        if not isinstance(collect_timeout, int) or not (5 <= collect_timeout <= 120):
            errors.append(f"无效的采集超时: {collect_timeout}")
        
        # 验证磁盘配置
        disk_paths = config_dict.get('disk_paths', [])
        if not isinstance(disk_paths, list):
            errors.append("磁盘路径配置必须是列表")
        else:
            for item in disk_paths:
                if isinstance(item, str):
                    if not ConfigValidator.is_safe_disk_path(item):
                        errors.append(f"不安全的磁盘路径: {item}")
                elif isinstance(item, dict):
                    path = item.get('path')
                    if not path or not ConfigValidator.is_safe_disk_path(path):
                        errors.append(f"无效的磁盘配置: {item}")
                else:
                    errors.append(f"无效的磁盘配置项类型: {type(item)}")
        
        return errors

def get_default_config() -> Dict[str, Any]:
    """获取默认配置"""
    return {
        'privacy_level': 'full',
        'cache_duration': 10,
        'collect_timeout': 25,
        'show_temp': True,
        'output_format': 'markdown',
        'disk_paths': [],
        'auto_discover_disks': True,
        'max_disk_count': 10,
        'enable_network_stats': True,
        'enable_process_stats': True,
        'enable_system_info': True,
        'enable_detailed_errors': True,
        'max_thread_workers': 3,
        'collection_interval': 30
    }