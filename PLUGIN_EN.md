# OpenClaw WeCom Bridge Plugin

Version: V26030101

## Features

- WeCom <-> OpenClaw bidirectional message bridge
- Support for text, image, video, voice, and file messages
- Voice recognition (Sherpa-ONNX + Whisper)
- Directed replies (non-owner users CC'd to owner)
- Media files uploaded via multipart/form-data

## Installation

1. Extract plugin to OpenClaw's skills directory
2. Run installation script: `python install.py`
3. Configure `config.json`
4. Start bridge: `python wecom_to_openclaw_bridge.py`

## Configuration

Edit `config.json`:

```json
{
  "api_key": "YOUR_SILLYMD_API_KEY",
  "wechat": {
    "owner_id": "YOUR_WECHAT_OWNER_ID"
  }
}
```

**Required Configuration:**
- `api_key`: API key from SillyMD
- `wechat.owner_id`: WeCom owner ID (receives CC messages)

**Auto-generated Items (no manual config needed):**
- JWT token - auto-obtained via api_key
- Tenant ID / Device ID - auto-obtained via login
- WeCom config (token, corp_id, etc.) - auto-fetched from backend
- OpenClaw sessions - auto-created

## Directory Structure

```
├── wecom_to_openclaw_bridge.py  # Main program
├── server_connector.py          # Server connection
├── config_manager.py            # Configuration management
├── voice_recognition.py         # Voice recognition
├── asr_sherpa_onnx.py           # Sherpa-ONNX ASR
├── wechat_crypto.py             # Encryption/Decryption
├── openclaw_session.py          # OpenClaw session
├── openclaw_send_file.py        # File sending utility
├── logging_config.py            # Logging configuration
├── install.py                   # Installation script
├── config.json                  # Configuration file
└── requirements.txt             # Dependencies
```

## Notes

- Full configuration is auto-generated on first start
- Log files are saved in `logs/` directory
- Received media files are saved in `file/` directory
