#!/usr/bin/env python3
"""
AstrBot Server Status Plugin - 工业级服务器状态监控插件

版本: 3.0.0
功能: 实时监控服务器CPU、内存、磁盘、网络等系统指标
特性: 多格式输出、智能缓存、容器支持、隐私保护
"""

import os
import sys

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# 导入主插件模块
from src.plugin import ServerStatusPlugin

# 导出插件类供AstrBot加载
__all__ = ['ServerStatusPlugin']

# 直接运行时显示信息
if __name__ == "__main__":
    print("=" * 60)
    print("AstrBot Server Status Plugin v3.0.0")
    print("=" * 60)
    print("📦 这是一个AstrBot插件，需要在AstrBot环境中运行。")
    print("")
    print("🚀 功能特性:")
    print("  ✅ 实时系统监控 (CPU/内存/磁盘/网络)")
    print("  ✅ 多格式输出 (Markdown/纯文本/JSON)")
    print("  ✅ 智能缓存机制")
    print("  ✅ 容器环境支持")
    print("  ✅ 隐私保护模式")
    print("")
    print("🔧 使用方法:")
    print("  1. 在AstrBot插件管理中安装此插件")
    print("  2. 配置监控选项和隐私设置")
    print("  3. 使用命令: /status, 状态, zt, s, sysinfo")
    print("")
    print("📖 文档: https://github.com/riceshowerX/astrbot_plugin_status")
    print("=" * 60)