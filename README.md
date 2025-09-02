# AstrBot 服务器状态插件 v3.0

![Version](https://img.shields.io/badge/version-v3.0-blue) ![Python](https://img.shields.io/badge/python-3.9+-blue.svg) ![License](https://img.shields.io/badge/license-MIT-lightgrey) ![AstrBot](https://img.shields.io/badge/AstrBot-≥1.0.0-green)

> **项目地址:** [**github.com/riceshowerX/astrbot_plugin_status**](https://github.com/riceshowerX/astrbot_plugin_status)

一个为 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 打造的工业级服务器状态监控插件，提供全面的系统指标监控和智能管理功能。

## 🚀 v3.0 新特性

### 架构优化
- **单文件架构** - 保持AstrBot兼容性的同时实现内部模块化
- **类型安全** - 完整的类型注解和静态类型检查
- **异步优化** - 全异步架构，避免阻塞主线程

### 功能增强
- **多格式输出** - 支持 Markdown、纯文本 两种输出格式
- **智能缓存** - 可配置的缓存策略，支持强制刷新
- **容器支持** - 改进的容器环境检测和运行时间计算
- **隐私保护** - 增强的隐私模式（完整/最小化）

### 性能提升
- **线程池管理** - 优化的线程池配置，避免资源竞争
- **超时控制** - 精确的超时管理，防止采集卡死
- **内存优化** - 智能的内存使用和缓存清理

### 安全加固
- **输入验证** - 严格的配置验证和路径安全检查
- **错误处理** - 优雅的错误处理和详细的日志记录
- **路径安全** - 增强的磁盘路径安全检查机制

## 📦 安装

### 通过链接安装 (推荐)
1. 复制插件仓库链接: `https://github.com/riceshowerX/astrbot_plugin_status`
2. 在 AstrBot WebUI 的 **插件管理 → 从链接安装** 中粘贴并安装

### 通过文件安装
1. 下载或克隆本仓库
2. 在 AstrBot WebUI 的 **插件管理 → 从文件安装** 中选择项目文件夹

## ⚙️ 配置说明

### 基本配置
| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `privacy_level` | string | `full` | 隐私级别: `full`(完整) 或 `minimal`(最小) |
| `cache_duration` | int | `10` | 缓存时间(秒)，0表示禁用缓存 |
| `collect_timeout` | int | `25` | 采集超时时间(秒) |
| `show_temp` | bool | `true` | 是否显示CPU温度 |

### 磁盘监控配置
| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `disk_paths` | list | `[]` | 要监控的磁盘路径列表 |

### 配置示例

```json
{
  "privacy_level": "minimal",
  "cache_duration": 15,
  "collect_timeout": 30,
  "show_temp": true,
  "disk_paths": [
    "/data",
    {"path": "/var/log", "display": "日志存储"},
    {"path": "/home", "display": "用户数据"}
  ]
}
```

## 🎯 使用方法

### 基本命令
- `/status` - 获取服务器状态
- `状态` / `zt` / `s` - 命令别名

### 高级用法
- `/status 刷新` - 强制重新采集数据（绕过缓存）
- `/status_help` - 显示帮助信息

### 输出示例

**完整模式 (privacy_level: full):**
```markdown
💻 **服务器实时状态**

⚠️ **在容器中运行, 指标可能仅反映容器限制。**

────────────────────────
⏱️ **系统稳定运行**: 3天 2小时 15分钟
────────────────────────
🖥️ **CPU**
   - 使用率: 25.4%
   - 温度: 45.2°C
────────────────────────
💾 **内存**
   - 使用率: 62.3%
   - 已使用: 8.2GB / 16.0GB
────────────────────────
💿 **磁盘 (/data)**
   - 使用率: 45.2%
   - 已使用: 225GB / 500GB
────────────────────────
💿 **磁盘 (日志存储)**
   - 使用率: 12.1%
   - 已使用: 12GB / 100GB
────────────────────────
🌐 **网络I/O (自进程启动后总计)**
   - 总上传: 2.1GB
   - 总下载: 5.4GB
────────────────────────
📅 **数据更新时间**: 2024-01-15 14:30:25
```

**最小化模式 (privacy_level: minimal):**
```markdown
💻 **服务器实时状态**

────────────────────────
🖥️ **CPU**: 25.4%
────────────────────────
💾 **内存**: 62.3%
────────────────────────
💿 **磁盘 (/data)**: 45.2%
────────────────────────
💿 **磁盘 (日志存储)**: 12.1%
────────────────────────
📅 **数据更新时间**: 2024-01-15 14:30:25
```

## 🛠️ 开发指南

### 项目结构
```
astrbot_plugin_status/
├── main.py              # 主插件文件（单文件架构）
├── _conf_schema.json   # 配置架构定义
├── metadata.yaml       # 插件元数据
├── requirements.txt    # Python依赖项
├── README.md          # 项目文档
└── LICENSE            # 开源许可证
```

### 架构说明
插件采用单文件架构，内部通过类实现模块化：
- **MetricsCollector** - 系统指标采集器
- **MetricsFormatter** - 数据格式化器  
- **ServerStatusPlugin** - 主插件类

### 扩展开发
要添加新的监控指标：

1. 在 `MetricsCollector` 类中添加数据采集方法
2. 在 `MetricsFormatter` 类中添加格式化逻辑
3. 更新配置验证和默认值

### 代码质量
- 遵循 PEP 8 代码风格规范
- 完整的类型注解支持
- 详细的错误处理和日志记录
- 严格的输入验证和安全检查

## 🔒 安全建议

### 生产环境配置
1. **限制访问权限**: 确保status命令有严格的ACL控制
2. **启用隐私模式**: 在公共群组使用 `privacy_level: minimal`
3. **路径安全检查**: 只监控安全的系统路径
4. **监控资源使用**: 定期检查插件性能和资源消耗

### 安全配置示例
```json
{
  "privacy_level": "minimal",
  "cache_duration": 30,
  "collect_timeout": 25,
  "show_temp": false,
  "disk_paths": [
    {"path": "/app/data", "display": "应用数据"},
    {"path": "/app/logs", "display": "日志文件"}
  ]
}
```

## 📊 性能指标

### 资源消耗
- **内存使用**: ~5-15MB (轻量级设计)
- **CPU占用**: <1% (采集期间短暂峰值)
- **网络流量**: 可忽略不计

### 采集时间
- **首次采集**: 1-2秒
- **缓存命中**: <50ms
- **超时设置**: 建议25秒

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request!

1. Fork 本仓库
2. 创建特性分支: `git checkout -b feature/new-feature`
3. 提交更改: `git commit -am 'Add new feature'`
4. 推送分支: `git push origin feature/new-feature`
5. 创建 Pull Request

### 开发规范
- 遵循 PEP 8 代码风格规范
- 添加完整的类型注解
- 编写详细的文档说明
- 保持向后兼容性

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。

## 🆘 技术支持

- 📖 [查看文档](README.md)
- 🐛 [提交Issue](https://github.com/riceshowerX/astrbot_plugin_status/issues)
- 💬 [讨论区](https://github.com/riceshowerX/astrbot_plugin_status/discussions)

---

**温馨提示**: 在生产环境使用前，请务必测试所有功能并配置适当的安全策略。
