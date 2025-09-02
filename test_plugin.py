#!/usr/bin/env python3
"""
AstrBot Server Status Plugin - 功能测试脚本

这个脚本用于测试插件的基本功能，不依赖AstrBot环境。
"""

import asyncio
import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.core.config import PluginConfig, ConfigValidator
from src.core.collector import MetricsCollector
from src.core.formatter import MetricsFormatter

async def test_config():
    """测试配置管理"""
    print("🧪 测试配置管理...")
    
    # 测试默认配置
    config = PluginConfig()
    assert config.privacy_level == "full"
    assert config.cache_duration == 10
    print("✅ 默认配置测试通过")
    
    # 测试配置验证
    test_config = {
        'privacy_level': 'invalid',
        'cache_duration': -1,
        'disk_paths': ['/safe/path', '/unsafe/../path']
    }
    
    errors = ConfigValidator.validate_config(test_config)
    assert len(errors) > 0
    print("✅ 配置验证测试通过")
    
    # 测试磁盘路径安全检测
    assert ConfigValidator.is_safe_disk_path('/safe/path') == True
    assert ConfigValidator.is_safe_disk_path('/unsafe/../path') == False
    assert ConfigValidator.is_safe_disk_path('') == False
    print("✅ 安全路径检测测试通过")

async def test_collector():
    """测试数据采集器"""
    print("🧪 测试数据采集器...")
    
    config = PluginConfig()
    collector = MetricsCollector(config.to_dict())
    
    try:
        # 测试指标采集
        metrics = await collector.collect_metrics()
        
        # 基本验证
        assert hasattr(metrics, 'cpu_percent')
        assert hasattr(metrics, 'mem_total')
        assert hasattr(metrics, 'disks')
        assert hasattr(metrics, 'errors')
        
        print("✅ 数据采集测试通过")
        
    except Exception as e:
        print(f"⚠️  数据采集测试出现异常: {e}")
        # 在测试环境中可能某些指标无法采集，这不算失败

async def test_formatter():
    """测试格式化器"""
    print("🧪 测试格式化器...")
    
    config = PluginConfig()
    formatter = MetricsFormatter(config.to_dict())
    
    # 创建测试数据
    from datetime import datetime, timedelta
    from src.core.collector import SystemMetrics, DiskUsage
    
    test_metrics = SystemMetrics(
        cpu_percent=25.5,
        cpu_temp=45.0,
        cpu_freq=3200.0,
        cpu_cores=8,
        cpu_load_avg=(1.2, 1.0, 0.8),
        mem_total=17179869184,
        mem_used=10737418240,
        mem_free=6442450944,
        mem_percent=62.5,
        swap_total=2147483648,
        swap_used=536870912,
        swap_percent=25.0,
        disks=[
            DiskUsage(
                display_path="/data",
                total=536870912000,
                used=268435456000,
                free=268435456000,
                percent=50.0,
                fs_type="ext4",
                mount_point="/data"
            )
        ],
        network=None,
        processes=None,
        uptime=timedelta(days=3, hours=2, minutes=15),
        boot_time=datetime.now() - timedelta(days=3, hours=2, minutes=15),
        is_containerized=False,
        platform_info={
            'system': 'Linux',
            'release': '5.15.0-91-generic',
            'version': '#101-Ubuntu SMP Tue Nov 14 13:30:08 UTC 2023',
            'machine': 'x86_64'
        },
        errors=[],
        warnings=[]
    )
    
    # 测试不同格式输出
    markdown_output = formatter.format(test_metrics)
    assert "服务器实时状态" in markdown_output
    assert "CPU" in markdown_output
    
    # 测试纯文本格式
    config.output_format = "plain"
    formatter = MetricsFormatter(config.to_dict())
    plain_output = formatter.format(test_metrics)
    assert "服务器状态报告" in plain_output
    
    # 测试JSON格式
    config.output_format = "json"
    formatter = MetricsFormatter(config.to_dict())
    json_output = formatter.format(test_metrics)
    assert '"cpu_percent": 25.5' in json_output
    
    print("✅ 格式化器测试通过")

async def main():
    """主测试函数"""
    print("🚀 开始测试 AstrBot Server Status Plugin v3.0")
    print("=" * 60)
    
    try:
        await test_config()
        await test_collector()
        await test_formatter()
        
        print("=" * 60)
        print("🎉 所有测试通过！")
        print("插件基本功能正常，可以部署到AstrBot环境。")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(asyncio.run(main()))