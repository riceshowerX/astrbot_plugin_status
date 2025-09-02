"""AstrBot服务器状态插件主模块"""
import asyncio
import time
import logging
from typing import Dict, Any, Optional

from astrbot.api.star import Star, register, Context
from astrbot.api.event import filter as event_filter, AstrMessageEvent
from astrbot.api import logger as astr_logger, AstrBotConfig

from .core.config import PluginConfig, ConfigValidator
from .core.collector import MetricsCollector
from .core.formatter import MetricsFormatter
from .core.cache import get_global_cache, shutdown_global_cache

# 配置插件日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@register(
    name="astrbot_plugin_status",
    author="riceshowerx & AstrBot Assistant",
    desc="[v3.0] 工业级服务器状态监控插件 - 支持多格式输出和智能缓存",
    version="3.0.0",
    repo="https://github.com/riceshowerX/astrbot_plugin_status"
)
class ServerStatusPlugin(Star):
    """服务器状态监控插件"""
    
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.context = context
        
        # 解析和验证配置
        self.plugin_config = self._validate_and_parse_config(config)
        self.collector: Optional[MetricsCollector] = None
        self.formatter: Optional[MetricsFormatter] = None
        self.cache_manager = None
        self._lock = asyncio.Lock()
        
        # 初始化状态
        self.is_initialized = False
        self.last_collection_time = 0
        self.collection_count = 0
        
    async def initialize(self) -> None:
        """异步初始化插件"""
        try:
            # 初始化组件
            self.collector = MetricsCollector(self.plugin_config.to_dict())
            self.formatter = MetricsFormatter(self.plugin_config.to_dict())
            self.cache_manager = await get_global_cache(self.plugin_config.to_dict())
            
            # 记录初始化信息
            self._log_startup_info()
            
            self.is_initialized = True
            logger.info("✅ 服务器状态插件初始化成功")
            
        except Exception as e:
            logger.error("❌ 插件初始化失败: %s", e, exc_info=True)
            self.is_initialized = False
            raise
    
    async def shutdown(self) -> None:
        """关闭插件"""
        if self.collector:
            self.collector.close()
        
        if self.cache_manager:
            await shutdown_global_cache()
            
        logger.info("服务器状态插件已关闭")
    
    def _validate_and_parse_config(self, config: AstrBotConfig) -> PluginConfig:
        """验证和解析配置"""
        try:
            # 验证配置
            config_dict = dict(config)
            errors = ConfigValidator.validate_config(config_dict)
            
            if errors:
                for error in errors:
                    astr_logger.warning("[StatusPlugin] 配置验证警告: %s", error)
            
            # 创建配置对象
            return PluginConfig.from_dict(config_dict)
            
        except Exception as e:
            astr_logger.error("[StatusPlugin] 配置解析错误: %s", e)
            # 返回默认配置
            return PluginConfig()
    
    def _log_startup_info(self) -> None:
        """记录启动信息"""
        config = self.plugin_config
        
        astr_logger.info("=" * 60)
        astr_logger.info("[StatusPlugin] 🚀 服务器状态插件 v3.0 初始化")
        astr_logger.info("[StatusPlugin] 📋 配置摘要:")
        astr_logger.info("[StatusPlugin]   - 隐私级别: %s", config.privacy_level)
        astr_logger.info("[StatusPlugin]   - 缓存时间: %ds", config.cache_duration)
        astr_logger.info("[StatusPlugin]   - 采集超时: %ds", config.collect_timeout)
        astr_logger.info("[StatusPlugin]   - 输出格式: %s", config.output_format)
        astr_logger.info("[StatusPlugin]   - 磁盘监控: %d个配置 + 自动发现", 
                        len(config.disk_config))
        
        # 安全警告
        astr_logger.warning("\n" + "!" * 60)
        astr_logger.warning("[StatusPlugin] 🔒 安全警告:")
        astr_logger.warning("[StatusPlugin] 1. 确保status命令有严格的访问控制!")
        astr_logger.warning("[StatusPlugin] 2. 在生产环境固定psutil版本!")
        astr_logger.warning("[StatusPlugin] 3. 定期检查日志和监控!")
        astr_logger.warning("!" * 60)
        astr_logger.info("=" * 60)
    
    @event_filter.command("status", alias={"服务器状态", "状态", "zt", "s", "sysinfo"})
    async def handle_server_status(self, event: AstrMessageEvent):
        """处理服务器状态查询"""
        if not self.is_initialized:
            yield event.plain_result("❌ 状态插件未正确初始化，请联系管理员检查日志。")
            return
        
        # 检查是否强制刷新
        force_refresh = self._should_force_refresh(event.plain_text)
        
        # 尝试使用缓存
        if not force_refresh and self.cache_manager.should_use_cache():
            cached_result = await self.cache_manager.get_cached_metrics()
            if cached_result:
                yield event.plain_result(cached_result)
                return
        
        # 显示采集提示
        if not force_refresh:
            yield event.plain_result("🔄 正在采集服务器状态，请稍候...")
        
        try:
            # 采集系统指标
            metrics = await self._collect_metrics_with_timeout()
            
            # 格式化输出
            formatted_text = self.formatter.format(metrics)
            
            # 缓存成功的结果
            if not metrics.errors:
                await self.cache_manager.cache_metrics(formatted_text)
            
            yield event.plain_result(formatted_text)
            
        except asyncio.TimeoutError:
            error_msg = f"⏰ 数据采集超时 ({self.plugin_config.collect_timeout}s)，请稍后重试或联系管理员。"
            logger.error("数据采集超时")
            yield event.plain_result(error_msg)
            
        except Exception as e:
            error_msg = "❌ 处理状态请求时出现未知错误，请联系管理员。"
            logger.error("状态处理错误: %s", e, exc_info=True)
            yield event.plain_result(error_msg)
    
    async def _collect_metrics_with_timeout(self) -> Any:
        """带超时的指标采集"""
        return await asyncio.wait_for(
            self.collector.collect_metrics(),
            timeout=self.plugin_config.collect_timeout
        )
    
    def _should_force_refresh(self, message_text: str) -> bool:
        """判断是否强制刷新缓存"""
        refresh_keywords = ["刷新", "强制", "fresh", "force", "reload"]
        message_lower = message_text.lower()
        
        return any(keyword in message_lower for keyword in refresh_keywords)
    
    @event_filter.command("status_help", alias={"状态帮助", "status help", "帮助"})
    async def handle_help(self, event: AstrMessageEvent):
        """显示帮助信息"""
        help_text = """📖 **服务器状态插件帮助**

**命令别名:**
- `/status` / `状态` / `zt` / `s` / `sysinfo`

**功能特性:**
- ✅ 实时系统监控 (CPU/内存/磁盘/网络)
- ✅ 多格式输出 (Markdown/纯文本/JSON)
- ✅ 智能缓存机制
- ✅ 容器环境支持
- ✅ 隐私保护模式

**高级用法:**
- 添加 `刷新` 或 `force` 到消息中强制重新采集
- 配置隐私级别保护敏感信息

**配置选项:**
- 隐私级别 (full/minimal)
- 缓存时间 (0-3600秒)
- 磁盘路径监控
- 输出格式选择

需要更多帮助？请查看项目文档。"""
        
        yield event.plain_result(help_text)
    
    @event_filter.command("status_stats", alias={"状态统计", "stats"})
    async def handle_stats(self, event: AstrMessageEvent):
        """显示插件统计信息"""
        if not self.is_initialized:
            yield event.plain_result("❌ 插件未初始化")
            return
        
        stats = await self.cache_manager.get_cache_stats()
        uptime = time.time() - self.last_collection_time if self.last_collection_time > 0 else 0
        
        stats_text = f"""📊 **插件运行统计**

**采集统计:**
- 总采集次数: {self.collection_count}
- 运行时间: {self._format_seconds(uptime)}

**缓存统计:**
- 缓存条目: {stats['valid_entries']}/{stats['total_entries']}
- 内存使用: {self._format_bytes(stats['memory_usage_bytes'])}
- 默认TTL: {stats['default_ttl']}秒

**系统状态:**
- 插件版本: 3.0.0
- 初始化状态: ✅ 正常
- 最后采集: {self._format_timestamp(self.last_collection_time)}"""
        
        yield event.plain_result(stats_text)
    
    def _format_seconds(self, seconds: float) -> str:
        """格式化秒数"""
        if seconds <= 0:
            return "0秒"
        
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        parts = []
        if hours > 0:
            parts.append(f"{int(hours)}小时")
        if minutes > 0:
            parts.append(f"{int(minutes)}分")
        if seconds > 0 or not parts:
            parts.append(f"{int(seconds)}秒")
            
        return "".join(parts)
    
    def _format_bytes(self, bytes_count: int) -> str:
        """格式化字节大小"""
        if bytes_count == 0:
            return "0B"
            
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        power, n = 1024, 0
        
        while bytes_count >= power and n < len(units) - 1:
            bytes_count /= power
            n += 1
            
        if n == 0:
            return f"{bytes_count}{units[n]}"
        else:
            return f"{bytes_count:.2f}{units[n]}"
    
    def _format_timestamp(self, timestamp: float) -> str:
        """格式化时间戳"""
        if timestamp <= 0:
            return "从未采集"
            
        from datetime import datetime
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

# 插件生命周期管理
async def plugin_initialize():
    """插件初始化钩子"""
    pass

async def plugin_shutdown():
    """插件关闭钩子"""
    await shutdown_global_cache()