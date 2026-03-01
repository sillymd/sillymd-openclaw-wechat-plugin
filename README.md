# SillyMD OpenClaw-WeChat Plugin

企业微信与 OpenClaw 的双向消息桥接插件，支持本地语音识别和多媒体消息。

[![Release](https://img.shields.io/github/v/release/sillymd/sillymd-openclaw-wechat-plugin)](https://github.com/sillymd/sillymd-openclaw-wechat-plugin/releases)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**仓库镜像:** [GitHub](https://github.com/sillymd/sillymd-openclaw-wechat-plugin) | [Gitee](https://gitee.com/sillymd/sillymd-openclaw-wechat-plugin)

## 功能特性

- **双向消息同步**: 企业微信 ↔ OpenClaw 实时消息互通
- **本地语音识别**: 集成 Sherpa-ONNX 和 Whisper，无需联网即可识别语音
- **多媒体支持**: 文本、图片、视频、语音、文件消息
- **简化配置**: 仅需 api_key 和 owner_id，其他配置自动获取
- **智能抄送**: 非 owner 用户提问时自动抄送 owner
- **文件直传**: 支持通过 SillyMD 发送媒体文件
- **离线安装支持**: 包含所有依赖 wheels，无需外网即可安装
- **隐私保护**: **不获取 User ID**，避免后台数据规律泄露

## 系统要求

- Python 3.8+
- Windows/Linux/macOS
- 内存: 至少 4GB (推荐 8GB)
- 磁盘: 至少 1GB 可用空间

## 快速开始

### 1. 安装依赖

```bash
# 使用离线依赖包（推荐）
python install.py
```

### 2. 配置插件

编辑 `config.json`，仅需配置两项：

```json
{
  "api_key": "YOUR_SILLYMD_API_KEY",
  "wechat": {
    "owner_id": "YOUR_WECHAT_OWNER_ID"
  }
}
```

**必要配置:**
- `api_key`: 从 SillyMD 获取的 API Key - https://websocket.sillymd.com
- `wechat.owner_id`: 企微 owner 的 ID（接收抄送消息）

**自动获取的配置（无需手动设置）:**
- JWT Token - 通过 api_key 自动登录获取
- Tenant ID / Device ID - WebSocket 连接后自动获取
- 企微配置（token, corp_id, encoding_aes_key 等）- 从后端自动获取

### 3. 启动插件

```bash
python wecom_to_openclaw-wechat-plugin.py
```

## 下载安装

### 从 GitHub 下载（推荐）

```bash
git clone https://github.com/sillymd/sillymd-openclaw-wechat-plugin.git
cd sillymd-openclaw-wechat-plugin
```

从 [GitHub Releases](https://github.com/sillymd/sillymd-openclaw-wechat-plugin/releases) 下载：
- `models-v26030101.tar.gz` - 语音识别模型 (~282MB)
- `wheels-v26030101.tar.gz` - 离线依赖包 (~356MB)

### 从 Gitee 下载（国内镜像）

```bash
git clone https://gitee.com/sillymd/sillymd-openclaw-wechat-plugin.git
cd sillymd-openclaw-wechat-plugin
```

> **注意**：Gitee 免费版附件限制 100MB，模型和依赖包需从 GitHub Releases 下载。

## 目录结构

```
.
├── wecom_to_openclaw_bridge.py    # 主程序入口
├── server_connector.py            # 服务器连接器（WebSocket/HTTP）
├── config_manager.py              # 配置管理
├── wechat_crypto.py               # 微信消息加解密
├── voice_recognition.py           # 语音识别模块
├── asr_sherpa_onnx.py             # Sherpa-ONNX ASR
├── openclaw_session.py            # OpenClaw 会话管理
├── openclaw_send_file.py          # 文件发送工具
├── logging_config.py              # 日志配置
├── models/                        # 语音识别模型
│   ├── sherpa-onnx/ASR/          # Sherpa-ONNX 模型 (~234MB)
│   └── tiny.pt                   # Whisper tiny 模型 (~73MB)
├── wheels/                        # 离线依赖包 (~364MB)
├── whisper_local/                 # Whisper 本地实现
├── logs/                          # 日志目录
├── file/                          # 接收的媒体文件
├── config.json                    # 主配置文件（简化配置）
├── install.py                     # 安装脚本
├── PLUGIN.md                      # 插件说明
└── README.md                      # 本文件
```

## 语音识别说明

插件优先使用 **Sherpa-ONNX** 进行语音识别：

1. **Sherpa-ONNX** (默认): 本地 ONNX 模型，速度快，支持中英文
2. **Whisper** (备用): 本地 Whisper 模型，准确率高，多语言支持

语音文件会自动从 AMR 格式转换为 WAV 格式进行处理。

## 配置说明

### 配置文件

插件使用极简配置，只需创建 `config.json` 文件：

```json
{
  "api_key": "YOUR_SILLYMD_API_KEY",
  "wechat": {
    "owner_id": "YOUR_WECHAT_OWNER_ID"
  }
}
```

### 配置项说明

| 配置项 | 必填 | 说明 |
|--------|------|------|
| `api_key` | ✅ | 从 SillyMD 控制台获取的 API Key |
| `wechat.owner_id` | ✅ | 企业微信所有者 ID（接收抄送消息的目标用户）|

### 自动获取的配置

以下配置无需手动设置，插件启动时会自动从后端 API 获取并存储在内存中：

| 配置项 | 来源 | 用途 |
|--------|------|------|
| `tenant_id` | API 获取 | 租户唯一标识 |
| `device_id` | WebSocket 绑定 | 设备标识 |
| `jwt_token` | API 获取 | WebSocket 认证（如使用 API Key 直接连接则不需要）|
| `token` | API 获取 | 企业微信消息加解密 Token |
| `encoding_aes_key` | API 获取 | 企业微信消息加解密密钥 |
| `corp_id` | API 获取 | 企业微信 CorpID |
| `corp_secret` | API 获取 | 企业微信应用密钥 |

**安全说明**：所有敏感配置（token, aes_key, corp_secret 等）均从后端动态获取，**不会写入本地配置文件**，仅存储在内存中使用，避免配置文件泄露导致的安全风险。

### 环境变量（可选）

可通过环境变量覆盖配置：

```bash
# Windows PowerShell
$env:SILLYMD_API_KEY="your_api_key"
$env:WECOM_OWNER_ID="YourName"

# Linux/Mac
export SILLYMD_API_KEY=your_api_key
export WECOM_OWNER_ID=YourName
```

## 常见问题

### Q: 安装依赖时提示缺少 Microsoft Visual C++?
A: 从 wheels/ 目录安装预编译的依赖包：
```bash
pip install wheels/*.whl
```

### Q: 语音识别失败?
A: 检查 models/ 目录下模型文件是否完整，或查看日志了解具体错误。

### Q: 消息重复发送?
A: 插件已内置去重机制，会自动跳过重复消息。如需清理缓存，删除 `.processed_responses` 文件。

### Q: 如何更新配置?
A: 修改 `.env` 文件或对应的 JSON 配置文件，然后重启插件即可。

## 日志查看

插件运行日志默认输出到控制台，也可查看生成的日志文件：

```bash
# 实时查看日志
tail -f wecom_bridge.log
```

## 技术架构

```
┌─────────────┐      WebSocket       ┌─────────────┐
│   企业微信   │ ◄──────────────────► │ SillyMD 服务器│
└─────────────┘                      └─────────────┘
       │                                     │
       │         Webhook/回调                │
       ▼                                     ▼
┌─────────────────────────────────────────────────┐
│          wecom_to_openclaw_bridge.py            │
│  ┌──────────────┐  ┌──────────────────────┐    │
│  │ wechat_crypto│  │ voice_recognition    │    │
│  │   消息加解密  │  │ Sherpa-ONNX/Whisper │    │
│  └──────────────┘  └──────────────────────┘    │
└─────────────────────────────────────────────────┘
                        │
                        │ OpenClaw CLI
                        ▼
               ┌─────────────────┐
               │   OpenClaw      │
               │   AI Agent      │
               └─────────────────┘
```

## 许可证

MIT License

## 支持与反馈

如有问题，请提交 Issue 或联系开发者。
