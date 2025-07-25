# main.py (V1.5.2 修正图片发送API错误，使用临时文件策略)

import psutil
import datetime
import platform
import asyncio
import io
import uuid # 用于生成唯一文件名
from typing import Dict, Any, Optional
from pathlib import Path

# 新增 Pillow 图像处理库的导入
from PIL import Image, ImageDraw, ImageFont

# 导入 AstrBot 官方 API
from astrbot.api.star import Star, register, Context
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger, AstrBotConfig
import astrbot.api.message_components as Comp

# --- 插件主类 ---

@register(
    name="astrabot_plugin_status", 
    author="riceshowerx", 
    desc="以图片形式查询服务器的实时状态 (高速版)", 
    version="1.5.2", # 版本号提升
    repo="https://github.com/riceshowerX/astrbot_plugin_status"
)
class ServerStatusPlugin(Star):
    def __init__(self, context: Context, config: Optional[AstrBotConfig] = None):
        super().__init__(context)
        self.context = context
        self.config = config if config is not None else AstrBotConfig({})
        # 创建一个用于存放临时图片的目录
        self.temp_dir = Path(__file__).parent / "tmp"
        self.temp_dir.mkdir(exist_ok=True)
        try:
            self.boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        except Exception as e:
            logger.error(f"获取系统启动时间失败: {e}"); self.boot_time = datetime.datetime.now()
        font_file = Path(__file__).parent / "font.ttf"
        if font_file.exists():
            try:
                self.font_title = ImageFont.truetype(str(font_file), 32)
                self.font_main = ImageFont.truetype(str(font_file), 24)
                self.font_small = ImageFont.truetype(str(font_file), 18)
            except Exception as e:
                logger.warning(f"加载字体文件失败: {e}"); self._load_default_fonts()
        else:
            logger.info("未找到 font.ttf，将使用默认字体。"); self._load_default_fonts()
        logger.info("服务器状态插件(v1.5.2)已成功加载。")

    def _load_default_fonts(self):
        self.font_title = ImageFont.load_default(); self.font_main = ImageFont.load_default(); self.font_small = ImageFont.load_default()

    def get_system_stats(self) -> Dict[str, Any]:
        # ... (此函数无需改动，为简洁省略) ...
        stats = {'disks': []};
        try: stats['cpu_percent'] = psutil.cpu_percent(interval=1)
        except Exception as e: logger.warning(f"获取 CPU 使用率失败: {e}"); stats['cpu_percent'] = 0
        stats['cpu_temp'] = None
        if self.config.get("show_temp", True) and platform.system() == "Linux":
            try:
                temps = psutil.sensors_temperatures()
                for key in ['coretemp', 'k10temp', 'cpu_thermal']:
                    if key in temps and temps[key]: stats['cpu_temp'] = temps[key][0].current; break
            except Exception as e: logger.info(f"未能获取 CPU 温度: {e}")
        try: mem = psutil.virtual_memory(); stats.update({'mem_total': mem.total, 'mem_used': mem.used, 'mem_percent': mem.percent})
        except Exception as e: logger.warning(f"获取内存信息失败: {e}")
        paths_to_check = self.config.get('disk_paths', [])
        if not paths_to_check:
            try: paths_to_check = [p.mountpoint for p in psutil.disk_partitions(all=False)]
            except Exception as e: logger.warning(f"自动发现磁盘分区失败: {e}"); paths_to_check = ['C:\\' if platform.system() == "Windows" else '/']
        for path in paths_to_check:
            try: usage = psutil.disk_usage(path); stats['disks'].append({'path': path, 'total': usage.total, 'used': usage.used, 'percent': usage.percent})
            except Exception as e: logger.warning(f"获取磁盘路径 '{path}' 信息失败: {e}")
        try: net = psutil.net_io_counters(); stats.update({'net_sent': net.bytes_sent, 'net_recv': net.bytes_recv})
        except Exception as e: logger.warning(f"获取网络IO信息失败: {e}")
        return stats

    def process_stats(self, raw_stats: Dict[str, Any]) -> Dict[str, Any]:
        # ... (此函数无需改动，为简洁省略) ...
        processed = raw_stats.copy(); uptime = datetime.datetime.now() - self.boot_time
        days, rem = divmod(uptime.total_seconds(), 86400); hours, rem = divmod(rem, 3600); minutes, _ = divmod(rem, 60)
        processed['uptime_str'] = f"{int(days)}天 {int(hours)}小时 {int(minutes)}分钟"
        processed['cpu_percent_str'] = f"{raw_stats.get('cpu_percent', 0):.1f}"; processed['mem_percent_str'] = f"{raw_stats.get('mem_percent', 0):.1f}"
        processed['mem_total_str'] = self._format_bytes(raw_stats.get('mem_total', 0)); processed['mem_used_str'] = self._format_bytes(raw_stats.get('mem_used', 0))
        processed['net_sent_str'] = self._format_bytes(raw_stats.get('net_sent', 0)); processed['net_recv_str'] = self._format_bytes(raw_stats.get('net_recv', 0))
        processed['disks_str'] = [{'path': d['path'], 'percent': f"{d.get('percent', 0):.1f}", 'used': self._format_bytes(d.get('used', 0)), 'total': self._format_bytes(d.get('total', 0))} for d in raw_stats.get('disks', [])]
        return processed

    async def render_status_with_pillow(self, data: Dict[str, Any]) -> io.BytesIO:
        # ... (此函数无需改动，为简洁省略) ...
        W, H = 600, 280; H += len(data.get('disks_str', [])) * 70
        BG_COLOR, TEXT_COLOR, BAR_BG, BAR_COLOR = "#ffffff", "#1f2937", "#e5e7eb", "#4f46e5"
        img = Image.new("RGB", (W, H), BG_COLOR); draw = ImageDraw.Draw(img); y = 30
        draw.text((W/2, y), "服务器实时状态", font=self.font_title, fill=TEXT_COLOR, anchor="ms"); y += 50
        def draw_item(label, value, percent):
            nonlocal y
            draw.text((40, y), label, font=self.font_main, fill=TEXT_COLOR)
            draw.rectangle((40, y + 35, W - 40, y + 55), fill=BAR_BG, width=0)
            bar_width = (W - 80) * (float(percent) / 100)
            draw.rectangle((40, y + 35, 40 + bar_width, y + 55), fill=BAR_COLOR, width=0)
            draw.text((W-40, y), f"{value}", font=self.font_main, fill=TEXT_COLOR, anchor="ra"); y += 70
        cpu_temp_str = f"({data['cpu_temp']:.1f}°C)" if data.get('cpu_temp') else ""
        draw_item(f"🖥️ CPU {cpu_temp_str}", f"{data['cpu_percent_str']}%", data['cpu_percent_str'])
        draw_item(f"💾 内存 ({data['mem_used_str']} / {data['mem_total_str']})", f"{data['mem_percent_str']}%", data['mem_percent_str'])
        for disk in data.get('disks_str', []): draw_item(f"💿 磁盘 [{disk['path']}] ({disk['used']} / {disk['total']})", f"{disk['percent']}%", disk['percent'])
        draw.line([(40, y), (W - 40, y)], fill="#e5e7eb", width=2); y += 20
        draw.text((40, y), f"⏱️ 运行: {data['uptime_str']}", font=self.font_small, fill=TEXT_COLOR); y += 25
        draw.text((40, y), f"⬆️ 上传: {data['net_sent_str']}", font=self.font_small, fill=TEXT_COLOR)
        draw.text((W - 40, y), f"⬇️ 下载: {data['net_recv_str']}", font=self.font_small, fill=TEXT_COLOR, anchor="ra")
        img_buffer = io.BytesIO(); img.save(img_buffer, format='PNG', quality=90); img_buffer.seek(0)
        return img_buffer

    @filter.command("status", alias={"服务器状态", "状态", "zt", "s"})
    async def handle_server_status(self, event: AstrMessageEvent):
        '''查询并显示当前服务器的详细运行状态 (Pillow高速版)'''
        # 提前定义临时文件路径变量，以备 finally 块使用
        temp_filepath = None
        try:
            await event.send(event.plain_result("正在生成状态图，请稍候..."))
            
            loop = asyncio.get_running_loop()
            raw_stats = await loop.run_in_executor(None, self.get_system_stats)
            processed_data = self.process_stats(raw_stats)
            image_buffer = await self.render_status_with_pillow(processed_data)
            
            # ===================================================================
            # 核心修正：实现“临时文件”策略
            # ===================================================================
            # 1. 生成一个唯一的临时文件名
            temp_filename = f"status_{uuid.uuid4()}.png"
            temp_filepath = self.temp_dir / temp_filename
            
            # 2. 将内存中的图片数据写入临时文件
            with open(temp_filepath, "wb") as f:
                f.write(image_buffer.getvalue())

            # 3. 使用临时文件的路径（字符串）创建 Image 组件
            image_component = Comp.Image(file=str(temp_filepath))
            
            # 4. 构建并发送消息
            message_to_send = event.make_result()
            message_to_send.chain = [image_component]
            await event.send(message_to_send)
            # ===================================================================

        except Exception as e:
            logger.error(f"处理 status 指令时发生未知错误: {e}", exc_info=True)
            await event.send(event.plain_result(f"抱歉，生成状态图时出现错误，请联系管理员。"))
        finally:
            # 5. (关键) 无论成功还是失败，都尝试删除临时文件
            if temp_filepath and temp_filepath.exists():
                try:
                    temp_filepath.unlink()
                except Exception as e:
                    logger.warning(f"删除临时文件 {temp_filepath} 失败: {e}")
    
    @staticmethod
    def _format_bytes(byte_count: int) -> str:
        if byte_count is None: return "N/A"
        power = 1024; n = 0
        power_labels = {0: ' B', 1: ' KB', 2: ' MB', 3: ' GB', 4: ' TB'}
        while byte_count >= power and n < len(power_labels) - 1: byte_count /= power; n += 1
        return f"{byte_count:.2f}{power_labels[n]}"