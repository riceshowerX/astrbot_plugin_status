# AstrBot 服务器状态插件 v3.0

![Version](https://img.shields.io/badge/version-v3.0-blue) ![Python](https://img.shields.io/badge/python-3.9+-blue.svg) ![License](https://img.shields.io/badge/license-MIT-lightgrey) ![AstrBot](https://img.shields.io/badge/AstrBot-≥1.0.0-green)

> **项目地址:** [**github.com/riceshowerX/astrbot_plugin_status**](https://github.com/riceshowerX/astrbot_plugin_status)

一个为 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 打造的服务器状态监控插件，提供全面的系统指标监控和智能管理功能。

## 🚀 v3.0 新特性

### 架构升级
- **模块化设计** - 核心功能分离为独立模块，便于维护和扩展
- **类型安全** - 完整的类型注解和静态类型检查
- **异步优化** - 全异步架构，避免阻塞主线程

### 功能增强
- **多格式输出** - 支持 Markdown、纯文本、JSON 三种输出格式
- **智能缓存** - 可配置的缓存策略，支持强制刷新
- **扩展监控** - 新增进程统计、网络详情、系统负载等指标
- **容器优化** - 更好的容器环境检测和支持

### 性能优化
- **线程池管理** - 可配置的线程池大小，避免资源竞争
- **超时控制** - 精确的超时管理，防止采集卡死
- **内存优化** - 智能的内存使用和缓存清理

### 安全加固
- **输入验证** - 严格的配置验证和路径安全检查
- **隐私保护** - 增强的隐私模式，保护敏感信息
- **错误处理** - 优雅的错误处理和详细的日志记录

## 📦 安装

### 通过链接安装 (推荐)
1. 复制插件仓库链接: `https://github.com/riceshowerX/astrbot_plugin_status`
2. 在 AstrBot WebUI 的 **插件管理 → 从链接安装** 中粘贴并安装

### 通过文件安装
1. 在 [Releases](https://github.com/riceshowerX/astrbot_plugin_status/releases) 页面下载最新的 `.zip` 压缩包
2. 在 AstrBot WebUI 的 **插件管理 → 从文件安装** 中上传并安装

## ⚙️ 配置说明

### 基本配置
| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `privacy_level` | string | `full` | 隐私级别: `full`(完整) 或 `minimal`(最小) |
| `cache_duration` | int | `10` | 缓存时间(秒)，0表示禁用缓存 |
| `collect_timeout` | int | `25` | 采集超时时间(秒) |
| `output_format` | string | `markdown` | 输出格式: `markdown`, `plain`, `json` |
| `show_temp` | bool | `true` | 是否显示CPU温度 |

### 磁盘监控
| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `disk_paths` | list | `[]` | 要监控的磁盘路径列表 |
| `auto_discover_disks` | bool | `true` | 是否自动发现磁盘 |
| `max_disk_count` | int | `10` | 最大监控磁盘数量 |

### 高级配置
| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_network_stats` | bool | `true` | 启用网络统计 |
| `enable_process_stats` | bool | `true` | 启用进程统计 |
| `enable_system_info` | bool | `true` | 启用系统信息 |
| `enable_detailed_errors` | bool | `true` | 显示详细错误 |
| `max_thread_workers` | int | `3` | 最大工作线程数 |
| `collection_interval` | int | `30` | 采集间隔(秒) |

### 配置示例

```json
{
  "privacy_level": "minimal",
  "cache_duration": 15,
  "collect_timeout": 30,
  "output_format": "markdown",
  "show_temp": true,
  "disk_paths": [
    "/data",
    {"path": "/var/log", "display": "日志存储"},
    {"path": "/home", "display": "用户数据"}
  ],
  "auto_discover_disks": false,
  "max_disk_count": 5
}
```

## 🎯 使用方法

### 基本命令
- `/status` - 获取服务器状态
- `状态` / `zt` / `s` / `sysinfo` - 命令别名

### 高级用法
- `/status 刷新` - 强制重新采集数据
- `/status_help` - 显示帮助信息
- `/status_stats` - 显示插件统计信息

### 输出示例

**Markdown 格式:**
```markdown
# 🖥️ 服务器实时状态

⏱️ 系统运行时间: 3天 2小时 15分钟

🖥️ CPU
   - 使用率: 25.4%
   - 温度: 45.2°C
   - 频率: 3200MHz
   - 核心: 8核
   - 负载: 1.25, 1.10, 0.95

💾 内存
   - 使用率: 62.3%
   - 已使用: 8.2GB/16.0GB

💿 磁盘
   - /data: 45.2% (225GB/500GB)
   - 日志存储: 12.1% (12GB/100GB)

🌐 网络
   - 总上传: 2.1GB
   - 总下载: 5.4GB

📊 进程
   - 总数: 183 | 运行: 12 | 睡眠: 158

📅 数据更新时间: 2024-01-15 14:30:25
```

**JSON 格式:**
```json
{
  "system_info": {
    "uptime": "3天 2小时 15分钟",
    "boot_time": "2024-01-12T12:15:30",
    "is_containerized": false,
    "platform": {
      "system": "Linux",
      "release": "5.15.0-91-generic",
      "version": "#101-Ubuntu SMP Tue Nov 14 13:30:08 UTC 2023",
      "machine": "x86_64"
    }
  },
  "cpu_info": {
    "percent": 25.4,
    "temperature": 45.2,
    "frequency": 3200,
    "cores": 8,
    "load_avg": [1.25, 1.10, 0.95]
  },
  "memory_info": {
    "total": 17179869184,
    "used": 10737418240,
    "free": 6442450944,
    "percent": 62.3,
    "swap_total": 2147483648,
    "swap_used": 536870912,
    "swap_percent": 25.0
  }
}
```

## 🛠️ 开发指南

### 项目结构
```
astrbot_plugin_status/
├── src/                    # 源代码目录
│   ├── core/              # 核心模块
│   │   ├── __init__.py
│   │   ├── collector.py   # 数据采集器
│   │   ├── formatter.py  # 格式化器
│   │   ├── config.py     # 配置管理
│   │   └── cache.py      # 缓存管理
│   ├── __init__.py
│   └── plugin.py          # 主插件模块
├── main.py               # 入口文件
├── _conf_schema.json     # 配置架构
├── metadata.yaml         # 插件元数据
├── requirements.txt      # 依赖项
└── README.md            # 说明文档
```

### 扩展开发
要添加新的监控指标:

1. 在 `collector.py` 中添加数据采集方法
2. 在 `formatter.py` 中添加格式化逻辑
3. 更新配置验证和默认值

### 测试建议
```bash
# 安装测试依赖
pip install pytest pytest-asyncio

# 运行测试
pytest tests/ -v
```

## 🔒 安全建议

### 生产环境配置
1. **固定依赖版本**: 使用 `pip freeze > requirements.txt`
2. **限制访问权限**: 确保status命令有严格的ACL控制
3. **启用隐私模式**: 在公共群组使用 `privacy_level: minimal`
4. **监控资源使用**: 定期检查插件性能和资源消耗

### 安全配置示例
```json
{
  "privacy_level": "minimal",
  "cache_duration": 30,
  "disk_paths": [
    {"path": "/app/data", "display": "应用数据"},
    {"path": "/app/logs", "display": "日志文件"}
  ],
  "auto_discover_disks": false,
  "enable_detailed_errors": false
}
```

## 📊 性能指标

### 资源消耗
- **内存使用**: ~10-50MB (取决于监控指标数量)
- **CPU占用**: <1% (采集期间短暂峰值)
- **网络流量**: 可忽略不计

### 采集时间
- **首次采集**: 1-3秒
- **缓存命中**: <100ms
- **超时设置**: 建议25-30秒

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request!

1. Fork 本仓库
2. 创建特性分支: `git checkout -b feature/new-feature`
3. 提交更改: `git commit -am 'Add new feature'`
4. 推送分支: `git push origin feature/new-feature`
5. 创建 Pull Request

### 开发规范
- 遵循 PEP 8 代码风格
- 添加类型注解
- 编写单元测试
- 更新文档

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。

## 🆘 技术支持

- 📖 [详细文档](https://github.com/riceshowerX/astrbot_plugin_status/wiki)
- 🐛 [提交Issue](https://github.com/riceshowerX/astrbot_plugin_status/issues)
- 💬 [讨论区](https://github.com/riceshowerX/astrbot_plugin_status/discussions)

---

**温馨提示**: 在生产环境使用前，请务必测试所有功能并配置适当的安全策略。