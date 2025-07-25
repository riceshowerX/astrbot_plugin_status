# main.py (V1.6.0 回归文本输出的终极简化版)

import psutil
import datetime
import platform
import asyncio
from typing import Dict, Any, Optional

# 导入 AstrBot 官方 API
from astrbot.api.star import Star, register, Context
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger, AstrBotConfig

# --- 插件主类 ---

@register(
    name="astrabot_plugin_status", 
    author="riceshowerx", 
    desc="以文本形式查询服务器的实时状态 (快速稳定版)", 
    version="1.6.0", # 版本号提升
    repo="https://github.com/riceshowerX/astrbot_plugin_status"
)
class ServerStatusPlugin(Star):
    def __init__(self, context: Context, config: Optional[AstrBotConfig] = None):
        super().__init__(context)
        self.context = context
        self.config = config if config is not None else AstrBotConfig({})
        try:
            self.boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        except Exception as e:
            logger.error(f"获取系统启动时间失败: {e}"); self.boot_time = datetime.datetime.now()
        
        logger.info("服务器状态插件(v1.6.0)已成功加载，使用纯文本输出。")

    def get_system_stats(self) -> Dict[str, Any]:
        """获取原始系统状态数据，包含详细的错误处理。"""
        stats = {'disks': []}
        try:
            stats['cpu_percent'] = psutil.cpu_percent(interval=1)
        except Exception as e:
            logger.warning(f"获取 CPU 使用率失败: {e}"); stats['cpu_percent'] = 0
        stats['cpu_temp'] = None
        if self.config.get("show_temp", True) and platform.system() == "Linux":
            try:
                temps = psutil.sensors_temperatures()
                for key in ['coretemp', 'k10temp', 'cpu_thermal']:
                    if key in temps and temps[key]: stats['cpu_temp'] = temps[key][0].current; break
            except Exception as e:
                logger.info(f"未能获取 CPU 温度: {e}")
        try:
            mem = psutil.virtual_memory()
            stats.update({'mem_total': mem.total, 'mem_used': mem.used, 'mem_percent': mem.percent})
        except Exception as e:
            logger.warning(f"获取内存信息失败: {e}")
        paths_to_check = self.config.get('disk_paths', [])
        if not paths_to_check:
            try:
                paths_to_check = [p.mountpoint for p in psutil.disk_partitions(all=False)]
            except Exception as e:
                logger.warning(f"自动发现磁盘分区失败: {e}"); paths_to_check = ['C:\\' if platform.system() == "Windows" else '/']
        for path in paths_to_check:
            try:
                usage = psutil.disk_usage(path)
                stats['disks'].append({'path': path, 'total': usage.total, 'used': usage.used, 'percent': usage.percent})
            except Exception as e:
                logger.warning(f"获取磁盘路径 '{path}' 信息失败: {e}")
        try:
            net = psutil.net_io_counters()
            stats.update({'net_sent': net.bytes_sent, 'net_recv': net.bytes_recv})
        except Exception as e:
            logger.warning(f"获取网络IO信息失败: {e}")
        return stats

    def format_text_message(self, raw_stats: Dict[str, Any]) -> str:
        """将原始数据格式化为对用户友好的文本消息。"""
        # --- 数据格式化 ---
        uptime = datetime.datetime.now() - self.boot_time
        days, rem = divmod(uptime.total_seconds(), 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        uptime_str = f"{int(days)}天 {int(hours)}小时 {int(minutes)}分钟"

        cpu_percent_str = f"{raw_stats.get('cpu_percent', 0):.1f}%"
        cpu_temp_str = f"({raw_stats['cpu_temp']:.1f}°C)" if raw_stats.get('cpu_temp') else ""

        mem_percent_str = f"{raw_stats.get('mem_percent', 0):.1f}%"
        mem_used_str = self._format_bytes(raw_stats.get('mem_used', 0))
        mem_total_str = self._format_bytes(raw_stats.get('mem_total', 0))

        net_sent_str = self._format_bytes(raw_stats.get('net_sent', 0))
        net_recv_str = self._format_bytes(raw_stats.get('net_recv', 0))

        # --- 字符串拼接 ---
        lines = [
            "💻 **服务器实时状态**",
            "--------------------",
            f"⏱️ **已稳定运行**: {uptime_str}",
            "--------------------",
            f"🖥️ **CPU** {cpu_temp_str}",
            f"   - **使用率**: {cpu_percent_str}",
            "--------------------",
            f"💾 **内存**",
            f"   - **使用率**: {mem_percent_str}",
            f"   - **已使用**: {mem_used_str} / {mem_total_str}",
        ]
        
        for disk in raw_stats.get('disks', []):
            lines.extend([
                "--------------------",
                f"💿 **磁盘 ({disk['path']})**",
                f"   - **使用率**: {disk.get('percent', 0):.1f}%",
                f"   - **已使用**: {self._format_bytes(disk.get('used', 0))} / {self._format_bytes(disk.get('total', 0))}"
            ])
        
        lines.extend([
            "--------------------",
            "🌐 **网络I/O (自启动)**",
            f"   - **总上传**: {net_sent_str}",
            f"   - **总下载**: {net_recv_str}"
        ])
        
        return "\n".join(lines)

    @filter.command("status", alias={"服务器状态", "状态", "zt", "s"})
    async def handle_server_status(self, event: AstrMessageEvent):
        '''查询并显示当前服务器的详细运行状态 (文本版)'''
        try:
            await event.send(event.plain_result("正在获取服务器状态，请稍候..."))
            
            loop = asyncio.get_running_loop()
            raw_stats = await loop.run_in_executor(None, self.get_system_stats)
            
            # 直接获取数据并格式化为文本
            text_message = self.format_text_message(raw_stats)
            
            # 发送最终的纯文本消息
            await event.send(event.plain_result(text_message))

        except Exception as e:
            logger.error(f"处理 status 指令时发生未知错误: {e}", exc_info=True)
            await event.send(event.plain_result(f"抱歉，获取状态时出现错误，请联系管理员。"))
    
    @staticmethod
    def _format_bytes(byte_count: int) -> str:
        if byte_count is None: return "N/A"
        power = 1024; n = 0
        power_labels = {0: ' B', 1: ' KB', 2: ' MB', 3: ' GB', 4: ' TB'}
        while byte_count >= power and n < len(power_labels) - 1: byte_count /= power; n += 1
        return f"{byte_count:.2f}{power_labels[n]}"