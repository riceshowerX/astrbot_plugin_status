# main.py (V1.4.1 修正 config 初始化错误)
import psutil, datetime, platform, asyncio
from typing import Dict, Any, Optional
from astrbot.api.star import Star, register, Context
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger, AstrBotConfig

@register(name="astrabot_plugin_status", author="riceshowerx", desc="以图片形式查询服务器的实时状态", version="1.4.1", repo="https://github.com/riceshowerX/astrbot_plugin_status")
class ServerStatusPlugin(Star):
    def __init__(self, context: Context, config: Optional[AstrBotConfig] = None):
        super().__init__(context)
        self.context = context
        self.config = config if config is not None else AstrBotConfig({})
        self.boot_time = datetime.datetime.now()
        try:
            self.boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        except Exception as e:
            logger.error(f"获取系统启动时间失败: {e}")
        logger.info("服务器状态插件(v1.4.1)已成功加载。")
    def get_system_stats(self) -> Dict[str, Any]:
        stats = {'disks': []};
        try: stats['cpu_percent'] = psutil.cpu_percent(interval=1)
        except Exception as e: logger.warning(f"获取 CPU 使用率失败: {e}"); stats['cpu_percent'] = 0
        stats['cpu_temp'] = None
        if self.config.get("show_temp", True) and platform.system() == "Linux":
            try:
                temps = psutil.sensors_temperatures()
                for key in ['coretemp', 'k10temp', 'cpu_thermal']:
                    if key in temps and temps[key]: stats['cpu_temp'] = temps[key][0].current; break
            except Exception as e: logger.info(f"未能获取 CPU 温度 (可能是硬件不支持或权限不足): {e}")
        try: mem = psutil.virtual_memory(); stats.update({'mem_total': mem.total, 'mem_used': mem.used, 'mem_percent': mem.percent})
        except Exception as e: logger.warning(f"获取内存信息失败: {e}")
        paths_to_check = self.config.get('disk_paths', [])
        if not paths_to_check:
            try: paths_to_check = [p.mountpoint for p in psutil.disk_partitions(all=False)]
            except Exception as e: logger.warning(f"自动发现磁盘分区失败, 将仅检查根目录: {e}"); paths_to_check = ['C:\\' if platform.system() == "Windows" else '/']
        for path in paths_to_check:
            try: usage = psutil.disk_usage(path); stats['disks'].append({'path': path, 'total': usage.total, 'used': usage.used, 'percent': usage.percent})
            except Exception as e: logger.warning(f"获取磁盘路径 '{path}' 信息失败: {e}")
        try: net = psutil.net_io_counters(); stats.update({'net_sent': net.bytes_sent, 'net_recv': net.bytes_recv})
        except Exception as e: logger.warning(f"获取网络IO信息失败: {e}")
        return stats
    def process_stats(self, raw_stats: Dict[str, Any]) -> Dict[str, Any]:
        processed = raw_stats.copy(); uptime = datetime.datetime.now() - self.boot_time
        days, rem = divmod(uptime.total_seconds(), 86400); hours, rem = divmod(rem, 3600); minutes, _ = divmod(rem, 60)
        processed['uptime_str'] = f"{int(days)}天 {int(hours)}小时 {int(minutes)}分钟"
        processed['cpu_percent_str'] = f"{raw_stats.get('cpu_percent', 0):.1f}"; processed['mem_percent_str'] = f"{raw_stats.get('mem_percent', 0):.1f}"
        processed['mem_total_str'] = self._format_bytes(raw_stats.get('mem_total', 0)); processed['mem_used_str'] = self._format_bytes(raw_stats.get('mem_used', 0))
        processed['net_sent_str'] = self._format_bytes(raw_stats.get('net_sent', 0)); processed['net_recv_str'] = self._format_bytes(raw_stats.get('net_recv', 0))
        processed['disks_str'] = [{'path': d['path'], 'percent': f"{d.get('percent', 0):.1f}", 'used': self._format_bytes(d.get('used', 0)), 'total': self._format_bytes(d.get('total', 0))} for d in raw_stats.get('disks', [])]
        return processed
    async def render_status_image(self, data: Dict[str, Any]) -> str:
        HTML_TEMPLATE = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;width:450px;padding:10px;background-color:#f0f2f5}.card{background-color:#fff;padding:20px;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,.1)}h2{color:#1f2937;text-align:center;margin-top:0;margin-bottom:20px;font-weight:600}.item{margin-bottom:16px}.label{font-weight:500;color:#4b5563;display:block;margin-bottom:6px}.progress-bar{width:100%;background-color:#e5e7eb;border-radius:8px;overflow:hidden;height:20px}.progress{height:100%;background:linear-gradient(90deg,#4f46e5,#7c3aed);color:#fff;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:500;transition:width .5s ease-in-out}.info-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:14px;color:#374151}.disk-item{border-top:1px solid #e5e7eb;padding-top:10px;margin-top:10px}</style></head><body><div class="card"><h2>服务器实时状态</h2><div class="item"><span class="label">⏱️ 已稳定运行: {{ uptime_str }}</span></div><div class="item"><span class="label">🖥️ CPU {% if cpu_temp %}({{ cpu_temp }}°C){% endif %}</span><div class="progress-bar"><div class="progress" style="width: {{ cpu_percent_str }}%;">{{ cpu_percent_str }}%</div></div></div><div class="item"><span class="label">💾 内存 ({{ mem_used_str }} / {{ mem_total_str }})</span><div class="progress-bar"><div class="progress" style="width: {{ mem_percent_str }}%;">{{ mem_percent_str }}%</div></div></div>{% for disk in disks_str %}<div class="item disk-item"><span class="label">💿 磁盘 [{{ disk.path }}] ({{ disk.used }} / {{ disk.total }})</span><div class="progress-bar"><div class="progress" style="width: {{ disk.percent }}%;">{{ disk.percent }}%</div></div></div>{% endfor %}<div class="item info-grid" style="border-top:1px solid #e5e7eb;padding-top:16px"><div><span class="label">⬆️ 总上传</span>{{ net_sent_str }}</div><div><span class="label">⬇️ 总下载</span>{{ net_recv_str }}</div></div></div></body></html>"""
        return await self.html_render(HTML_TEMPLATE, data)
    @filter.command("status", alias={"服务器状态", "状态", "zt", "s"})
    async def handle_server_status(self, event: AstrMessageEvent):
        try:
            loop = asyncio.get_running_loop()
            raw_stats = await loop.run_in_executor(None, self.get_system_stats)
            processed_data = self.process_stats(raw_stats)
            image_url = await self.render_status_image(processed_data)
            yield event.image_result(image_url)
        except Exception as e:
            logger.error(f"处理 status 指令时发生未知错误: {e}", exc_info=True)
            yield event.plain_result(f"抱歉，生成状态图时出现错误，请联系管理员。")
    @staticmethod
    def _format_bytes(byte_count: int) -> str:
        if byte_count is None: return "N/A"
        power = 1024; n = 0
        power_labels = {0: ' B', 1: ' KB', 2: ' MB', 3: ' GB', 4: ' TB'}
        while byte_count >= power and n < len(power_labels) - 1: byte_count /= power; n += 1
        return f"{byte_count:.2f}{power_labels[n]}"