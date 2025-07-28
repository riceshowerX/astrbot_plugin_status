import psutil
import datetime
import platform
import asyncio
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import json
import os
import random

# 统一使用框架提供的 logger
from astrbot.api.star import Star, register, Context
from astrbot.api.event import filter as event_filter, AstrMessageEvent
from astrbot.api import logger, AstrBotConfig

# == 二次元元素：消息库与角色库 ==
MOE_MESSAGES = {
    "boot": [
        "喵呜~ 服务器启动啦，{kanban}来为你守护系统！(｡•ㅅ•｡)♡",
        "咦咦，{kanban}刚刚醒来，准备为主人监控服务器哦~"
    ],
    "error": [
        "呜呜，检测出了一些小问题呢 ({reason})，要不要安慰一下看板娘？(；´д｀)ゞ",
        "{kanban}发现了异常：{reason}，请主人快来看看…"
    ],
    "ok": [
        "一切正常，{kanban}超开心！服务器很健康哟~ (๑•̀ㅂ•́)و✧",
        "{kanban}报告：当前没有异常，可以放心摸摸头！"
    ],
    "timeout": [
        "呜呜，状态采集超时了，{kanban}有点着急…",
    ],
    "special": [
        "今天是{festival}，{kanban}祝主人节日快乐！服务器也要加油哦！"
    ]
}

KANBAN_ROLES = [
    {"name": "小星", "emoji": "⭐", "avatar": "https://cdn.example.com/xiaoxing.png"},
    {"name": "初音", "emoji": "🎤", "avatar": "https://cdn.example.com/miku.png"},
    {"name": "爱酱", "emoji": "💖", "avatar": "https://cdn.example.com/ai.png"}
]

def pick_kanban():
    return random.choice(KANBAN_ROLES)

def moe_message(key, **kwargs):
    msg = random.choice(MOE_MESSAGES.get(key, [""]))
    return msg.format(**kwargs)

def is_festival_today():
    now = datetime.datetime.now()
    if now.month == 8 and now.day == 31:
        return "初音未来生日"
    if now.month == 7 and now.day == 28:
        return "GitHub Copilot 纪念日"
    return None

# --- 工具函数 ---
def safe_disk_path(path: Any) -> bool:
    """
    验证给定的路径是否为用于磁盘使用情况检查的安全、绝对路径。
    防止路径遍历和其他不安全的模式。
    """
    if not isinstance(path, str) or not path or len(path) > 1024:
        return False
    if not os.path.isabs(path):
        return False
    for c in ['..', '~', '\0', '*', '?', '|', '<', '>', '"']:
        if c in path:
            return False
    return True

# --- 数据契约 ---
@dataclass(frozen=True)
class DiskUsage:
    path: str
    total: int
    used: int
    percent: float

@dataclass(frozen=True)
class SystemMetrics:
    cpu_percent: float
    cpu_temp: Optional[float]
    mem_total: int
    mem_used: int
    mem_percent: float
    net_sent: int
    net_recv: int
    uptime: Optional[datetime.timedelta]
    disks: List[DiskUsage] = field(default_factory=list)
    # 扩展: 进程检测与SSL证书（演示字段）
    nginx_alive: Optional[bool] = None
    # ssl_expiry_days: Optional[int] = None

