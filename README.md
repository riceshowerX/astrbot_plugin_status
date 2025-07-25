# AstrBot 服务器状态插件 (astrabot_plugin_status)

![Version](https://img.shields.io/badge/version-v3.1.1-blueviolet)
![Author](https://img.shields.io/badge/author-riceshowerx-green)
![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

一个为 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 设计的服务器状态查询插件。该插件经过重构，以稳定性、可维护性和性能为目标，提供清晰、快速的文本格式状态报告。

**仓库地址:** [https://github.com/riceshowerX/astrbot_plugin_status](https://github.com/riceshowerX/astrbot_plugin_status)

## 📖 简介

`astrabot_plugin_status` 允许用户通过简单的聊天指令，快速获取运行 AstrBot 的服务器的各项关键性能指标。V3.0+ 版本对插件进行了重构，采用了更清晰的模块化设计，并引入了缓存机制来提升响应性能。这些改进旨在提高代码的长期可维护性与稳定性。

## ✨ 功能特性

- **响应缓存**: 若在短时间内（默认为5秒）连续请求，将返回缓存结果，以有效降低服务器负载，并提升高频请求下的响应速度。
- **全面的状态监控**:
  - **CPU**: 实时使用率和核心温度。
  - **内存**: 已用/总内存及使用百分比。
  - **网络**: 开机至今的总上传与下载流量。
  - **运行时间**: 服务器自开机以来的稳定运行时间。
- **智能磁盘发现**: 优先使用用户配置的路径，若未配置则自动发现所有物理磁盘分区。
- **高度可配置**: 用户可在 WebUI 中配置监控的磁盘路径、是否显示温度等。
- **清晰的代码架构**: 插件内部逻辑分为数据采集、文本格式化和指令协调三个部分，使代码结构清晰，易于理解和后续的功能扩展。
- **稳健的错误处理**: 完善的错误处理机制确保核心指标获取失败时能向用户返回明确的错误提示，而不是静默失败或崩溃。
- **轻量高效**: 仅依赖 `psutil` 库，并通过 `asyncio.to_thread` 异步执行，避免阻塞 AstrBot 主程序。

## ⚙️ 安装指南

**重要提示**: 本插件 V3.0.0 及以上版本要求 **Python 3.9 或更高**。

请根据您的使用场景，在 AstrBot WebUI 中选择以下任一方式进行安装。

### 方式一：通过链接安装 (推荐)

1.  复制本插件的仓库链接：
    ```
    https://github.com/riceshowerX/astrbot_plugin_status
    ```
2.  登录您的 AstrBot WebUI 管理界面。
3.  导航至 **插件管理** 页面，找到 **“从链接安装”** 功能入口。
4.  将链接粘贴到输入框中，点击“安装”。
5.  安装完成后，在插件列表中启用即可使用。

### 方式二：通过文件安装

此方法适用于无法直接访问 GitHub 或需要安装特定版本的场景。

1.  从本仓库的 [Releases](https://github.com/riceshowerX/astrbot_plugin_status/releases) 页面下载对应版本的 `.zip` 压缩包。
2.  登录您的 AstrBot WebUI 管理界面。
3.  导航至 **插件管理** 页面，找到 **“从文件安装”** 功能入口。
4.  选择您下载的 `.zip` 文件并上传。
5.  安装完成后，在插件列表中启用即可。

---

## 🔧 插件配置

安装并启用插件后，您可以在 **插件管理** 页面找到本插件，点击 **管理** 进入配置界面。

可配置项如下：

- **`要监控的磁盘路径列表 (disk_paths)`**:
  - **功能**: 指定要监控的磁盘分区列表。
  - **格式**: 一个 JSON 格式的字符串列表，例如 `["/"]` 或 `["C:\\", "D:\\"]`。
  - **默认行为**: 如果此列表为空，插件将自动扫描并监控服务器上所有的物理磁盘分区。

- **`是否显示CPU温度 (show_temp)`**:
  - **功能**: 控制是否在状态报告中显示CPU温度。
  - **注意**: 此功能仅在部分受支持的Linux系统上有效。若无法获取到温度，即使开启此选项，也不会显示。

## 🚀 使用方法

配置完成后，在任何已接入 AstrBot 的聊天窗口中，发送以下任意指令即可：

- `/status`
- `服务器状态`
- `状态`
- `zt`
- `s`

### 示例输出

机器人将会回复类似下面的格式化消息：
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

- **Python**: `3.9+`
- **第三方库**: `psutil`

依赖已在 `requirements.txt` 中声明，AstrBot 会尝试自动安装。

## 📝 贡献

欢迎任何形式的贡献！无论是提交 Issue、发起 Pull Request，还是提出改进建议。

1.  Fork 本仓库
2.  创建您的特性分支 (`git checkout -b feature/AmazingFeature`)
3.  提交您的更改 (`git commit -m 'Add some AmazingFeature'`)
4.  推送到分支 (`git push origin feature/AmazingFeature`)
5.  开启一个 Pull Request

## 📄 许可证

本项目使用 [MIT License](LICENSE) 开源。
