#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenClaw 发送文件到企微的工具
用法: python openclaw_send_file.py <file_path> [message]
"""
import asyncio
import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server_connector import ServerConnector
from config_manager import ConfigManager

async def send_file(file_path: str, message: str = "", touser: str = None):
    """发送文件到企微

    Args:
        file_path: 文件路径
        message: 消息内容
        touser: 目标用户ID，多个用户用 | 分隔，默认从配置文件获取 owner_id
    """
    if not os.path.exists(file_path):
        print(f"错误: 文件不存在 {file_path}")
        return False

    config = ConfigManager().load_server_config()
    connector = ServerConnector(
        api_key=config.api_key,
        base_url=config.base_url,
        device_id=config.device_id,
        tenant_id=config.tenant_id,
        jwt_token=config.jwt_token
    )

    connector.wechat_config = config.wechat

    # 如果没有指定目标用户，使用配置中的 owner_id
    if not touser:
        touser = config.wechat.get('owner_id', '@all') if hasattr(config, 'wechat') else '@all'
        if not touser:
            touser = '@all'

    try:
        # 根据文件扩展名判断类型
        ext = os.path.splitext(file_path)[1].lower()

        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
            # 图片
            result = await connector.send_media_to_wechat(
                media_type="image",
                file_path=file_path,
                message=message or "图片消息",
                touser=touser
            )
        elif ext in ['.mp4', '.avi', '.mov', '.mkv', '.flv']:
            # 视频
            result = await connector.send_media_to_wechat(
                media_type="video",
                file_path=file_path,
                message=message or "视频消息",
                title=os.path.basename(file_path),
                description=message,
                touser=touser
            )
        elif ext in ['.amr', '.wav', '.mp3']:
            # 语音 - 作为文件发送
            result = await connector.send_file_to_wechat(
                file_path=file_path,
                file_name=os.path.basename(file_path),
                message=message or "语音消息",
                touser=touser
            )
        else:
            # 其他文件
            result = await connector.send_file_to_wechat(
                file_path=file_path,
                file_name=os.path.basename(file_path),
                message=message,
                touser=touser
            )

        if result.get('status') == 'success':
            print(f"[OK] 文件发送成功: {result.get('msg_id')}")
            return True
        else:
            print(f"[FAIL] 文件发送失败: {result}")
            return False

    except Exception as e:
        print(f"[ERROR] 发送异常: {e}")
        return False
    finally:
        await connector.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python openclaw_send_file.py <file_path> [message] [touser]")
        print("示例:")
        print("  python openclaw_send_file.py file/test.jpg")
        print("  python openclaw_send_file.py file/test.mp4 \"这是视频\"")
        print("  python openclaw_send_file.py file/test.mp4 \"这是视频\" \"HughWang|OwnerID\"")
        sys.exit(1)

    file_path = sys.argv[1]
    message = sys.argv[2] if len(sys.argv) > 2 else ""
    touser = sys.argv[3] if len(sys.argv) > 3 else None

    success = asyncio.run(send_file(file_path, message, touser))
    sys.exit(0 if success else 1)
