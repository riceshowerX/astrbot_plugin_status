#!/usr/bin/env python3
"""
AstrBot Server Status Plugin - 安装脚本
"""

import os
import sys
from setuptools import setup, find_packages

# 读取版本信息
with open('src/__init__.py', 'r', encoding='utf-8') as f:
    for line in f:
        if line.startswith('__version__'):
            version = line.split('=')[1].strip().strip('"\'')
            break
    else:
        version = '3.0.0'

# 读取长描述
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

# 读取依赖项
with open('requirements.txt', 'r', encoding='utf-8') as f:
    requirements = []
    for line in f:
        line = line.strip()
        if line and not line.startswith('#'):
            requirements.append(line)

setup(
    name="astrbot-plugin-status",
    version=version,
    description="AstrBot Server Status Plugin - 工业级服务器状态监控插件",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="riceshowerx & AstrBot Assistant",
    author_email="riceshowerx@example.com",
    url="https://github.com/riceshowerX/astrbot_plugin_status",
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    include_package_data=True,
    install_requires=requirements,
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Monitoring",
        "Topic :: Utilities",
    ],
    python_requires=">=3.9",
    keywords="astrbot plugin server status monitoring system",
    project_urls={
        "Documentation": "https://github.com/riceshowerX/astrbot_plugin_status/wiki",
        "Source": "https://github.com/riceshowerX/astrbot_plugin_status",
        "Tracker": "https://github.com/riceshowerX/astrbot_plugin_status/issues",
    },
    entry_points={
        "astrbot.plugin": [
            "status = src.plugin:ServerStatusPlugin",
        ],
    },
)

if __name__ == "__main__":
    print(f"Building AstrBot Server Status Plugin v{version}")
    print("This is primarily for development and distribution.")
    print("For AstrBot installation, use the plugin management interface.")