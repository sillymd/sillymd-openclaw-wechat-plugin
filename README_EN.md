# SillyMD OpenClaw-WeChat Plugin

A bidirectional message bridge between WeCom (Enterprise WeChat) and OpenClaw, supporting local voice recognition and multimedia messaging.

[![Release](https://img.shields.io/github/v/release/sillymd/sillymd-openclaw-wechat-plugin)](https://github.com/sillymd/sillymd-openclaw-wechat-plugin/releases)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Repository Mirrors:** [GitHub](https://github.com/sillymd/sillymd-openclaw-wechat-plugin) | [Gitee](https://gitee.com/sillymd/sillymd-openclaw-wechat-plugin)

## Features

- **Bidirectional Message Sync**: Real-time messaging between WeCom and OpenClaw
- **Local Voice Recognition**: Built-in Sherpa-ONNX and Whisper, works offline
- **Multimedia Support**: Text, image, video, voice, and file messages
- **Simplified Configuration**: Only requires api_key and owner_id, other configs auto-fetched
- **Smart CC**: Auto-CC owner when non-owner users ask questions
- **File Transfer**: Send media files via SillyMD
- **Offline Installation**: Includes all dependency wheels, no internet required

## System Requirements

- Python 3.8+
- Windows/Linux/macOS
- Memory: At least 4GB (8GB recommended)
- Disk: At least 1GB free space

## Quick Start

### Method 1: npm Installation (Recommended)

```bash
# Install globally (auto-downloads models and wheels)
npm install -g sillymd-wechat

# Configure (interactive)
sillymd-wechat check

# Start the plugin
sillymd-wechat start
```

### Method 2: Manual Installation

```bash
# Clone repository (GitHub)
git clone https://github.com/sillymd/sillymd-openclaw-wechat-plugin.git
cd sillymd-openclaw-wechat-plugin

# Or clone from Gitee (China recommended)
git clone https://gitee.com/sillymd/sillymd-openclaw-wechat-plugin.git
cd sillymd-openclaw-wechat-plugin

# Install (auto-downloads models and wheels)
python install.py --skip

# Configure
sillymd-wechat check

# Start the plugin
python wecom_to_openclaw_bridge.py
```

### Configure the Plugin

Edit `config.json`, or use interactive configuration:

```bash
# Interactive configuration (can run separately)
sillymd-wechat check

# Or manually edit config.json
```

```json
{
  "api_key": "YOUR_SILLYMD_API_KEY",
  "wechat": {
    "owner_id": "YOUR_WECHAT_OWNER_ID"
  }
}
```

**Required Configuration:**
- `api_key`: Get from SillyMD - https://websocket.sillymd.com
- `wechat.owner_id`: WeCom owner ID (receives CC messages)

**Auto-fetched Configuration (no manual setup needed):**
- JWT Token - Auto-obtained via api_key login
- Tenant ID / Device ID - Auto-obtained after WebSocket connection
- WeCom config (token, corp_id, encoding_aes_key, etc.) - Auto-fetched from backend

### Start the Plugin

```bash
# Using npm command
sillymd-wechat start

# Or run Python directly
python wecom_to_openclaw_bridge.py
```

## Download & Installation

```bash
# Clone repository
git clone https://github.com/sillymd/sillymd-openclaw-wechat-plugin.git
# Or clone from Gitee (China recommended)
git clone https://gitee.com/sillymd/sillymd-openclaw-wechat-plugin.git

cd sillymd-openclaw-wechat-plugin

# Install (auto-downloads models and wheels)
python install.py --skip
```

> **Note**: Installation will download models and dependencies from https://resource.sillymd.com/sillyhub/

## Directory Structure

```
.
├── wecom_to_openclaw_bridge.py    # Main entry point
├── server_connector.py            # Server connector (WebSocket/HTTP)
├── config_manager.py              # Configuration management
├── wechat_crypto.py               # WeChat message encryption/decryption
├── voice_recognition.py           # Voice recognition module
├── asr_sherpa_onnx.py            # Sherpa-ONNX ASR
├── openclaw_session.py            # OpenClaw session management
├── openclaw_send_file.py          # File sending utility
├── logging_config.py              # Logging configuration
├── models_list.md                 # Model file list (auto-downloaded)
├── wheels_list.md                 # Dependencies list (auto-downloaded)
├── models/                        # Voice recognition models (auto-downloaded)
│   └── sherpa-onnx/ASR/          # Sherpa-ONNX model
├── wheels/                        # Python dependencies (auto-downloaded)
├── whisper_local/                 # Whisper local implementation
├── logs/                          # Log directory
├── file/                          # Received media files
├── config.json                    # Main config file
├── install.py                     # Installation script
├── bin/cli.js                    # npm CLI entry
├── PLUGIN.md                      # Plugin documentation
├── README.md                      # Chinese version
└── README_EN.md                   # English version
```

## Voice Recognition

The plugin uses **Sherpa-ONNX** for voice recognition by default:

1. **Sherpa-ONNX** (default): Local ONNX model, fast, supports Chinese and English
2. **Whisper** (backup): Local Whisper model, higher accuracy, multilingual support

Voice files are automatically converted from AMR to WAV format for processing.

## Configuration Guide

### Config File

The plugin uses minimal configuration, just create a `config.json` file:

```json
{
  "api_key": "YOUR_SILLYMD_API_KEY",
  "wechat": {
    "owner_id": "YOUR_WECHAT_OWNER_ID"
  }
}
```

### Configuration Options

| Option | Required | Description |
|--------|----------|-------------|
| `api_key` | ✅ | API Key from SillyMD console |
| `wechat.owner_id` | ✅ | WeCom owner ID (receives CC messages) |

### Auto-fetched Configuration

The following configs are automatically fetched from the backend API when the plugin starts and stored in memory:

| Option | Source | Usage |
|--------|--------|-------|
| `tenant_id` | API | Tenant unique identifier |
| `device_id` | WebSocket | Device identifier |
| `jwt_token` | API | WebSocket authentication (not needed if using API Key directly) |
| `token` | API | WeCom message encryption token |
| `encoding_aes_key` | API | WeCom message encryption key |
| `corp_id` | API | WeCom CorpID |
| `corp_secret` | API | WeCom application secret |

**Security Note**: All sensitive configs (token, aes_key, corp_secret, etc.) are dynamically fetched from the backend and are NOT written to local config files, only stored in memory to prevent security risks from config file leaks.

### Environment Variables (Optional)

You can override configs via environment variables:

```bash
# Windows PowerShell
$env:SILLYMD_API_KEY="your_api_key"
$env:WECOM_OWNER_ID="YourName"

# Linux/Mac
export SILLYMD_API_KEY=your_api_key
export WECOM_OWNER_ID=YourName
```

## FAQ

### Q: Missing Microsoft Visual C++ when installing dependencies?
A: Install precompiled wheels from wheels/ directory:
```bash
pip install wheels/*.whl
```

### Q: Voice recognition fails?
A: Check if model files in models/ directory are complete, or check logs for errors.

### Q: Duplicate messages sent?
A: The plugin has built-in deduplication and automatically skips duplicate messages. To clear cache, delete `.processed_responses` file.

### Q: How to update configuration?
A: Modify `.env` file or corresponding JSON config file, then restart the plugin.

## Logs

Plugin logs are output to console by default, you can also check generated log files:

```bash
# View logs in real-time
tail -f wecom_bridge.log
```

## Architecture

```
┌─────────────┐      WebSocket       ┌─────────────┐
│   WeCom     │ ◄──────────────────► │ SillyMD Server│
└─────────────┘                      └─────────────┘
       │                                     │
       │         Webhook/Callback            │
       ▼                                     ▼
┌─────────────────────────────────────────────────┐
│          wecom_to_openclaw_bridge.py            │
│  ┌──────────────┐  ┌──────────────────────┐    │
│  │ wechat_crypto│  │ voice_recognition    │    │
│  │   Encryption │  │ Sherpa-ONNX/Whisper  │    │
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

## License

MIT License

## Support & Feedback

For issues, please submit an Issue or contact the developer.
