
# AstrBot 服务器状态插件 (astrabot_plugin_status)

![Version](https://img.shields.io/badge/version-v1.0-blue) ![Python](https://img.shields.io/badge/python-3.9+-blue.svg) ![Author](https://img.shields.io/badge/author-riceshowerx-green) ![License](https://img.shields.io/badge/license-MIT-lightgrey)

> **项目地址:** [**github.com/riceshowerX/astrbot_plugin_status**](https://github.com/riceshowerX/astrbot_plugin_status)

一个为 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 打造的，简洁、可靠且注重隐私的服务器状态查询插件。

希望这个小工具能帮助你更方便地了解你的服务器状态。

---

## 📖 简介

这个插件允许你通过一个简单的命令，来获取运行 AstrBot 的服务器的核心性能指标，比如 CPU、内存、磁盘使用情况等。

## ✨ 主要特点

这个插件在设计时考虑了几个方面，希望能让它足够好用：

*   **注重安全与隐私**:
    *   **隐私模式**: 你可以通过配置开启“最小模式”(`minimal`)，在公共群组中隐藏详细路径、资源总量等敏感信息。
    *   **路径别名**: 支持为你的磁盘路径设置一个别名，避免直接暴露服务器的真实目录结构。
    *   **安全检查**: 会对配置的路径进行基本的安全检查，防止不正确的配置。

*   **稳定可靠**:
    *   **容错设计**: 即使部分指标（比如某个磁盘、CPU温度）获取失败，插件也不会崩溃，而是会继续展示它能获取到的其余正常数据，并给出提示。
    *   **超时保护**: 内置了超时机制，防止因为系统某个部分响应缓慢而卡住整个机器人。

*   **轻量高效**:
    *   **异步采集**: 采用异步方式获取系统数据，不会阻塞或影响机器人对其他命令的响应。
    *   **查询缓存**: 对短时间内的重复查询使用了缓存，可以减少不必要的系统开销。

---

## ⚙️ 安装指南

> **提示**：本插件需要 **Python 3.9 或更高版本**。

1.  **通过链接安装 (推荐)**
    *   复制本插件的仓库链接：`https://github.com/riceshowerX/astrbot_plugin_status`
    *   在 AstrBot WebUI 的 **插件管理 → 从链接安装** 中粘贴并安装。

2.  **通过文件安装**
    *   在 [**Releases**](https://github.com/riceshowerX/astrbot_plugin_status/releases) 页面下载最新的 `.zip` 压缩包。
    *   在 AstrBot WebUI 的 **插件管理 → 从文件安装** 中上传并安装。

安装完成后，记得到插件列表中**启用**它。

---

## 🔧 插件配置

你可以在插件管理页面找到这个插件并进行配置。

*   **`隐私级别 (privacy_level)`**
    *   功能: 控制信息的详细程度。`full` 显示全部；`minimal` 隐藏敏感数据。
    *   建议: 在公共群组中，推荐使用 `minimal` 模式来保护服务器隐私。
    *   默认: `full`

*   **`要监控的磁盘路径列表 (disk_paths)`**
    *   功能: 指定要监控的磁盘路径。可以只是一个路径字符串，也可以是带别名的对象。
    *   示例: `["/data", {"path": "/var/log", "display": "日志"}]`
    *   建议: 如果服务器磁盘较多或有网络挂载，最好在这里明确指定要监控的路径。

*   **`采集超时时间 (collect_timeout)`**
    *   功能: 数据采集的最长等待时间（秒）。
    *   默认: `25`

*   **`缓存时间 (cache_duration)`**
    *   功能: 查询结果的缓存时间（秒）。
    *   默认: `10`

*   **`是否显示CPU温度 (show_temp)`**
    *   功能: 是否尝试显示CPU温度。如果你的硬件不支持，它会自动隐藏。
    *   默认: `true`

---

## 🚀 如何使用

启用后，发送以下任意指令即可：

- `/status`
- `服务器状态`
- `状态`
- `zt`
- `s`

### 📊 示例输出

通常情况下，你会看到这样的报告：

<img width="600" height="720" alt="插件输出效果图" src="https://github.com/user-attachments/assets/657b4f0a-4176-43c1-b459-1efc5f4587d5" />

如果某个组件（比如温度传感器）出现问题，插件会尝试像这样反馈：

> ```
> 💻 **服务器实时状态**
> --------------------
> 🖥️ **CPU**
>    - 使用率: 25.4%
> --------------------
> ... (其他正常信息) ...
> --------------------
> ⚠️ **注意: 部分指标采集失败 (CPU Temp Failed)**
> ```

---

## 📦 依赖项

*   **Python**: `3.9+`
*   **第三方库**: `psutil` (AstrBot 会自动安装)

---

## 欢迎参与 (Contributions Welcome)

这是一个开源项目，欢迎任何形式的贡献！无论是提交问题 (Issue)、修复 Bug 还是提出新功能建议，我们都非常欢迎。你可以通过以下方式参与：

1.  **Fork** 本仓库。
2.  创建你的新分支。
3.  提交你的更改。
4.  **创建 Pull Request**。

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 开源。
