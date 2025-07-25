# main.py

import psutil
import datetime
import platform
from typing import Dict, Any
from astrbot.api.star import Star, register, on_command
from astrbot.api.message import Message
from astrbot.core.platform.astr_message_event import AstrMessageEvent

# --- 辅助函数 ---

def format_bytes(byte_count: int) -> str:
    """将字节数格式化为最合适的单位 (GB, MB, KB)"""
    if byte_count is None:
        return "N/A"
    power = 1024
    n = 0
    power_labels = {0: ' B', 1: ' KB', 2: ' MB', 3: ' GB', 4: ' TB'}
    # 避免 byte_count 为 0 时进入循环
    while byte_count >= power and n < len(power_labels) -1:
        byte_count /= power
        n += 1
    return f"{byte_count:.2f}{power_labels[n]}"

# --- 数据获取模块 ---

def get_system_stats() -> Dict[str, Any]:
    """
    获取所有系统状态信息，并将其打包成一个字典。
    包含错误处理，确保在任何环境下都能返回数据。
    """
    stats = {}

    # CPU信息
    stats['cpu_percent'] = psutil.cpu_percent(interval=1)
    
    # CPU温度 (可能在某些系统上不可用)
    stats['cpu_temp'] = None
    if platform.system() == "Linux":
        try:
            temps = psutil.sensors_temperatures()
            # 常见的温度传感器键
            for key in ['coretemp', 'k10temp', 'cpu_thermal']:
                if key in temps and temps[key]:
                    stats['cpu_temp'] = temps[key][0].current
                    break
        except (AttributeError, KeyError, IndexError):
            # 忽略获取温度时可能发生的任何错误
            pass

    # 内存信息
    memory = psutil.virtual_memory()
    stats['mem_total'] = memory.total
    stats['mem_used'] = memory.used
    stats['mem_percent'] = memory.percent

    # 磁盘信息 (自动检测Windows或Linux的根目录)
    disk_path = 'C:\\' if platform.system() == "Windows" else '/'
    try:
        disk = psutil.disk_usage(disk_path)
        stats['disk_path'] = disk_path
        stats['disk_total'] = disk.total
        stats['disk_used'] = disk.used
        stats['disk_percent'] = disk.percent
    except FileNotFoundError:
        stats.update({'disk_path': disk_path, 'disk_total': 0, 'disk_used': 0, 'disk_percent': 0})

    # 系统运行时间
    boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
    stats['uptime'] = datetime.datetime.now() - boot_time

    # 网络IO信息
    net_io = psutil.net_io_counters()
    stats['net_sent'] = net_io.bytes_sent
    stats['net_recv'] = net_io.bytes_recv

    return stats

# --- 插件主类 ---

# @register 装饰器用于向 AstrBot 核心注册插件。
# 虽然大部分元数据在 config.yaml 中定义，但这里的注册信息作为代码内的快速参考。
@register(
    name="astrabot_plugin_status", 
    display_name="服务器状态", 
    author="riceshowerx", 
    version="v1.3", 
    brief="查询服务器的实时状态"
)
class ServerStatusPlugin(Star):
    """
    一个用于查询和显示服务器运行状态的 AstrBot 插件。
    
    Author: riceshowerx
    Version: v1.3
    Repo: https://github.com/riceshowerX/astrbot_plugin_status
    """
    def __init__(self, bot, **kwargs):
        super().__init__(bot, **kwargs)
        self.log("服务器状态插件已加载。")

    def format_status_message(self, stats: Dict[str, Any]) -> str:
        """将收集到的状态字典格式化为对用户友好的消息字符串。"""
        
        # 格式化运行时间
        uptime = stats.get('uptime', datetime.timedelta(0))
        days, remainder = divmod(uptime.total_seconds(), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, _ = divmod(remainder, 60)
        uptime_str = f"{int(days)}天 {int(hours)}小时 {int(minutes)}分钟"

        # 使用列表构建消息，更清晰高效
        lines = [
            "💻 **服务器实时状态** 💻",
            "--------------------",
            f"⏱️ **已稳定运行**: {uptime_str}",
            "--------------------",
            "🖥️ **CPU**",
            f"   - **使用率**: {stats.get('cpu_percent', 0):.1f}%",
        ]
        
        # 仅当获取到温度时才显示
        if stats.get('cpu_temp'):
            lines.append(f"   - **核心温度**: {stats['cpu_temp']:.1f}°C")

        lines.extend([
            "--------------------",
            "💾 **内存**",
            f"   - **使用率**: {stats.get('mem_percent', 0):.1f}%",
            f"   - **已使用**: {format_bytes(stats.get('mem_used', 0))} / {format_bytes(stats.get('mem_total', 0))}",
            "--------------------",
            f"💿 **磁盘 ({stats.get('disk_path', '/')})**",
            f"   - **使用率**: {stats.get('disk_percent', 0):.1f}%",
            f"   - **已使用**: {format_bytes(stats.get('disk_used', 0))} / {format_bytes(stats.get('disk_total', 0))}",
            "--------------------",
            "🌐 **网络I/O (自启动)**",
            f"   - **总上传**: {format_bytes(stats.get('net_sent', 0))}",
            f"   - **总下载**: {format_bytes(stats.get('net_recv', 0))}"
        ])
        
        return "\n".join(lines)

    @on_command("status", "服务器状态", "state", aliases={"状态", "zt", "s"}, help="显示当前服务器的详细运行状态")
    async def handle_server_status(self, event: Event):
        """处理用户的状态查询命令，先发送提示信息，然后获取并格式化数据。"""
        # 异步任务，避免阻塞
        try:
            # 1. 获取数据
            system_stats = await self.bot.loop.run_in_executor(None, get_system_stats)
            # 2. 格式化消息
            status_message = self.format_status_message(system_stats)
            # 3. 发送最终消息
            await self.bot.send(event, Message(status_message))
        except Exception as e:
            self.log_error(f"获取服务器状态时发生未知错误: {e}")
            await self.bot.send(event, Message(f"抱歉，获取服务器状态时出现错误。详情请查看日志。"))