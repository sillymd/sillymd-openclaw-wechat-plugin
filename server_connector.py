# -*- coding: utf-8 -*-
"""
服务器端连接器 - WebSocket 实时推送
连接到 websocket.sillymd.com 的 WebSocket 服务
"""
import asyncio
import json
import logging
import os
from typing import Optional, Callable, Dict, Any
from datetime import datetime

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    websockets = None

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None

from logging_config import get_module_logger

logger = get_module_logger("server_connector")


class ServerConnector:
    """
    服务器端连接器
    支持 WebSocket 连接和 HTTP API 调用
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://websocket.sillymd.com",
        device_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        jwt_token: Optional[str] = None
    ):
        """
        初始化服务器连接器

        Args:
            api_key: API Key
            base_url: 服务器基础 URL
            device_id: 设备 ID (格式: user_id:tenant_id:device_name)
            tenant_id: 租户 ID
            jwt_token: JWT Token (用于WebSocket认证)
        """
        self.logger = logger
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.device_id = device_id
        self.tenant_id = tenant_id
        self.jwt_token = jwt_token

        # WebSocket URL
        ws_protocol = "wss" if base_url.startswith("https") else "ws"
        self.ws_url = f"{ws_protocol}://{base_url.split('://')[1]}/ws"

        # 连接状态
        self.ws_connection = None
        self.http_session = None
        self.connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5

        # 消息处理器
        self.message_handlers: list[Callable] = []

        # JWT Token 已在构造函数中设置

    async def get_http_session(self) -> 'aiohttp.ClientSession':
        """获取或创建 HTTP 会话"""
        if not AIOHTTP_AVAILABLE:
            raise ImportError("aiohttp 未安装，请运行: pip install aiohttp")

        if self.http_session is None or self.http_session.closed:
            headers = {
                "X-API-Key": self.api_key
                # 注意：不要在这里设置 Content-Type，让每次请求自行设置
            }
            if self.jwt_token:
                headers["Authorization"] = f"Bearer {self.jwt_token}"

            timeout = aiohttp.ClientTimeout(total=30)
            self.http_session = aiohttp.ClientSession(
                headers=headers,
                timeout=timeout
            )

        return self.http_session

    async def close_http_session(self):
        """关闭 HTTP 会话"""
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
            self.http_session = None

    def get_websocket_token(self) -> str:
        """
        获取 WebSocket 连接用的 token
        本系统直接使用 API Key 作为 token

        Returns:
            str: WebSocket token
        """
        return self.jwt_token or self.api_key

    async def fetch_tenant_info(self) -> Optional[dict]:
        """
        从后端获取租户信息（包含企业微信配置）
        使用 X-API-Key 进行认证

        Returns:
            dict: 租户信息，失败返回 None
        """
        try:
            session = await self.get_http_session()
            url = f"{self.base_url}/api/v1/tenants/me"

            self.logger.info("获取租户信息...")

            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    self.logger.info("租户信息获取成功")

                    # 构造企微配置
                    wechat_config = {
                        "token": data.get("wechat_token"),
                        "encoding_aes_key": data.get("wechat_aes_key"),
                        "corp_id": data.get("wechat_corp_id"),
                        "corp_secret": data.get("wechat_corp_secret"),
                        "push_target": data.get("wechat_push_target"),
                        "agent_id": data.get("wechat_agent_id"),
                    }

                    # 更新 connector 的 tenant_id
                    if data.get("id"):
                        self.tenant_id = str(data["id"])

                    return {
                        "id": data.get("id"),
                        "name": data.get("name"),
                        "wechat": wechat_config
                    }
                elif response.status == 401:
                    self.logger.error("API Key 无效或已过期")
                    return None
                else:
                    text = await response.text()
                    self.logger.error(f"获取租户信息失败: {response.status} - {text}")
                    return None

        except Exception as e:
            self.logger.error(f"获取租户信息请求失败: {e}")
            return None

    def add_message_handler(self, handler: Callable):
        """
        添加消息处理器

        Args:
            handler: 消息处理函数，接收一个参数 (message: dict)
        """
        self.message_handlers.append(handler)
        self.logger.info(f"已添加消息处理器: {handler.__name__}")

    def remove_message_handler(self, handler: Callable):
        """
        移除消息处理器

        Args:
            handler: 消息处理函数
        """
        if handler in self.message_handlers:
            self.message_handlers.remove(handler)
            self.logger.info(f"已移除消息处理器: {handler.__name__}")

    async def handle_message(self, message: dict):
        """
        处理接收到的消息

        Args:
            message: 消息字典
        """
        self.logger.info(f"收到消息: {message.get('type', 'unknown')}")

        # 调用所有消息处理器
        for handler in self.message_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                self.logger.error(f"消息处理器 {handler.__name__} 出错: {e}", exc_info=e)

    async def connect_websocket(self, token: Optional[str] = None) -> bool:
        """
        连接 WebSocket

        Args:
            token: JWT Token (可选)

        Returns:
            bool: 是否连接成功
        """
        if not WEBSOCKETS_AVAILABLE:
            self.logger.error("websockets 未安装，请运行: pip install websockets")
            return False

        if token:
            self.jwt_token = token

        # 构建 WebSocket URL
        uri = f"{self.ws_url}?token={self.jwt_token or self.api_key}"

        try:
            self.logger.info(f"正在连接 WebSocket: {self.ws_url}")

            self.ws_connection = await websockets.connect(
                uri,
                ping_interval=20,
                ping_timeout=90,
                close_timeout=10
            )

            self.connected = True
            self.reconnect_attempts = 0

            self.logger.info("WebSocket 连接成功")

            # 接收连接成功消息
            try:
                response = await self.ws_connection.recv()
                self.logger.info(f"收到消息: {response[:100] if isinstance(response, str) else 'binary'}")
            except Exception as e:
                self.logger.warning(f"接收初始消息失败: {e}")

            # 发送设备绑定消息
            await self.bind_device()

            return True

        except Exception as e:
            self.logger.error(f"WebSocket 连接失败: {e}", exc_info=e)
            self.connected = False
            return False

    async def bind_device(self, device_name: Optional[str] = "OpenClaw") -> bool:
        """
        绑定设备到 WebSocket 连接
        自动从响应中获取 tenant_id 和 device_id

        Args:
            device_name: 设备名称，默认 "OpenClaw"

        Returns:
            bool: 是否绑定成功
        """
        if not self.ws_connection or not self.connected:
            self.logger.error("WebSocket 未连接，无法绑定设备")
            return False

        bind_message = {
            "type": "bind",
            "device_name": device_name,
            "tenant_id": self.tenant_id or ""
        }

        try:
            await self.ws_connection.send(json.dumps(bind_message))
            self.logger.info(f"发送绑定消息: device_name={device_name}")

            # 等待绑定响应
            response = await self.ws_connection.recv()
            data = json.loads(response)

            if data.get("type") == "bound":
                # 自动获取 tenant_id 和 device_id
                if not self.tenant_id and "tenant_id" in data:
                    self.tenant_id = data["tenant_id"]
                    self.logger.info(f"自动获取 tenant_id: {self.tenant_id}")

                device_id = data.get('device_id')
                if device_id:
                    self.device_id = device_id
                    self.logger.info(f"设备绑定成功: {device_id}")
                else:
                    # 如果没有 device_id，使用默认值
                    self.device_id = f"{self.tenant_id}:{device_name}" if self.tenant_id else device_name
                    self.logger.info(f"设备绑定成功: {self.device_id}")
                return True
            else:
                self.logger.warning(f"绑定响应异常: {data}")
                return False

        except Exception as e:
            self.logger.error(f"设备绑定失败: {e}")
            return False

    async def disconnect_websocket(self):
        """断开 WebSocket 连接"""
        if self.ws_connection:
            try:
                await self.ws_connection.close()
                self.logger.info("WebSocket 连接已关闭")
            except Exception as e:
                self.logger.error(f"关闭 WebSocket 连接时出错: {e}")
            finally:
                self.ws_connection = None
                self.connected = False

    async def listen_websocket(self):
        """
        监听 WebSocket 消息
        这是一个阻塞方法，应该在后台任务中运行
        """
        if not self.ws_connection or not self.connected:
            self.logger.error("WebSocket 未连接")
            return

        self.logger.info("开始监听 WebSocket 消息...")

        try:
            async for message in self.ws_connection:
                try:
                    data = json.loads(message)
                    await self.handle_message(data)
                except json.JSONDecodeError as e:
                    self.logger.error(f"JSON 解析失败: {e}")
                except Exception as e:
                    self.logger.error(f"处理消息时出错: {e}", exc_info=e)

        except websockets.exceptions.ConnectionClosed:
            self.logger.warning("WebSocket 连接已关闭")
            self.connected = False
        except Exception as e:
            self.logger.error(f"WebSocket 监听出错: {e}", exc_info=e)
            self.connected = False

    async def send_websocket_message(self, message: dict) -> bool:
        """
        通过 WebSocket 发送消息

        Args:
            message: 消息字典

        Returns:
            bool: 是否发送成功
        """
        if not self.ws_connection or not self.connected:
            self.logger.error("WebSocket 未连接，无法发送消息")
            return False

        try:
            await self.ws_connection.send(json.dumps(message, ensure_ascii=False))
            self.logger.info(f"消息已通过 WebSocket 发送: {message.get('type', 'unknown')}")
            return True
        except Exception as e:
            self.logger.error(f"WebSocket 发送消息失败: {e}", exc_info=e)
            self.connected = False
            return False

    async def push_to_device(self, target: str, message: dict) -> dict:
        """
        通过 API 推送消息到指定设备

        Args:
            target: 目标设备 ID (格式: user_id:tenant_id:device_name)
            message: 消息字典

        Returns:
            dict: API 响应
        """
        try:
            session = await self.get_http_session()

            payload = {
                "target": target,
                "message": message
            }

            self.logger.info(f"推送消息到设备: {target}")

            async with session.post(
                f"{self.base_url}/api/v1/ws/push",
                json=payload
            ) as response:
                result = await response.json()

                if response.status == 200:
                    self.logger.info("消息推送成功")
                else:
                    self.logger.error(f"消息推送失败: {result}")

                return result

        except Exception as e:
            self.logger.error(f"推送消息异常: {e}", exc_info=e)
            return {"status": "error", "message": str(e)}

    async def broadcast_message(self, message: dict) -> dict:
        """
        广播消息到所有设备

        Args:
            message: 消息字典

        Returns:
            dict: API 响应
        """
        return await self.push_to_device("*", message)

    async def get_tenant_info(self) -> Optional[dict]:
        """
        获取租户信息

        Returns:
            dict: 租户信息，失败返回 None
        """
        try:
            session = await self.get_http_session()

            async with session.get(f"{self.base_url}/api/v1/tenants/me") as response:
                if response.status == 200:
                    data = await response.json()
                    self.logger.info(f"获取租户信息成功: {data.get('name', 'Unknown')}")
                    return data
                else:
                    error = await response.text()
                    self.logger.error(f"获取租户信息失败: {error}")
                    return None

        except Exception as e:
            self.logger.error(f"获取租户信息异常: {e}", exc_info=e)
            return None

    async def get_webhook_logs(self, limit: int = 100) -> list:
        """
        获取 Webhook 日志

        Args:
            limit: 返回数量限制

        Returns:
            list: Webhook 日志列表
        """
        try:
            session = await self.get_http_session()

            async with session.get(
                f"{self.base_url}/api/v1/webhooks",
                params={"limit": limit}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logs = data.get("webhooks", [])
                    self.logger.info(f"获取到 {len(logs)} 条 Webhook 日志")
                    return logs
                else:
                    error = await response.text()
                    self.logger.error(f"获取 Webhook 日志失败: {error}")
                    return []

        except Exception as e:
            self.logger.error(f"获取 Webhook 日志异常: {e}", exc_info=e)
            return []

    async def reconnect_websocket(self) -> bool:
        """
        重新连接 WebSocket

        Returns:
            bool: 是否重连成功
        """
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            self.logger.error(f"已达到最大重连次数 ({self.max_reconnect_attempts})")
            return False

        self.reconnect_attempts += 1
        wait_time = min(2 ** self.reconnect_attempts, 30)  # 指数退避，最多 30 秒

        self.logger.info(f"尝试重连 WebSocket (第 {self.reconnect_attempts} 次)，等待 {wait_time} 秒...")
        await asyncio.sleep(wait_time)

        # 先断开旧连接
        await self.disconnect_websocket()

        # 尝试重新连接
        return await self.connect_websocket()

    async def run_websocket_loop(self):
        """
        运行 WebSocket 循环
        自动连接、监听、重连
        """
        while True:
            try:
                # 如果未连接，尝试连接
                if not self.connected:
                    success = await self.connect_websocket()
                    if not success:
                        # 连接失败，等待后重试
                        await asyncio.sleep(5)
                        continue

                # 监听消息
                await self.listen_websocket()

                # 连接断开，尝试重连
                if not self.connected:
                    await self.reconnect_websocket()

            except asyncio.CancelledError:
                self.logger.info("WebSocket 循环已被取消")
                break
            except Exception as e:
                self.logger.error(f"WebSocket 循环出错: {e}", exc_info=e)
                self.connected = False
                await asyncio.sleep(5)

    async def close(self):
        """关闭所有连接"""
        self.logger.info("正在关闭服务器连接器...")

        await self.disconnect_websocket()
        await self.close_http_session()

        self.logger.info("服务器连接器已关闭")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()

    async def send_media_to_wechat(
        self,
        media_type: str,
        media_url: str = None,
        media_data: str = None,
        file_path: str = None,
        message: str = "",
        title: str = "",
        description: str = "",
        touser: str = "@all"
    ) -> dict:
        """
        发送媒体消息（图片/视频）到企业微信
        支持: URL、base64、本地文件路径

        Args:
            media_type: "image" 或 "video"
            media_url: 媒体文件URL
            media_data: Base64编码的媒体数据
            file_path: 本地文件路径（优先使用 multipart 上传）
            message: 附加文本消息
            title: 视频标题（仅视频）
            description: 视频描述（仅视频）
            touser: 目标用户ID，多个用户用 | 分隔，默认 @all

        Returns:
            dict: API 响应
        """
        try:
            session = await self.get_http_session()
            wechat_config = getattr(self, 'wechat_config', {})
            corp_id = wechat_config.get('corp_id', '')

            self.logger.info(f"发送 {media_type} 到企微...")

            # 如果有本地文件路径，使用 multipart/form-data 方式上传（避免 base64 体积膨胀）
            if file_path and os.path.exists(file_path):
                import aiohttp

                form = aiohttp.FormData()
                self.logger.info(f"[SendMedia] 准备发送 multipart 请求: msg_type={media_type}, touser={touser}")
                form.add_field('msg_type', media_type)
                form.add_field('message', message)
                form.add_field('corp_id', corp_id or '')
                form.add_field('touser', touser)
                if title:
                    form.add_field('title', title)
                if description:
                    form.add_field('description', description)

                # 添加文件
                file_name = os.path.basename(file_path)
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                form.add_field('media_file', file_content, filename=file_name,
                               content_type=f'{"image/jpeg" if media_type == "image" else "video/mp4"}')

                # 重要：移除默认的 Content-Type header，让 aiohttp 自动设置 multipart boundary
                headers = {
                    "X-API-Key": self.api_key
                }
                if self.jwt_token:
                    headers["Authorization"] = f"Bearer {self.jwt_token}"

                async with session.post(
                    f"{self.base_url}/api/v1/wechat/send",
                    data=form,
                    headers=headers
                ) as response:
                    result = await response.json()
                    if response.status == 200:
                        self.logger.info(f"{media_type} 发送成功")
                    else:
                        self.logger.error(f"{media_type} 发送失败: {result}")
                    return result

            # 使用 JSON + base64/URL 方式（向后兼容）
            payload = {
                "msg_type": media_type,
                "message": message,
                "corp_id": corp_id,
                "media_url": media_url,
                "media_data": media_data,
                "title": title,
                "description": description,
                "touser": touser
            }

            # 移除空值（但保留 touser）
            payload = {k: v for k, v in payload.items() if v is not None}

            async with session.post(
                f"{self.base_url}/api/v1/wechat/send",
                json=payload
            ) as response:
                result = await response.json()

                if response.status == 200:
                    self.logger.info(f"{media_type} 发送成功")
                else:
                    self.logger.error(f"{media_type} 发送失败: {result}")

                return result

        except Exception as e:
            self.logger.error(f"发送媒体消息异常: {e}", exc_info=e)
            return {"status": "error", "message": str(e)}

    async def download_wechat_media(self, media_id: str) -> bytes:
        """
        从企微下载媒体文件

        Args:
            media_id: 企微媒体文件ID

        Returns:
            bytes: 文件数据
        """
        try:
            session = await self.get_http_session()

            self.logger.info(f"下载媒体文件: {media_id}")

            async with session.get(
                f"{self.base_url}/api/v1/wechat/media/{media_id}"
            ) as response:
                if response.status == 200:
                    data = await response.read()
                    self.logger.info(f"媒体文件下载成功: {len(data)} bytes")
                    return data
                else:
                    error = await response.text()
                    self.logger.error(f"下载媒体失败: {error}")
                    return None

        except Exception as e:
            self.logger.error(f"下载媒体异常: {e}", exc_info=e)
            return None

    async def download_wechat_file(self, file_key: str, file_name: str = "download") -> bytes:
        """
        从企微下载文件（PDF、DOC等）

        Args:
            file_key: 企微文件key
            file_name: 文件名

        Returns:
            bytes: 文件数据
        """
        try:
            session = await self.get_http_session()

            self.logger.info(f"下载文件: {file_name} (key: {file_key[:20]}...)")

            payload = {
                "file_key": file_key,
                "file_name": file_name
            }

            async with session.post(
                f"{self.base_url}/api/v1/wechat/file/download",
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.read()
                    self.logger.info(f"文件下载成功: {file_name} ({len(data)} bytes)")
                    return data
                else:
                    error = await response.text()
                    self.logger.error(f"下载文件失败: {error}")
                    return None

        except Exception as e:
            self.logger.error(f"下载文件异常: {e}", exc_info=e)
            return None

    async def send_file_to_wechat(
        self,
        file_path: str,
        file_name: str = None,
        message: str = "",
        touser: str = "@all"
    ) -> dict:
        """
        发送文件到企业微信 (PDF, DOC, 等)
        使用 multipart/form-data 方式上传，避免 base64 体积膨胀

        Args:
            file_path: 本地文件路径
            file_name: 文件名（可选，默认从路径提取）
            message: 附加文本消息
            touser: 目标用户ID，默认 @all

        Returns:
            dict: API 响应
        """
        try:
            if not file_name:
                file_name = os.path.basename(file_path)

            file_size = os.path.getsize(file_path)
            self.logger.info(f"发送文件到企微: {file_name} ({file_size} bytes), 目标: {touser}")

            session = await self.get_http_session()

            # 使用 multipart/form-data 方式上传（避免 base64 体积膨胀）
            import aiohttp
            form = aiohttp.FormData()
            form.add_field('msg_type', 'file')
            form.add_field('message', message)
            form.add_field('corp_id', getattr(self, 'wechat_config', {}).get('corp_id', ''))
            form.add_field('touser', touser)

            # 添加文件
            with open(file_path, 'rb') as f:
                file_content = f.read()
            form.add_field('media_file', file_content, filename=file_name,
                           content_type='application/octet-stream')

            # 重要：移除默认的 Content-Type header，让 aiohttp 自动设置 multipart boundary
            headers = {
                "X-API-Key": self.api_key
            }
            if self.jwt_token:
                headers["Authorization"] = f"Bearer {self.jwt_token}"

            async with session.post(
                f"{self.base_url}/api/v1/wechat/send",
                data=form,
                headers=headers
            ) as response:
                result = await response.json()

                if response.status == 200:
                    self.logger.info(f"文件发送成功: {file_name}")
                else:
                    self.logger.error(f"文件发送失败: {result}")

                return result

        except Exception as e:
            self.logger.error(f"发送文件异常: {e}", exc_info=e)
            return {"status": "error", "message": str(e)}

    async def send_reply_to_wechat(self, user_id: str, message: str, touser: str = "@all") -> dict:
        """
        发送文本回复到企业微信

        Args:
            user_id: 用户ID (corporation_id)
            message: 文本消息内容
            touser: 目标用户ID，默认 @all 发送给所有人

        Returns:
            dict: API 响应
        """
        try:
            session = await self.get_http_session()

            payload = {
                "msg_type": "text",
                "message": message,
                "corp_id": user_id,
                "touser": touser
            }

            self.logger.info(f"发送文本消息到企微，目标用户: {touser}...")

            async with session.post(
                f"{self.base_url}/api/v1/wechat/send",
                json=payload
            ) as response:
                result = await response.json()

                if response.status == 200:
                    self.logger.info(f"文本消息发送成功")
                else:
                    self.logger.error(f"文本消息发送失败: {result}")

                return result

        except Exception as e:
            self.logger.error(f"发送文本消息异常: {e}", exc_info=e)
            return {"status": "error", "message": str(e)}


# 便捷函数

async def create_connector(
    api_key: str,
    base_url: str = "https://websocket.sillymd.com",
    device_id: Optional[str] = None,
    tenant_id: Optional[str] = None
) -> ServerConnector:
    """
    创建服务器连接器

    Args:
        api_key: API Key
        base_url: 服务器基础 URL
        device_id: 设备 ID
        tenant_id: 租户 ID

    Returns:
        ServerConnector: 连接器实例
    """
    connector = ServerConnector(
        api_key=api_key,
        base_url=base_url,
        device_id=device_id,
        tenant_id=tenant_id
    )

    # 获取租户信息验证连接
    tenant_info = await connector.get_tenant_info()
    if tenant_info:
        logger.info("服务器连接器创建成功并已验证")
    else:
        logger.warning("服务器连接器创建成功但验证失败")

    return connector


if __name__ == "__main__":
    # 测试代码
    async def test_connector():
        """测试连接器"""
        # 注意：这里需要真实的 API Key
        api_key = "test_api_key"

        async with ServerConnector(api_key=api_key) as connector:
            # 获取租户信息
            tenant_info = await connector.get_tenant_info()
            print(f"租户信息: {tenant_info}")

            # 获取 Webhook 日志
            logs = await connector.get_webhook_logs(limit=10)
            print(f"日志数量: {len(logs)}")

    # 运行测试
    asyncio.run(test_connector())
