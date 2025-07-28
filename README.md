

#  AstrBot 服务器状态插件 (astrabot_plugin_status)

![Version](https://img.shields.io/badge/version-v1.0-blueviolet)![Author](https://img.shields.io/badge/author-riceshowerx-green)![Python](https://img.shields.io/badge/python-3.9+-blue.svg)![License](https://img.shields.io/badge/license-MIT-lightgrey)

> **项目地址:** [**github.com/riceshowerX/astrbot_plugin_status**](https://github.com/riceshowerX/astrbot_plugin_status)

一个为 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 精心打造的服务器状态查询插件。此版本经过全面重构，以**稳定性**、**可维护性**和**高性能**为核心目标，为您提供清晰、迅捷的服务器状态报告。

---

## 📖 简介

`astrabot_plugin_status` 允许您和您的用户通过简单的聊天指令，即时获取运行 AstrBot 的服务器的核心性能指标。无论是检查 CPU 负载还是监控磁盘空间，一切尽在掌握。

---

## ✨ 核心特性

- **🚀 高效响应缓存**
  - 短时间内（默认 5 秒）的连续请求将直接返回缓存结果，极大降低服务器负载，实现毫秒级响应。

- **📊 全面状态监控**
  - **CPU**: 实时使用率与核心温度（兼容主流 Linux 系统及部分硬件）。
  - **内存**: 已用/总内存及精准的百分比展示。
  - **网络**: 服务器自启动以来的累计上传与下载流量。
  - **磁盘**: 智能发现所有物理分区，或根据您的配置进行监控。
  - **运行时间**: 系统自开机以来的稳定运行时长，一目了然。

- **🧠 智能与健壮**
  - **智能磁盘发现**: 优先使用用户配置的路径，若未配置则自动扫描并展示所有物理磁盘。
  - **结构化设计**: 代码逻辑清晰分层，易于理解和二次开发。
  - **强大的错误处理**: 精准捕获常见异常，并在获取失败时向用户返回明确提示，杜绝静默崩溃。

- **🍃 轻量无阻塞**
  - 仅依赖 `psutil` 库，通过 `asyncio.to_thread` 异步采集数据，完全不影响 AstrBot 主程序的事件循环。

---

## ⚙️ 安装指南

> **重要提示**：本插件要求 **Python 3.9 或更高版本**。在安装前，请确保您的运行环境满足此要求。

### 方式一：🔗 通过链接安装 (推荐)

1.  **复制** 本插件的仓库链接：
    ```
    https://github.com/riceshowerX/astrbot_plugin_status
    ```
2.  **登录** AstrBot WebUI 管理界面。
3.  进入 **插件管理** → **从链接安装**。
4.  **粘贴** 上述链接并点击“安装”。
5.  安装成功后，在插件列表中**启用**本插件即可。

### 方式二：📁 通过文件安装

此方式适用于无法直接访问 GitHub 或需要安装特定版本的场景。

1.  前往本项目的 [**Releases**](https://github.com/riceshowerX/astrbot_plugin_status/releases) 页面，下载最新版或指定版本的 `.zip` 压缩包。
2.  **登录** AstrBot WebUI 管理界面。
3.  进入 **插件管理** → **从文件安装**。
4.  **上传** 您刚刚下载的 `.zip` 文件。
5.  安装完成后，在插件列表中**启用**即可。

---

## 🔧 插件配置

安装并启用插件后，您可以在 **插件管理** 页面找到本插件，点击“管理”按钮进入配置界面。

- **`要监控的磁盘路径列表 (disk_paths)`**
  - **功能**: 指定您希望监控的磁盘分区。
  - **格式**: JSON 格式的字符串列表。例如 `["/"]` (Linux) 或 `["C:\\", "D:\\"]` (Windows)。
  - **默认**: 若留空，插件将自动扫描并显示所有物理磁盘分区。

- **`是否显示CPU温度 (show_temp)`**
  - **功能**: 控制是否在状态报告中包含 CPU 温度信息。
  - **注意**: 此功能仅在部分受支持的 Linux 系统/硬件上可用。若无法获取，该项会自动隐藏。

- **`缓存时间 (cache_duration)`**
  - **功能**: 设置状态查询结果的缓存有效时间（单位：秒）。
  - **默认**: `5` 秒。可根据您的使用频率和服务器性能适当调整。

---

## 🚀 如何使用

配置完成后，在任何接入了 AstrBot 的聊天平台，发送以下任意一个指令即可：

- `/status`
- `服务器状态`
- `状态`
- `zt`
- `s`

### 📊 示例输出

机器人将以清晰的卡片格式回复状态信息：

<img width="600" height="720" alt="插件输出效果图" src="https://github.com/user-attachments/assets/657b4f0a-4176-43c1-b459-1efc5f4587d5" />

---

## 📦 依赖项

- **Python**: `3.9+`
- **第三方库**: `psutil`

*所有依赖项均已在 `requirements.txt` 中声明，AstrBot 会在安装插件时自动处理。*

---

## 📝 如何贡献

我们欢迎任何形式的贡献，包括但不限于提交问题 (Issue)、发起拉取请求 (Pull Request) 或提出功能建议。

1.  **Fork** 本仓库。
2.  创建您的特性分支 (`git checkout -b feature/YourAmazingFeature`)。
3.  提交您的更改 (`git commit -m 'Add some AmazingFeature'`)。
4.  将分支推送到您的 Fork 仓库 (`git push origin feature/YourAmazingFeature`)。
5.  **创建 Pull Request** 等待合并。

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 进行开源。
