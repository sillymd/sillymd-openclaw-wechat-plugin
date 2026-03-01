"""
OpenClaw Session 客户端
使用 WebSocket 发送消息
"""
import asyncio
import websockets
import json
import logging
from typing import Optional, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class OpenClawSessionClient:
    """OpenClaw Session 客户端 - WebSocket 实现"""

    def __init__(
        self,
        gateway_url: str = "ws://127.0.0.1:18789/ws",
        api_token: str = "jcoding"
    ):
        """
        初始化客户端

        Args:
            gateway_url: OpenClaw Gateway WebSocket URL
            api_token: API Token
        """
        self.gateway_url = gateway_url
        self.api_token = api_token
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False

    async def connect(self) -> bool:
        """连接到 OpenClaw Gateway"""
        try:
            logger.info(f"正在连接到 {self.gateway_url}...")
            self.websocket = await websockets.connect(self.gateway_url)
            self.is_connected = True
            logger.info("WebSocket 连接成功")
            return True
        except Exception as e:
            logger.error(f"连接失败: {e}")
            return False

    async def send_message(
        self,
        session_key: str,
        message: str,
        message_type: str = "text",
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        发送消息到 session

        Args:
            session_key: OpenClaw session key
            message: 消息内容
            message_type: 消息类型
            metadata: 额外数据

        Returns:
            Dict: 发送结果
        """
        if not self.is_connected or not self.websocket:
            success = await self.connect()
            if not success:
                return {
                    "success": False,
                    "error": "无法连接到 Gateway",
                    "message": "连接失败"
                }

        try:
            data = {
                "action": "send_to_session",
                "session_key": session_key,
                "message": message,
                "message_type": message_type,
                "api_token": self.api_token,
                "timestamp": datetime.now().isoformat()
            }

            if metadata:
                data["metadata"] = metadata

            await self.websocket.send(json.dumps(data))
            logger.info(f"消息已发送到 session: {session_key}")
            return {
                "success": True,
                "message": "消息发送成功",
                "sent_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"发送失败: {e}")
            self.is_connected = False
            return {
                "success": False,
                "error": str(e),
                "message": "发送失败"
            }

    async def send_notification(
        self,
        session_key: str,
        title: str,
        content: str,
        icon: Optional[str] = None
    ) -> Dict:
        """发送通知到 session"""
        message = f"{title}\n\n{content}"

        return await self.send_message(
            session_key=session_key,
            message=message,
            message_type="notification",
            metadata={"icon": icon} if icon else None
        )

    async def close(self):
        """关闭客户端"""
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
            logger.info("WebSocket 连接已关闭")


# 便捷函数

async def create_session_client(
    gateway_url: str = "ws://127.0.0.1:18789/ws",
    api_token: str = "jcoding"
) -> OpenClawSessionClient:
    """
    创建 Session 客户端

    Args:
        gateway_url: OpenClaw Gateway WebSocket URL
        api_token: API Token

    Returns:
        OpenClawSessionClient: 客户端实例
    """
    return OpenClawSessionClient(
        gateway_url=gateway_url,
        api_token=api_token
    )


async def send_to_openclaw(
    message: str,
    session_key: str,
    gateway_url: str = "ws://127.0.0.1:18789/ws",
    api_token: str = "jcoding"
) -> Dict:
    """
    发送消息到 OpenClaw（便捷函数）

    Args:
        message: 消息内容
        session_key: OpenClaw session key
        gateway_url: Gateway WebSocket URL
        api_token: API Token

    Returns:
        Dict: 发送结果
    """
    client = OpenClawSessionClient(
        gateway_url=gateway_url,
        api_token=api_token
    )

    try:
        success = await client.connect()
        if not success:
            return {
                "success": False,
                "error": "连接失败"
            }

        result = await client.send_message(
            session_key=session_key,
            message=message
        )
        await client.close()
        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