# --- 数据采集器 ---
class MetricsCollector:
    MAX_DISK_COUNT = 10

    def __init__(self, disk_paths_to_check: List[str], show_temp: bool):
        self.disk_paths_to_check = disk_paths_to_check
        self.show_temp = show_temp
        try:
            self.boot_time: Optional[datetime.datetime] = datetime.datetime.fromtimestamp(psutil.boot_time())
        except Exception as e:
            logger.error("[StatusPlugin] 获取系统启动时间失败: %s", e)
            self.boot_time = None

    def _get_disk_usages(self) -> List[DiskUsage]:
        disks = []
        paths_to_check = self.disk_paths_to_check

        if not paths_to_check:
            try:
                all_parts = [p.mountpoint for p in psutil.disk_partitions(all=False)]
                paths_to_check = [p for p in all_parts if safe_disk_path(p)][:self.MAX_DISK_COUNT]
            except Exception as e:
                logger.warning("[StatusPlugin] 自动发现磁盘分区失败，将使用默认路径: %s", e)
                paths_to_check = ['C:\\' if platform.system() == "Windows" else '/']

        for path in paths_to_check:
            try:
                usage = psutil.disk_usage(path)
                disks.append(DiskUsage(
                    path=path, total=usage.total, used=usage.used, percent=usage.percent
                ))
            except (PermissionError, FileNotFoundError) as e:
                logger.warning("[StatusPlugin] 无法访问磁盘路径 '%s' (%s)，已忽略。", path, e.__class__.__name__)
            except Exception as e:
                logger.warning("[StatusPlugin] 获取磁盘路径 '%s' 信息失败: %s", path, e)
        return disks

    def check_process_alive(self, pname="nginx"):
        """检测指定进程是否存活"""
        try:
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and pname.lower() in proc.info['name'].lower():
                    return True
            return False
        except Exception:
            return None

    # def check_ssl_expiry(self, hostname, port=443):
    #     # 预留接口，可用ssl和socket实现
    #     return None

    def collect(self) -> Optional[SystemMetrics]:
        try:
            cpu_p = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            net = psutil.net_io_counters()
        except Exception as e:
            logger.error("[StatusPlugin] 获取核心系统指标失败: %s", e, exc_info=True)
            return None

        cpu_t = None
        if self.show_temp and hasattr(psutil, "sensors_temperatures"):
            try:
                temps = psutil.sensors_temperatures()
                for key in ['coretemp', 'k10temp', 'cpu_thermal', 'acpitz']:
                    if key in temps and temps[key]:
                        cpu_t = temps[key][0].current
                        break
            except Exception as e:
                logger.warning("[StatusPlugin] 获取CPU温度失败: %s", e)

        current_uptime = (datetime.datetime.now() - self.boot_time) if self.boot_time else None

        # 二次元彩蛋：检测nginx进程
        nginx_alive = self.check_process_alive("nginx")

        return SystemMetrics(
            cpu_percent=cpu_p, cpu_temp=cpu_t,
            mem_total=mem.total, mem_used=mem.used, mem_percent=mem.percent,
            net_sent=net.bytes_sent, net_recv=net.bytes_recv,
            uptime=current_uptime,
            disks=self._get_disk_usages(),
            nginx_alive=nginx_alive
            # ssl_expiry_days=None
        )

