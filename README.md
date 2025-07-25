# AstrBot 服务器状态插件 (astrabot_plugin_status)

![Version](https://img.shields.io/badge/version-v1.3-blue)
![Author](https://img.shields.io/badge/author-riceshowerx-green)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

一个为 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 设计的实用插件，用于实时查询并显示机器人所在服务器的系统状态，严格遵循 AstrBot 官方插件开发规范。

**仓库地址:** [https://github.com/riceshowerX/astrbot_plugin_status](https://github.com/riceshowerX/astrbot_plugin_status)

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
- **健壮稳定**: 包含完善的错误处理，即使部分信息获取失败（如温度），插件也不会崩溃，而是会向用户返回明确的错误提示。
- **轻量高效**: 依赖 `psutil` 库，并通过异步执行避免阻塞 AstrBot 主程序。

## ⚙️ 安装指南

请根据您的使用场景，在 AstrBot WebUI 中选择以下任一方式进行安装。

### 方式一：通过链接安装 (推荐)

这是最简单、最推荐的安装方式，可以确保您安装的是最新版本。

1.  复制本插件的仓库链接：
    ```
    https://github.com/riceshowerX/astrbot_plugin_status
    ```
2.  登录您的 AstrBot WebUI 管理界面。
3.  导航至 **插件管理** 页面。
4.  找到 **“从链接安装”** 功能入口。
5.  将复制的链接粘贴到输入框中，点击“安装”。
6.  AstrBot 将会自动完成下载、安装和依赖配置。安装完成后，启用插件即可使用。

### 方式二：通过文件安装

此方法适用于服务器无法直接访问 GitHub，或者需要安装特定版本插件的场景。

1.  访问本插件的 GitHub 仓库页面。
2.  点击右上角的 `Code` 按钮，然后选择 `Download ZIP`，将插件的压缩包下载到您的电脑上。
3.  登录您的 AstrBot WebUI 管理界面。
4.  导航至 **插件管理** 页面。
5.  找到 **“从文件安装”** 功能入口。
6.  选择您刚刚下载的 `.zip` 文件并上传。
7.  AstrBot 将自动解压并安装插件。安装完成后，启用插件即可使用。

---

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

依赖已在 `requirements.txt` 中声明，无论使用何种方式安装，AstrBot 都会尝试自动处理。

## 📝 贡献

欢迎任何形式的贡献！无论是提交 Issue、发起 Pull Request，还是提出改进建议。

1.  Fork 本仓库
2.  创建您的特性分支 (`git checkout -b feature/AmazingFeature`)
3.  提交您的更改 (`git commit -m 'Add some AmazingFeature'`)
4.  推送到分支 (`git push origin feature/AmazingFeature`)
5.  开启一个 Pull Request

## 📄 许可证

本项目使用 [MIT License](LICENSE) 开源。
