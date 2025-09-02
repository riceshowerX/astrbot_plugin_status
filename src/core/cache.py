"""缓存管理模块 - 负责状态数据的缓存管理"""
import asyncio
import time
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from .collector import SystemMetrics

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """缓存条目"""
    data: Any
    timestamp: float
    ttl: int
    
    def is_valid(self) -> bool:
        """检查缓存是否有效"""
        return (time.time() - self.timestamp) < self.ttl

class MetricsCache:
    """指标缓存管理器"""
    
    def __init__(self, default_ttl: int = 10):
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
        
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存数据"""
        async with self._lock:
            entry = self._cache.get(key)
            if entry and entry.is_valid():
                logger.debug("缓存命中: %s", key)
                return entry.data
            return None
            
    async def set(self, key: str, data: Any, ttl: Optional[int] = None) -> None:
        """设置缓存数据"""
        async with self._lock:
            self._cache[key] = CacheEntry(
                data=data,
                timestamp=time.time(),
                ttl=ttl or self.default_ttl
            )
            logger.debug("缓存设置: %s (TTL: %ds)", key, ttl or self.default_ttl)
            
    async def invalidate(self, key: str) -> None:
        """使缓存失效"""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug("缓存失效: %s", key)
                
    async def clear(self) -> None:
        """清空所有缓存"""
        async with self._lock:
            self._cache.clear()
            logger.debug("缓存已清空")
            
    async def cleanup(self) -> None:
        """清理过期缓存"""
        async with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, entry in self._cache.items()
                if not entry.is_valid()
            ]
            
            for key in expired_keys:
                del self._cache[key]
                
            if expired_keys:
                logger.debug("清理了 %d 个过期缓存", len(expired_keys))
                
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        async with self._lock:
            current_time = time.time()
            valid_entries = 0
            total_size = 0
            
            for entry in self._cache.values():
                if entry.is_valid():
                    valid_entries += 1
                    total_size += self._estimate_size(entry.data)
                    
            return {
                'total_entries': len(self._cache),
                'valid_entries': valid_entries,
                'memory_usage_bytes': total_size,
                'default_ttl': self.default_ttl
            }
            
    def _estimate_size(self, data: Any) -> int:
        """估算数据大小"""
        if isinstance(data, str):
            return len(data.encode('utf-8'))
        elif isinstance(data, (int, float, bool)):
            return 8
        elif isinstance(data, dict):
            return sum(
                self._estimate_size(k) + self._estimate_size(v)
                for k, v in data.items()
            )
        elif isinstance(data, list):
            return sum(self._estimate_size(item) for item in data)
        else:
            return 100  # 默认估算大小
            
    async def periodic_cleanup(self, interval: int = 60) -> None:
        """定期清理缓存"""
        while True:
            try:
                await asyncio.sleep(interval)
                await self.cleanup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("缓存清理失败: %s", e)

class SmartCacheManager:
    """智能缓存管理器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.metrics_cache = MetricsCache(config.get('cache_duration', 10))
        self._cleanup_task: Optional[asyncio.Task] = None
        
    async def initialize(self) -> None:
        """初始化缓存管理器"""
        # 启动定期清理任务
        self._cleanup_task = asyncio.create_task(
            self.metrics_cache.periodic_cleanup(60)
        )
        logger.info("智能缓存管理器已初始化")
        
    async def shutdown(self) -> None:
        """关闭缓存管理器"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("智能缓存管理器已关闭")
        
    async def get_cached_metrics(self) -> Optional[str]:
        """获取缓存的指标数据"""
        return await self.metrics_cache.get('metrics')
        
    async def cache_metrics(self, metrics_text: str) -> None:
        """缓存指标数据"""
        await self.metrics_cache.set('metrics', metrics_text)
        
    async def invalidate_metrics_cache(self) -> None:
        """使指标缓存失效"""
        await self.metrics_cache.invalidate('metrics')
        
    def should_use_cache(self, force_refresh: bool = False) -> bool:
        """判断是否应该使用缓存"""
        if force_refresh:
            return False
            
        cache_duration = self.config.get('cache_duration', 10)
        if cache_duration <= 0:
            return False
            
        # 可以根据系统负载动态调整缓存策略
        # 例如：在高负载时延长缓存时间
        return True
        
    async def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return self.metrics_cache.get_stats()

# 全局缓存实例
_global_cache: Optional[SmartCacheManager] = None

async def get_global_cache(config: Dict[str, Any]) -> SmartCacheManager:
    """获取全局缓存实例"""
    global _global_cache
    if _global_cache is None:
        _global_cache = SmartCacheManager(config)
        await _global_cache.initialize()
    return _global_cache

async def shutdown_global_cache() -> None:
    """关闭全局缓存"""
    global _global_cache
    if _global_cache is not None:
        await _global_cache.shutdown()
        _global_cache = None