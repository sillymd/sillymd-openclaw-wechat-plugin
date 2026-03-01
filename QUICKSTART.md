# 快速开始指南

## 5分钟快速部署

### 1. 安装 (1分钟)

```bash
python install.py
```

### 2. 配置 (2分钟)

编辑 `.env` 文件：

```bash
# SillyMD 配置
SILLYMD_BASE_URL=https://your-server.com
SILLYMD_TENANT_ID=xxx
SILLYMD_DEVICE_NAME=OpenClaw

# 企业微信配置
WECOM_CORP_ID=xxx
WECOM_AGENT_ID=xxx
WECOM_SECRET=xxx
WECOM_TOKEN=xxx
WECOM_ENCODING_AES_KEY=xxx
```

### 3. 启动 (1分钟)

```bash
python wecom_to_openclaw_bridge.py
```

看到以下输出表示成功：

```
============================================================
企业微信 <-> OpenClaw 双向消息桥接器
============================================================
Session ID: xxx
SillyMD 连接成功，等待消息...
```

## 测试

1. **发送文本消息**到企业微信应用
2. **发送语音消息**测试语音识别
3. 查看 OpenClaw 会话中的响应

## 常见问题

**Q: 安装失败？**
```bash
# 手动安装依赖
pip install wheels/*.whl
pip install -r requirements.txt
```

**Q: 启动失败？**
- 检查 `.env` 配置是否正确
- 检查模型文件是否存在 `models/`

**Q: 语音识别失败？**
- 检查 `models/sherpa-onnx/ASR/` 目录
- 查看日志输出了解详情

## 目录说明

| 目录/文件 | 用途 |
|-----------|------|
| `wecom_to_openclaw_bridge.py` | 主程序 |
| `models/` | 语音识别模型 (306MB) |
| `wheels/` | 离线依赖包 (364MB) |
| `whisper_local/` | Whisper 实现 (2MB) |
| `tmp/` | 开发测试文件备份 |

## 技术支持

- 完整文档: [README.md](README.md)
- 安装脚本: [install.py](install.py)
