# main.py 

import psutil
import datetime
import platform
from typing import Dict, Any

# ===================================================================
# 核心修改：遵循官方文档的导入规范
# ===================================================================
from astrbot.api.star import Star, register, Context
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger # 使用官方推荐的 logger
# ===================================================================


# --- 辅助函数 (这部分是纯Python，无需改动) ---

def format_bytes(byte_count: int) -> str:
    """将字节数格式化为最合适的单位 (GB, MB, KB)"""
    if byte_count is None: return "N/A"
    power = 1024; n = 0
    power_labels = {0: ' B', 1: ' KB', 2: ' MB', 3: ' GB', 4: ' TB'}
    while byte_count >= power and n < len(power_labels) - 1:
        byte_count /= power
        n += 1
    return f"{byte_count:.2f}{power_labels[n]}"

def get_system_stats() -> Dict[str, Any]:
    """获取所有系统状态信息，并将其打包成一个字典。"""
    stats = {}
    stats['cpu_percent'] = psutil.cpu_percent(interval=1)
    stats['cpu_temp'] = None
    if platform.system() == "Linux":
        try:
            temps = psutil.sensors_temperatures()
            for key in ['coretemp', 'k10temp', 'cpu_thermal']:
                if key in temps and temps[key]:
                    stats['cpu_temp'] = temps[key][0].current
                    break
        except Exception: pass
    memory = psutil.virtual_memory()
    stats.update({'mem_total': memory.total, 'mem_used': memory.used, 'mem_percent': memory.percent})
    disk_path = 'C:\\' if platform.system() == "Windows" else '/'
    try:
        disk = psutil.disk_usage(disk_path)
        stats.update({'disk_path': disk_path, 'disk_total': disk.total, 'disk_used': disk.used, 'disk_percent': disk.percent})
    except FileNotFoundError:
        stats.update({'disk_path': disk_path, 'disk_total': 0, 'disk_used': 0, 'disk_percent': 0})
    boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
    stats['uptime'] = datetime.datetime.now() - boot_time
    net_io = psutil.net_io_counters()
    stats.update({'net_sent': net_io.bytes_sent, 'net_recv': net_io.bytes_recv})
    return stats

# --- 插件主类 ---

# 使用文档推荐的元数据格式，这些信息会被 metadata.yaml 覆盖
@register(
    name="astrabot_plugin_status", 
    author="riceshowerx", 
    desc="查询服务器的实时状态", 
    version="1.3.0",
    repo="https://github.com/riceshowerX/astrbot_plugin_status"
)
class ServerStatusPlugin(Star):
    # 遵循文档，__init__ 接收 Context 对象
    def __init__(self, context: Context):
        super().__init__(context)
        self.context = context # 保存 context 以便后续使用
        logger.info("服务器状态插件已成功加载。")

    def format_status_message(self, stats: Dict[str, Any]) -> str:
        """将收集到的状态字典格式化为对用户友好的消息字符串。"""
        uptime = stats.get('uptime', datetime.timedelta(0))
        days, remainder = divmod(uptime.total_seconds(), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, _ = divmod(remainder, 60)
        uptime_str = f"{int(days)}天 {int(hours)}小时 {int(minutes)}分钟"

        lines = [
            "💻 **服务器实时状态** 💻", "--------------------",
            f"⏱️ **已稳定运行**: {uptime_str}", "--------------------",
            "🖥️ **CPU**", f"   - **使用率**: {stats.get('cpu_percent', 0):.1f}%"
        ]
        
        if stats.get('cpu_temp'):
            lines.append(f"   - **核心温度**: {stats['cpu_temp']:.1f}°C")

        lines.extend([
            "--------------------", "💾 **内存**",
            f"   - **使用率**: {stats.get('mem_percent', 0):.1f}%",
            f"   - **已使用**: {format_bytes(stats.get('mem_used', 0))} / {format_bytes(stats.get('mem_total', 0))}",
            "--------------------", f"💿 **磁盘 ({stats.get('disk_path', '/')})**",
            f"   - **使用率**: {stats.get('disk_percent', 0):.1f}%",
            f"   - **已使用**: {format_bytes(stats.get('disk_used', 0))} / {format_bytes(stats.get('disk_total', 0))}",
            "--------------------", "🌐 **网络I/O (自启动)**",
            f"   - **总上传**: {format_bytes(stats.get('net_sent', 0))}",
            f"   - **总下载**: {format_bytes(stats.get('net_recv', 0))}"
        ])
        
        return "\n".join(lines)

    # 核心修改：使用 @filter.command() 注册指令，并提供别名
    @filter.command("status", alias={"服务器状态", "状态", "zt", "s"})
    async def handle_server_status(self, event: AstrMessageEvent):
        '''查询并显示当前服务器的详细运行状态'''
        try:
            # 在异步环境中执行阻塞操作是好习惯
            system_stats = await self.context.loop.run_in_executor(None, get_system_stats)
            status_message_str = self.format_status_message(system_stats)
            
            # 核心修改：使用 yield 和 event.plain_result() 发送消息
            yield event.plain_result(status_message_str)

        except Exception as e:
            logger.error(f"获取服务器状态时发生未知错误: {e}")
            yield event.plain_result(f"抱歉，获取服务器状态时出现错误。详情请查看日志。")