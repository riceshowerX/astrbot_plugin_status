# AstrBot 服务器状态插件 (astrabot_plugin_status)

![Version](https://img.shields.io/badge/version-v1.3-blue)
![Author](https://img.shields.io/badge/author-riceshowerx-green)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

一个为 [AstrBot](https://github.com/Soulter/AstrBot) 设计的实用插件，用于实时查询并显示机器人所在服务器的系统状态。

**仓库地址:** [https://github.com/riceshowerX/astrabot_plugin_status](https://github.com/riceshowerX/astrbot_plugin_status)

## 📖 简介

`astrabot_plugin_status` 允许用户通过简单的聊天指令，快速获取运行 AstrBot 的服务器的各项关键性能指标。这对于需要随时监控服务器健康状况的管理员来说非常方便，无需登录服务器，即可在聊天窗口中一目了然。

## ✨ 功能特性

- **全面的状态监控**:
  - **CPU**: 实时使用率和核心温度 (仅限部分Linux系统)。
  - **内存**: 已用/总内存及使用百分比。
  - **磁盘**: 根目录的已用/总空间及使用百分比。
  - **网络**: 开机至今的总上传与下载流量。
  - **运行时间**: 服务器自开机以来的稳定运行时间。
- **跨平台支持**: 能够良好地运行在 Windows 和 Linux 系统上，并能自动处理平台差异。
- **易于使用**: 支持多个别名指令，查询方便快捷。
- **健壮稳定**: 包含完善的错误处理，即使部分信息获取失败（如温度），插件也不会崩溃。
- **轻量高效**: 依赖 `psutil` 库，资源占用低，并通过异步执行避免阻塞 AstrBot 主程序。

## ⚙️ 安装指南

请选择以下任一方式进行安装。

### 方式一：使用 Git 克隆 (推荐)

这是最推荐的安装方式，方便后续更新。

1.  打开终端 (Terminal / CMD)。
2.  使用 `cd` 命令进入 AstrBot 的 `plugins` 目录。
3.  运行以下命令克隆仓库：
    ```bash
    git clone https://github.com/riceshowerX/astrabot_plugin_status.git
    ```
4.  重启 AstrBot。AstrBot 会自动检测 `requirements.txt` 并安装所需的 `psutil` 依赖。

### 方式二：手动下载

1.  访问本插件的 GitHub 仓库页面。
2.  点击右上角的 `Code` 按钮，然后选择 `Download ZIP`。
3.  解压下载的 ZIP 文件，将其中的文件夹（应名为 `astrabot_plugin_status-main` 或类似）重命名为 `astrabot_plugin_status`。
4.  将该文件夹完整地移动到 AstrBot 的 `plugins` 目录中。
5.  **手动安装依赖**：打开终端，运行以下命令：
    ```bash
    pip install psutil
    ```
6.  重启 AstrBot 或在 WebUI 中重载插件。

## 🚀 使用方法

安装并启用插件后，在任何已接入 AstrBot 的聊天窗口中，发送以下任意指令即可：

- `/status`
- `服务器状态`
- `状态`
- `zt`
- `s`

### 示例输出

机器人将会回复类似下面的格式化消息：

```
💻 **服务器实时状态** 💻
--------------------
⏱️ **已稳定运行**: 15天 8小时 22分钟
--------------------
🖥️ **CPU**
   - **使用率**: 12.5%
   - **核心温度**: 45.0°C
--------------------
💾 **内存**
   - **使用率**: 35.8%
   - **已使用**: 5.72 GB / 15.98 GB
--------------------
💿 **磁盘 (/)**
   - **使用率**: 60.2%
   - **已使用**: 27.98 GB / 46.51 GB
--------------------
🌐 **网络I/O (自启动)**
   - **总上传**: 120.75 GB
   - **总下载**: 1.25 TB
```
*(注意：CPU温度仅在部分受支持的Linux系统上显示)*

## 📦 依赖

本插件仅依赖一个第三方库：

- **psutil**: 一个跨平台的进程和系统利用率库。

依赖已在 `requirements.txt` 中声明，AstrBot 会在加载插件时尝试自动安装。

## 📝 贡献

欢迎任何形式的贡献！无论是提交 Issue、发起 Pull Request，还是提出改进建议。

1.  Fork 本仓库
2.  创建您的特性分支 (`git checkout -b feature/AmazingFeature`)
3.  提交您的更改 (`git commit -m 'Add some AmazingFeature'`)
4.  推送到分支 (`git push origin feature/AmazingFeature`)
5.  开启一个 Pull Request

## 📄 许可证

本项目使用 [MIT License](LICENSE) 开源。
