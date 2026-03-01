# OpenClaw 企微桥接插件

版本: V26030101

## 功能

- 企微 <-> OpenClaw 双向消息桥接
- 支持文本、图片、视频、语音、文件消息
- 语音识别 (Sherpa-ONNX + Whisper)
- 定向回复 (非 owner 用户抄送 owner)
- 媒体文件通过 multipart/form-data 上传

## 安装

1. 解压插件到 OpenClaw 的 skills 目录
2. 运行安装脚本: `python install.py`
3. 配置 `config.json`
4. 启动桥接器: `python wecom_to_openclaw_bridge.py`

## 配置

编辑 `config.json`:

```json
{
  "api_key": "YOUR_SILLYMD_API_KEY",
  "wechat": {
    "owner_id": "YOUR_WECHAT_OWNER_ID"
  }
}
```

**必要配置项:**
- `api_key`: 从 SillyMD 获取的 API key
- `wechat.owner_id`: 企微 owner 的 ID (接收抄送消息)

**自动生成项 (无需手动配置):**
- JWT token - 通过 api_key 自动获取
- Tenant ID / Device ID - 通过登录自动获取
- 企微配置 (token, corp_id 等) - 从后端自动获取
- OpenClaw 会话 - 自动创建

## 目录结构

```
├── wecom_to_openclaw_bridge.py  # 主程序
├── server_connector.py          # 服务器连接
├── config_manager.py            # 配置管理
├── voice_recognition.py         # 语音识别
├── asr_sherpa_onnx.py           # Sherpa-ONNX ASR
├── wechat_crypto.py             # 加密/解密
├── openclaw_session.py          # OpenClaw 会话
├── openclaw_send_file.py        # 文件发送工具
├── logging_config.py            # 日志配置
├── install.py                   # 安装脚本
├── config.json                  # 配置文件
└── requirements.txt             # 依赖列表
```

## 注意事项

- 首次启动时会自动生成完整配置
- 日志文件保存在 `logs/` 目录
- 接收的媒体文件保存在 `file/` 目录