# --- 文本格式化器 ---
class MetricsFormatter:
    _BYTE_LABELS: Dict[int, str] = {0: ' B', 1: ' KB', 2: ' MB', 3: ' GB', 4: ' TB'}
    SEPARATOR = "--------------------"

    def format(self, metrics: SystemMetrics, kanban: dict) -> str:
        parts = [
            f"{kanban['emoji']} **服务器实时状态 by {kanban['name']}**",
            self.SEPARATOR,
            self._format_uptime(metrics.uptime),
            self._format_cpu(metrics),
            self._format_memory(metrics),
            self._format_disks(metrics.disks),
            self._format_network(metrics),
            self._format_nginx(metrics.nginx_alive)
        ]
        return "\n".join(filter(None, parts))

    def _format_uptime(self, uptime: Optional[datetime.timedelta]) -> str:
        if uptime is None:
            return "⏱️ **已稳定运行**: 未知"
        days, rem = divmod(uptime.total_seconds(), 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        return f"⏱️ **已稳定运行**: {int(days)}天 {int(hours)}小时 {int(minutes)}分钟"

    def _format_cpu(self, m: SystemMetrics) -> str:
        temp_str = f" ({m.cpu_temp:.1f}°C)" if m.cpu_temp is not None else ""
        return f"{self.SEPARATOR}\n🖥️ **CPU**{temp_str}\n   - **使用率**: {m.cpu_percent:.1f}%"

    def _format_memory(self, m: SystemMetrics) -> str:
        used_formatted = self._format_bytes(m.mem_used)
        total_formatted = self._format_bytes(m.mem_total)
        return (
            f"{self.SEPARATOR}\n💾 **内存**\n"
            f"   - **使用率**: {m.mem_percent:.1f}%\n"
            f"   - **已使用**: {used_formatted} / {total_formatted}"
        )

    def _format_disks(self, disks: List[DiskUsage]) -> str:
        if not disks:
            return ""
        disk_parts = [
            f"""💿 **磁盘 ({self._escape_path(d.path)})**\n   - **使用率**: {d.percent:.1f}%\n   - **已使用**: {self._format_bytes(d.used)} / {self._format_bytes(d.total)}"""
            for d in disks
        ]
        return f"{self.SEPARATOR}\n" + f"\n{self.SEPARATOR}\n".join(disk_parts)

    def _format_network(self, m: SystemMetrics) -> str:
        return (
            f"{self.SEPARATOR}\n🌐 **网络I/O (自启动)**\n"
            f"   - **总上传**: {self._format_bytes(m.net_sent)}\n"
            f"   - **总下载**: {self._format_bytes(m.net_recv)}"
        )
    def _format_nginx(self, alive: Optional[bool]) -> str:
        if alive is None:
            return ""
        if alive:
            return f"{self.SEPARATOR}\n🥟 **Nginx进程存活**: (正常运行中~)"
        else:
            return f"{self.SEPARATOR}\n🥟 **Nginx进程存活**: (未检测到进程，快叫管理员！)"

    @classmethod
    def _format_bytes(cls, byte_count: int) -> str:
        if byte_count is None: return "N/A"
        power, n = 1024, 0
        while byte_count >= power and n < len(cls._BYTE_LABELS) - 1:
            byte_count /= power
            n += 1
        return f"{byte_count:.2f}{cls._BYTE_LABELS[n]}"

    @staticmethod
    def _escape_path(path: str) -> str:
        return path.replace('`', '').replace('*', '').replace('\n', '').replace('\r', '')

# --- AstrBot 插件主类 ---
@register(
    name="astrabot_plugin_status",
    author="riceshowerx & AstrBot Assistant",
    desc="以文本形式查询服务器的实时状态（萌化升级）",
    version="1.1",
    repo="https://github.com/riceshowerX/astrbot_plugin_status"
)
class ServerStatusPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.context = context
        self.plugin_config: Dict[str, Any] = self._validate_config(config)
        self.collector: Optional[MetricsCollector] = None
        self.formatter = MetricsFormatter()
        self._cache: Optional[str] = None
        self._cache_timestamp: float = 0.0
        self.cache_duration: int = self.plugin_config.get('cache_duration', 5)
        self._lock = asyncio.Lock()
        # pick kanban娘
        self.kanban = pick_kanban()
        self.language = self.plugin_config.get('language', 'zh')

    def _validate_config(self, config: AstrBotConfig) -> Dict[str, Any]:
        checked: Dict[str, Any] = {}
        try:
            cache_duration = int(config.get('cache_duration', 5))
            checked['cache_duration'] = cache_duration if 0 <= cache_duration <= 3600 else 5
        except (ValueError, TypeError):
            checked['cache_duration'] = 5

        disk_paths_raw = config.get('disk_paths', [])
        final_disk_paths: List[str] = []
        if isinstance(disk_paths_raw, str):
            try:
                disk_paths_raw = json.loads(disk_paths_raw)
            except json.JSONDecodeError:
                disk_paths_raw = []
        if isinstance(disk_paths_raw, list):
            final_disk_paths = [p for p in disk_paths_raw if safe_disk_path(p)]
        checked['disk_paths'] = final_disk_paths
        checked['show_temp'] = bool(config.get('show_temp', True))
        checked['language'] = config.get('language', 'zh')
        return checked

    @event_filter.command("status", alias={"服务器状态", "状态", "zt", "s"})
    async def handle_server_status(self, event: AstrMessageEvent):
        now = time.time()
        async with self._lock:
            if self.cache_duration > 0 and self._cache and (now - self._cache_timestamp < self.cache_duration):
                yield event.plain_result(self._cache)
                return

            festival = is_festival_today()
            if festival:
                yield event.plain_result(
                    moe_message("special", kanban=self.kanban["name"], festival=festival)
                )

            yield event.plain_result(
                moe_message("boot", kanban=self.kanban["name"])
            )

            try:
                if self.collector is None:
                    self.collector = MetricsCollector(
                        disk_paths_to_check=self.plugin_config['disk_paths'],
                        show_temp=self.plugin_config['show_temp']
                    )
                metrics = await asyncio.wait_for(asyncio.to_thread(self.collector.collect), timeout=20)
                if metrics is None:
                    yield event.plain_result(
                        moe_message("error", kanban=self.kanban["name"], reason="核心指标获取失败")
                    )
                    return

                text_message = self.formatter.format(metrics, self.kanban)
                self._cache, self._cache_timestamp = text_message, now
                ok_message = moe_message("ok", kanban=self.kanban["name"])
                yield event.plain_result(ok_message)
                yield event.plain_result(text_message)

            except asyncio.TimeoutError:
                logger.error("[StatusPlugin] 采集服务器状态超时")
                yield event.plain_result(
                    moe_message("timeout", kanban=self.kanban["name"])
                )
            except Exception as e:
                logger.error("[StatusPlugin] 处理 status 指令时发生未知错误: %s", e, exc_info=True)
                yield event.plain_result(
                    moe_message("error", kanban=self.kanban["name"], reason="未知错误")
                )

    @event_filter.command("miku", alias={"初音", "看板娘"})
    async def handle_kanban(self, event: AstrMessageEvent):
        yield event.plain_result(f"{self.kanban['emoji']} {self.kanban['name']}在这里为你服务喵~")
