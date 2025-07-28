# AstrBot 服务器状态插件 (astrabot_plugin_status)

![Version](https://img.shields.io/badge/version-v1.0-blueviolet)
![Author](https://img.shields.io/badge/author-riceshowerx-green)
![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

一个为 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 设计的服务器状态查询插件。该插件经过重构，以稳定性、可维护性和性能为目标，提供清晰、快速的文本格式状态报告。

**仓库地址:** [https://github.com/riceshowerX/astrbot_plugin_status](https://github.com/riceshowerX/astrbot_plugin_status)

## 📖 简介

`astrabot_plugin_status` 允许用户通过简单的聊天指令，快速获取运行 AstrBot 的服务器的各项关键性能指标。  
V3.0+ 版本对插件进行了重构，采用了更清晰的模块化设计，并引入了缓存机制来提升响应性能。3.1.3 及以上版本修复了插件属性注入时序导致的罕见兼容性问题，全面提升了健壮性和兼容性。

## ✨ 功能特性

- **响应缓存**：若在短时间内（默认为 5 秒）连续请求，将直接返回缓存结果，有效降低服务器负载并提升响应速度。
- **全面的状态监控**：
  - **CPU**：实时使用率和核心温度（兼容主流 Linux 及部分硬件）。
  - **内存**：已用/总内存及使用百分比。
  - **网络**：服务器自启动以来的总上传与下载流量。
  - **运行时间**：自开机以来的稳定运行时长。
- **智能磁盘发现**：优先使用用户配置路径，如未配置则自动发现所有物理磁盘分区。
- **高度可配置**：可在 WebUI 配置监控磁盘路径、是否显示温度、缓存时间等参数。
- **结构清晰**：采集、格式化、指令响应分层，便于理解和维护。
- **健壮的错误处理**：可捕获大部分常见异常，出现获取失败时会向用户返回明确提示，避免静默崩溃。
- **轻量高效**：仅依赖 `psutil`，通过 `asyncio.to_thread` 方式异步采集数据，完全不会阻塞主程序事件循环。

## ⚙️ 安装指南

**重要提示**：本插件 V3.0.0 及以上要求 **Python 3.9 或更高**，请确保您的环境满足要求。

### 方式一：通过链接安装（推荐）

1. 复制本插件的仓库链接：
    ```
    https://github.com/riceshowerX/astrbot_plugin_status
    ```
2. 登录 AstrBot WebUI 管理界面。
3. 进入 **插件管理**，选择“从链接安装”。
4. 粘贴上述链接，点击“安装”。
5. 安装完成后在插件列表中启用即可。

### 方式二：通过文件安装

适用于无法直接访问 GitHub 或需安装特定版本场景。

1. 前往 [Releases](https://github.com/riceshowerX/astrbot_plugin_status/releases) 页面，下载所需版本的 `.zip`。
2. 登录 AstrBot WebUI 管理界面。
3. 进入 **插件管理**，选择“从文件安装”。
4. 选择下载的 `.zip` 文件并上传。
5. 安装后在插件列表中启用即可。

---

## 🔧 插件配置

安装并启用插件后，可在 **插件管理** 页面点击本插件“管理”按钮进行配置。

可配置项如下：

- **`要监控的磁盘路径列表 (disk_paths)`**
  - 功能：指定要监控的磁盘分区列表。
  - 格式：JSON 字符串列表，如 `["/"]` 或 `["C:\\", "D:\\"]`。
  - 默认：如留空则自动扫描所有物理磁盘分区。

- **`是否显示CPU温度 (show_temp)`**
  - 功能：控制是否在状态报告中显示 CPU 温度。
  - 注意：仅部分受支持的 Linux 系统/硬件可用，无法获取时会自动隐藏。

- **`缓存时间 (cache_duration)`**
  - 功能：设置状态响应缓存的有效时间（单位：秒）。
  - 默认：5 秒，可根据需求调整。

## 🚀 使用方法

配置完成后，在任意已接入 AstrBot 的聊天窗口发送以下任意指令即可：

- `/status`
- `服务器状态`
- `状态`
- `zt`
- `s`

### 示例输出

机器人回复类似如下格式化消息：

```
💻 **服务器实时状态**
--------------------
⏱️ **已稳定运行**: 15天 8小时 22分钟
--------------------
🖥️ **CPU** (45.0°C)
   - **使用率**: 12.5%
--------------------
💾 **内存**
   - **使用率**: 35.8%
   - **已使用**: 5.72 GB / 15.98 GB
--------------------
💿 **磁盘 (/)**
   - **使用率**: 60.2%
   - **已使用**: 27.98 GB / 46.51 GB
--------------------
💿 **磁盘 (/home)**
   - **使用率**: 75.1%
   - **已使用**: 1.50 TB / 2.00 TB
--------------------
🌐 **网络I/O (自启动)**
   - **总上传**: 120.75 GB
   - **总下载**: 1.25 TB
```

## 📦 依赖

- **Python**：`3.9+`
- **第三方库**：`psutil`

依赖已在 `requirements.txt` 中声明，AstrBot 会自动尝试安装。

## 📝 贡献

欢迎任何形式的贡献！如提交 Issue、发起 Pull Request 或建议改进均可。

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📄 许可证

本项目使用 [MIT License](LICENSE) 开源。
