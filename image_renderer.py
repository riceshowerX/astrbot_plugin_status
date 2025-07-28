from PIL import Image, ImageDraw, ImageFont
import io
import datetime

def _format_uptime(uptime):
    if not uptime:
        return "已稳定运行: 未知"
    days, rem = divmod(uptime.total_seconds(), 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    return f"已稳定运行: {int(days)}天 {int(hours)}小时 {int(minutes)}分钟"

def _format_bytes(byte_count):
    if byte_count is None: return "N/A"
    power, n = 1024, 0
    labels = ['B', 'KB', 'MB', 'GB', 'TB']
    while byte_count >= power and n < len(labels) - 1:
        byte_count /= power
        n += 1
    return f"{byte_count:.2f}{labels[n]}"

def render_status_image(metrics, font_path="arial.ttf"):
    width, height = 650, 380 + 40 * len(metrics.disks)
    bg_color = (32, 32, 38)
    font_color = (240, 240, 240)
    accent = (80, 180, 250)
    font_size = 24

    try:
        font = ImageFont.truetype(font_path, font_size)
        font_bold = ImageFont.truetype(font_path, font_size + 4)
    except Exception:
        font = ImageFont.load_default()
        font_bold = ImageFont.load_default()

    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    draw.text((30, 28), "服务器实时状态", font=font_bold, fill=accent)
    y = 70
    sep = 35

    draw.text((30, y), _format_uptime(metrics.uptime), font=font, fill=font_color)
    y += sep

    cpu_line = f"CPU: {metrics.cpu_percent:.1f}%"
    if metrics.cpu_temp is not None:
        cpu_line += f"  温度: {metrics.cpu_temp:.1f}°C"
    draw.text((30, y), cpu_line, font=font, fill=font_color)
    y += sep

    mem_line = f"内存: {metrics.mem_percent:.1f}%  已用 {_format_bytes(metrics.mem_used)} / {_format_bytes(metrics.mem_total)}"
    draw.text((30, y), mem_line, font=font, fill=font_color)
    y += sep

    if metrics.disks:
        for d in metrics.disks:
            disk_line = f"磁盘({d.path}): {d.percent:.1f}%  已用 {_format_bytes(d.used)} / {_format_bytes(d.total)}"
            draw.text((30, y), disk_line, font=font, fill=font_color)
            y += sep

    net_line = f"网络上传: {_format_bytes(metrics.net_sent)}   下载: {_format_bytes(metrics.net_recv)}"
    draw.text((30, y), net_line, font=font, fill=font_color)
    y += sep

    draw.text((width-260, height-40), f"更新时间: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}",
              font=ImageFont.truetype(font_path, 18) if font_path else font, fill=(160, 160, 160))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
