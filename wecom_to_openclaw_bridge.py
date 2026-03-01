#!/usr/bin/env python3
"""
企业微信 <-> OpenClaw 双向消息桥接器
接收 SillyMD 消息并推送到 OpenClaw session，同时监控 agent 响应并发送回企微
"""
import asyncio
import hashlib
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

# ========== 进程锁机制 ==========
PID_FILE = Path(__file__).parent / ".bridge_pid"

def acquire_lock() -> bool:
    """获取进程锁，确保只有一个实例运行"""
    try:
        # 检查是否已有进程在运行
        if PID_FILE.exists():
            try:
                with open(PID_FILE, 'r') as f:
                    old_pid = int(f.read().strip())

                # 检查进程是否仍然存在（跨平台方法）
                if sys.platform == 'win32':
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    handle = kernel32.OpenProcess(1, False, old_pid)
                    if handle:
                        kernel32.CloseHandle(handle)
                        print(f"桥接器已在运行 (PID: {old_pid})，请勿重复启动")
                        return False
                else:
                    # Unix/Linux/Mac
                    try:
                        os.kill(old_pid, 0)
                        print(f"桥接器已在运行 (PID: {old_pid})，请勿重复启动")
                        return False
                    except ProcessLookupError:
                        pass  # 进程不存在

                # 进程已不存在，删除旧的 PID 文件
                PID_FILE.unlink()
            except (ValueError, OSError):
                # PID 文件内容无效，直接删除
                PID_FILE.unlink(missing_ok=True)

        # 写入当前进程 PID
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
        return True
    except Exception as e:
        print(f"获取进程锁失败: {e}")
        return False

def release_lock():
    """释放进程锁"""
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
    except Exception:
        pass

# 在导入其他模块前检查锁
if not acquire_lock():
    sys.exit(1)

# 确保程序退出时释放锁
import atexit
atexit.register(release_lock)

sys.path.insert(0, str(Path(__file__).parent))

from server_connector import ServerConnector
from config_manager import ConfigManager
from wechat_crypto import WeChatCrypto
from voice_recognition import transcribe_voice, get_recognizer

# 尝试导入 Sherpa-ONNX 语音识别
try:
    from asr_sherpa_onnx import transcribe_voice_sherpa
    SHERPA_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Sherpa-ONNX 语音识别模块未加载: {e}")
    SHERPA_AVAILABLE = False
    transcribe_voice_sherpa = None

# 配置日志
from logging_config import setup_logging
logger = setup_logging("__main__", log_to_file=True, log_to_console=True)

# 文件存储目录 - 接收到的所有文件统一存放于此
FILE_STORAGE_DIR = Path(__file__).parent / "file"
FILE_STORAGE_DIR.mkdir(exist_ok=True)
logger.info(f"文件存储目录: {FILE_STORAGE_DIR}")


# ========== 动态配置检测函数 ==========

def find_openclaw_cmd() -> str:
    """
    自动查找 openclaw 命令路径
    优先级: 环境变量 > PATH检测 > npm全局安装 > 默认命令
    """
    # 1. 检查环境变量
    env_cmd = os.getenv('OPENCLAW_CMD')
    if env_cmd and Path(env_cmd).exists():
        logger.info(f"从环境变量获取 openclaw 命令: {env_cmd}")
        return env_cmd

    # 2. 检查 PATH
    try:
        import shutil
        path_cmd = shutil.which('openclaw')
        if path_cmd:
            logger.info(f"从 PATH 找到 openclaw 命令: {path_cmd}")
            return path_cmd
    except Exception:
        pass

    # 3. 检查 npm 全局安装 (Windows)
    if sys.platform == 'win32':
        npm_path = Path(os.environ.get('APPDATA', '')) / 'npm' / 'openclaw.cmd'
        if npm_path.exists():
            logger.info(f"从 npm 全局安装找到 openclaw: {npm_path}")
            return str(npm_path)

    # 4. 检查常见位置
    common_paths = [
        Path.home() / 'AppData' / 'Roaming' / 'npm' / 'openclaw.cmd',
        Path('/usr/local/bin/openclaw'),
        Path('/usr/bin/openclaw'),
    ]
    for path in common_paths:
        if path.exists():
            logger.info(f"从常见路径找到 openclaw: {path}")
            return str(path)

    # 5. 默认命令（依赖系统 PATH）
    logger.warning("未找到 openclaw 具体路径，使用默认命令 'openclaw'")
    return 'openclaw'


def find_openclaw_session(agent_name: str = None, session_id: str = None) -> tuple:
    """
    自动查找 OpenClaw session

    优先级:
    1. 环境变量 OPENCLAW_SESSION_ID / OPENCLAW_SESSION_FILE
    2. 配置文件中指定的 session
    3. 自动查找最新的 session

    Returns:
        tuple: (session_id, session_file_path)
    """
    # 1. 检查环境变量
    env_session_id = os.getenv('OPENCLAW_SESSION_ID')
    env_session_file = os.getenv('OPENCLAW_SESSION_FILE')

    if env_session_file and Path(env_session_file).exists():
        session_id = env_session_id or Path(env_session_file).stem
        logger.info(f"从环境变量获取 session: {session_id}")
        return session_id, env_session_file

    # 2. 构建基础路径
    if agent_name is None:
        agent_name = os.getenv('OPENCLAW_AGENT', 'main')

    base_dir = Path.home() / '.openclaw' / 'agents' / agent_name / 'sessions'

    if not base_dir.exists():
        logger.error(f"OpenClaw agents 目录不存在: {base_dir}")
        logger.error("请确保 OpenClaw 已正确安装和配置")
        return None, None

    # 3. 如果指定了 session_id，查找对应文件
    if session_id:
        session_file = base_dir / f"{session_id}.jsonl"
        if session_file.exists():
            logger.info(f"找到指定的 session: {session_id}")
            return session_id, str(session_file)
        else:
            logger.warning(f"指定的 session 不存在: {session_file}")

    # 4. 自动查找最新的 session
    try:
        sessions = sorted(
            base_dir.glob('*.jsonl'),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        if sessions:
            latest_session = sessions[0]
            session_id = latest_session.stem
            logger.info(f"自动找到最新 session: {session_id}")
            return session_id, str(latest_session)
    except Exception as e:
        logger.error(f"查找 session 时出错: {e}")

    logger.error("未找到任何可用的 OpenClaw session")
    return None, None


def load_openclaw_config(server_config) -> dict:
    """
    加载 OpenClaw 配置
    优先级: 配置文件 > 环境变量 > 自动检测 > 硬编码默认值
    """
    config = {}

    # 1. 从服务器配置读取（如果存在）
    if hasattr(server_config, 'openclaw') and server_config.openclaw:
        config.update(server_config.openclaw)
        logger.info("从配置文件加载 openclaw 配置")

    # 2. 环境变量覆盖
    if os.getenv('OPENCLAW_SESSION_ID'):
        config['session_id'] = os.getenv('OPENCLAW_SESSION_ID')
    if os.getenv('OPENCLAW_SESSION_FILE'):
        config['session_file'] = os.getenv('OPENCLAW_SESSION_FILE')
    if os.getenv('OPENCLAW_CMD'):
        config['cmd'] = os.getenv('OPENCLAW_CMD')
    if os.getenv('OPENCLAW_AGENT'):
        config['agent'] = os.getenv('OPENCLAW_AGENT')

    # 3. 自动检测缺失的配置
    if not config.get('cmd'):
        config['cmd'] = find_openclaw_cmd()

    if not config.get('session_id') or not config.get('session_file'):
        agent_name = config.get('agent', 'main')
        session_id = config.get('session_id')
        detected_id, detected_file = find_openclaw_session(agent_name, session_id)

        if detected_id:
            config['session_id'] = detected_id
            config['session_file'] = detected_file
        else:
            # 最后的默认值（向后兼容）
            config['session_id'] = config.get('session_id', 'ffb310cd-a64a-4c55-a6dd-37b696f9a9c0')
            config['session_file'] = config.get('session_file',
                r"C:\Users\HughWang\.openclaw\agents\main\sessions\ffb310cd-a64a-4c55-a6dd-37b696f9a9c0.jsonl")
            logger.warning(f"使用默认 session 配置: {config['session_id']}")

    return config


class WeComToOpenClawBridge:
    """企微与 OpenClaw 双向消息桥接器"""

    def __init__(self, session_key: str = "main"):
        self.session_key = session_key
        self.config_manager = ConfigManager()
        self.server_config = self.config_manager.load_server_config()

        # 延迟初始化的组件
        self.crypto = None
        self.connector = None
        self.openclaw_config = None
        self.openclaw_session_id = None
        self.openclaw_session_file = None
        self.openclaw_cmd = None
        self.wechat_config = None  # 从API获取的企微配置（内存存储，不持久化）

    async def initialize(self):
        """异步初始化 - 获取配置并初始化组件"""
        logger.info("初始化桥接器...")

        # 初始化 SillyMD 连接器（使用简化配置）
        self.connector = ServerConnector(
            api_key=self.server_config.api_key,
            base_url=self.server_config.base_url,
            device_id=self.server_config.device_id,
            tenant_id=self.server_config.tenant_id,
            jwt_token=self.server_config.jwt_token
        )

        # 注册消息处理器
        self.connector.add_message_handler(self._handle_message)

        # 本系统使用 API Key 直接作为 WebSocket token
        # 无需额外获取 JWT Token
        if not self.server_config.jwt_token:
            logger.info("未配置 JWT Token，将使用 API Key 直接连接")

        # 从后端获取租户信息和企微配置
        logger.info("正在从后端获取配置...")
        tenant_info = await self.connector.fetch_tenant_info()
        if not tenant_info or not tenant_info.get('id'):
            logger.error("无法获取租户信息，请检查 API Key")
            raise ValueError("缺少租户信息")

        # 更新租户ID
        self.server_config.tenant_id = str(tenant_info['id'])
        self.connector.tenant_id = self.server_config.tenant_id
        logger.info(f"租户ID已获取: {self.server_config.tenant_id}")

        # 获取企微配置
        wechat_info = tenant_info.get('wechat', {})
        if not wechat_info or not wechat_info.get('token'):
            logger.error("服务器未配置企业微信参数")
            raise ValueError("缺少企业微信配置")

        # 合并企微配置（保留本地 owner_id）
        owner_id = self.server_config.wechat.get('owner_id', 'HughWang') if self.server_config.wechat else 'HughWang'
        self.wechat_config = {**wechat_info, 'owner_id': owner_id}
        logger.info("企业微信配置已获取（仅内存存储）")

        # 只保存最小化配置（api_key 和 owner_id），API获取的配置不保存到文件
        self.config_manager.save_minimal_config(self.server_config)

        # 初始化加密器
        wechat_config = self.wechat_config
        self.crypto = WeChatCrypto(
            wechat_config.get('token', ''),
            wechat_config.get('encoding_aes_key', ''),
            wechat_config.get('corp_id', '')
        )

        # 初始化 OpenClaw 配置（动态检测）
        self.openclaw_config = load_openclaw_config(self.server_config)
        self.openclaw_session_id = self.openclaw_config['session_id']
        self.openclaw_session_file = self.openclaw_config['session_file']
        self.openclaw_cmd = self.openclaw_config['cmd']

        logger.info("=" * 60)
        logger.info("OpenClaw 配置")
        logger.info(f"  命令: {self.openclaw_cmd}")
        logger.info(f"  Session ID: {self.openclaw_session_id}")
        logger.info(f"  Session 文件: {self.openclaw_session_file}")
        logger.info("=" * 60)

        # 响应监控
        self.response_monitor_task = None
        self.last_line_count = 0
        self.processed_message_ids = set()  # 用于去重OpenClaw响应
        self.processed_wechat_msg_ids = set()  # 用于去重企微消息
        self.processed_encrypted_msgs = set()  # 用于去重WebSocket收到的加密消息
        self.last_sender = None  # 用于记录最后的发送者以便回复
        self._message_lock = asyncio.Lock()  # 用于防止并发处理同一条消息
        self._pending_responses = {}  # 存储待处理响应的预期目标用户 {content_hash: (target_user, timestamp)}

        # 持久化去重 - 使用文件记录已处理的响应ID，跨进程共享
        self._dedup_file = Path(__file__).parent / ".processed_responses"
        self._load_processed_ids()

        # 统计
        self.stats = {
            "messages_received": 0,
            "messages_forwarded": 0,
            "responses_sent": 0,
            "messages_failed": 0
        }

    def _load_processed_ids(self):
        """从文件加载已处理的响应ID"""
        try:
            if self._dedup_file.exists():
                with open(self._dedup_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        msg_id = line.strip()
                        if msg_id:
                            self.processed_message_ids.add(msg_id)
                logger.info(f"已加载 {len(self.processed_message_ids)} 个已处理响应ID")
        except Exception as e:
            logger.warning(f"加载已处理响应ID失败: {e}")

    def _save_processed_id(self, msg_id: str):
        """保存已处理的响应ID到文件（防止重复写入）"""
        try:
            # 先检查是否已经保存过（防止重复）
            if msg_id in self.processed_message_ids:
                return

            # 添加到集合（防止内存中重复）
            self.processed_message_ids.add(msg_id)

            with open(self._dedup_file, 'a', encoding='utf-8') as f:
                f.write(f"{msg_id}\n")
                f.flush()  # 确保立即写入磁盘
        except Exception as e:
            logger.warning(f"保存已处理响应ID失败: {e}")

    async def _handle_message(self, message: dict):
        """处理 SillyMD 消息"""
        async with self._message_lock:
            try:
                msg_data = message.get('data', message)
                msg_type = msg_data.get('type', 'unknown')

                logger.info(f"收到消息类型: {msg_type}")

                if msg_type == 'ping':
                    return

                if msg_type == 'connected':
                    return

                if msg_type == 'wechat_reply':
                    logger.debug(f"跳过明文消息: {msg_type}")
                    return

                if msg_type != 'wechat_encrypted':
                    logger.debug(f"跳过非加密消息: {msg_type}")
                    return

                # 使用加密内容去重 - 防止服务器发送重复消息
                encrypted = msg_data.get('encrypted', '')
                if encrypted:
                    # 使用 MD5 生成稳定的哈希（hash() 函数每次运行结果不同）
                    encrypted_hash = hashlib.md5(encrypted[:100].encode()).hexdigest()[:16]
                    if encrypted_hash in self.processed_encrypted_msgs:
                        logger.info("检测到重复的加密消息，跳过处理")
                        return
                    self.processed_encrypted_msgs.add(encrypted_hash)
                    # 限制集合大小
                    if len(self.processed_encrypted_msgs) > 500:
                        self.processed_encrypted_msgs = set(list(self.processed_encrypted_msgs)[-250:])

                logger.info(f"收到加密消息 #{self.stats['messages_received'] + 1}")
                self.stats["messages_received"] += 1

                # 解密消息
                msg_signature = msg_data.get('msg_signature', '')
                timestamp = msg_data.get('timestamp', '')
                nonce = msg_data.get('nonce', '')

                try:
                    decrypted_xml = self.crypto.decrypt_msg(
                        msg_signature, timestamp, nonce, encrypted
                    )
                    logger.info("消息解密成功")

                    # 提取消息ID用于去重
                    msg_id = self._extract_msg_id(decrypted_xml)
                    if msg_id:
                        if msg_id in self.processed_wechat_msg_ids:
                            logger.info(f"消息 {msg_id[:16]}... 已处理过，跳过")
                            return
                        self.processed_wechat_msg_ids.add(msg_id)
                        logger.info(f"消息ID: {msg_id[:16]}...")
                        # 限制集合大小，防止内存无限增长
                        if len(self.processed_wechat_msg_ids) > 1000:
                            self.processed_wechat_msg_ids = set(list(self.processed_wechat_msg_ids)[-500:])

                    # 提取消息数据 v1.1.0 支持媒体消息
                    msg_payload, sender = self._extract_message_data(decrypted_xml)
                    logger.info(f"提取消息数据: type={msg_payload.get('type') if msg_payload else 'None'}, sender={sender}")
                    if msg_payload:
                        self.last_sender = sender  # 记录发送者以便回复
                        msg_inner_type = msg_payload.get("type", "text")

                        # 根据消息类型处理
                        if msg_inner_type == "text":
                            # 文本消息
                            content = msg_payload.get("content") or ""
                            if not content:
                                logger.warning(f"收到空文本消息，跳过: sender={sender}")
                            # 检查是否是企微系统消息（超大文件等）
                            elif self._is_wechat_system_message(content):
                                logger.info(f"收到企微系统消息，直接回复: {content[:50]}...")
                                await self._reply_system_message(content, sender)
                            else:
                                result = await self._forward_to_openclaw(content, sender)
                                if result.get("success"):
                                    self.stats["messages_forwarded"] += 1
                                    logger.info("文本消息转发成功")
                                else:
                                    self.stats["messages_failed"] += 1

                        elif msg_inner_type in ["image", "video", "voice"]:
                            # 媒体消息 v1.1.0
                            logger.info(f"收到{msg_inner_type}消息，开始处理...")
                            await self._handle_media_message(msg_payload, sender)

                        elif msg_inner_type == "file":
                            # 文件消息 v1.2.0
                            logger.info(f"收到文件消息，开始处理...")
                            await self._handle_file_message(msg_payload, sender)

                        else:
                            logger.warning(f"不支持的消息类型: {msg_inner_type}")

                    else:
                        logger.warning("无法提取消息内容")

                except Exception as e:
                    logger.error(f"解密或处理失败: {e}")
                    self.stats["messages_failed"] += 1

            except Exception as e:
                logger.error(f"处理消息时出错: {e}")

    def _extract_msg_id(self, xml_content: str) -> str:
        """从 XML 提取消息ID用于去重"""
        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(xml_content)
            # 辅助函数：查找元素（支持带或不带命名空间）
            def find_elem(root, tag):
                elem = root.find(tag)
                if elem is not None:
                    return elem
                for child in root.iter():
                    if child.tag.endswith('}' + tag) or child.tag == tag:
                        return child
                return None
            msg_id_node = find_elem(root, 'MsgId')
            if msg_id_node is not None:
                return msg_id_node.text
        except Exception:
            pass
        return None

    def _extract_message_data(self, xml_content: str) -> tuple:
        """从 XML 提取消息数据、发送者和消息类型 v1.1.0"""
        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(xml_content)

            # 辅助函数：查找元素（支持带或不带命名空间）
            def find_elem(root, tag):
                # 先尝试直接查找
                elem = root.find(tag)
                if elem is not None:
                    return elem
                # 遍历所有元素，匹配 tag（忽略命名空间前缀）
                for child in root.iter():
                    if child.tag.endswith('}' + tag) or child.tag == tag:
                        return child
                return None

            msg_type_node = find_elem(root, 'MsgType')
            content_node = find_elem(root, 'Content')
            from_user = find_elem(root, 'FromUserName')

            msg_type = msg_type_node.text if msg_type_node is not None else "text"
            sender = from_user.text if from_user is not None else "Unknown"

            # 图片消息
            if msg_type == "image":
                pic_url = find_elem(root, 'PicUrl')
                media_id = find_elem(root, 'MediaId')
                return {
                    "type": "image",
                    "pic_url": pic_url.text if pic_url is not None else None,
                    "media_id": media_id.text if media_id is not None else None
                }, sender

            # 视频/小视频消息
            if msg_type in ["video", "shortvideo"]:
                media_id = find_elem(root, 'MediaId')
                thumb_media_id = find_elem(root, 'ThumbMediaId')
                return {
                    "type": "video",
                    "media_id": media_id.text if media_id is not None else None,
                    "thumb_media_id": thumb_media_id.text if thumb_media_id is not None else None
                }, sender

            # 语音消息 v1.1.0
            if msg_type == "voice":
                media_id = find_elem(root, 'MediaId')
                format_node = find_elem(root, 'Format')
                recognition = find_elem(root, 'Recognition')  # 企微自带的语音识别结果
                return {
                    "type": "voice",
                    "media_id": media_id.text if media_id is not None else None,
                    "format": format_node.text if format_node is not None else "amr",
                    "recognition": recognition.text if recognition is not None else None  # 企微已识别的文字
                }, sender

            # 文件消息 v1.1.0
            if msg_type == "file":
                file_key = find_elem(root, 'FileKey')
                file_name = find_elem(root, 'FileName')
                file_ext = find_elem(root, 'FileExtension')
                file_size = find_elem(root, 'FileSize')
                return {
                    "type": "file",
                    "file_key": file_key.text if file_key is not None else None,
                    "file_name": file_name.text if file_name is not None else "unknown",
                    "file_ext": file_ext.text if file_ext is not None else "",
                    "file_size": int(file_size.text) if file_size is not None and file_size.text.isdigit() else 0
                }, sender

            # 文本消息 (默认)
            content = content_node.text if content_node is not None else None
            return {"type": "text", "content": content}, sender

        except Exception as e:
            logger.error(f"XML 解析失败: {e}")
            return None, None

    def _forward_to_openclaw_sync(self, content: str, sender: str) -> dict:
        """同步方式转发到 OpenClaw"""
        try:
            import subprocess
            import hashlib
            import time

            # 防护：确保 content 不为 None 或空
            if not content:
                logger.warning(f"尝试转发空内容，跳过: sender={sender}")
                return {"success": False, "error": "Empty content"}

            # 在消息内容中添加[sender]标识
            message_text = f"[{sender}] {content}"

            # 计算内容哈希，用于后续关联响应
            content_hash = hashlib.md5(content.encode()).hexdigest()

            # 构建目标用户（用于后续回复）- 发给发送者，抄送owner
            wechat_config = self.wechat_config
            owner_id = wechat_config.get('owner_id', '')
            if sender and sender != owner_id:
                # 发给发送者 + 抄送owner
                target_user = f"{sender}|{owner_id}" if owner_id else sender
            elif sender:
                # 发送者就是owner，只发给owner
                target_user = sender
            else:
                target_user = owner_id or "@all"

            # 记录待处理响应的预期目标用户和问题内容（5分钟过期）
            self._pending_responses[content_hash] = (target_user, time.time(), content, sender)
            logger.info(f"[Pending] 记录响应目标: {target_user}, hash={content_hash[:8]}..., sender={sender}")

            # 清理过期的pending记录（超过5分钟）
            current_time = time.time()
            expired_hashes = [h for h, (_, ts, _, _) in self._pending_responses.items() if current_time - ts > 300]
            for h in expired_hashes:
                del self._pending_responses[h]

            # 注意：不要直接写入 session 文件，让 OpenClaw agent 自己处理
            # 直接触发 OpenClaw agent 运行
            try:
                cmd = [
                    self.openclaw_cmd,
                    "agent",
                    "--session-id", self.openclaw_session_id,
                    "--message", message_text,
                    "--thinking", "low"
                ]
                logger.info(f"触发 OpenClaw agent: {self.openclaw_cmd}")

                subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=(sys.platform == 'win32')
                )
                logger.info("Agent 已触发")
            except Exception as e:
                logger.warning(f"触发 agent 失败: {e}")

            return {"success": True}

        except Exception as e:
            logger.error(f"写入 session 文件失败: {e}")
            return {"success": False, "error": str(e)}

    async def _forward_to_openclaw(self, content: str, sender: str) -> dict:
        """转发到 OpenClaw"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._forward_to_openclaw_sync, content, sender)

    async def _monitor_responses(self):
        """监控 OpenClaw session 文件中的 agent 响应"""
        logger.info("启动响应监控...")

        # 使用锁防止并发处理同一条响应
        response_lock = asyncio.Lock()
        # 正在处理的响应ID（防止发送过程中重复）
        processing_ids = set()
        # 内容级别去重（防止相同内容多次发送）
        # 内容级别去重 - 存储 {hash: timestamp}
        processed_content_hashes = {}

        while True:
            try:
                await asyncio.sleep(2)  # 每2秒检查一次

                if not os.path.exists(self.openclaw_session_file):
                    continue

                with open(self.openclaw_session_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                current_line_count = len(lines)

                # 文件有新增内容
                if current_line_count > self.last_line_count:
                    new_lines = lines[self.last_line_count:]
                    self.last_line_count = current_line_count

                    for line in new_lines:
                        try:
                            entry = json.loads(line.strip())
                            msg_id = entry.get('id')

                            if not msg_id:
                                continue

                            # 立即检查是否已处理或正在处理
                            if msg_id in self.processed_message_ids:
                                continue
                            if msg_id in processing_ids:
                                continue

                            # 只处理 assistant 角色的消息
                            if entry.get('message', {}).get('role') == 'assistant':
                                content_blocks = entry.get('message', {}).get('content', [])
                                text_content = self._extract_text_from_content(content_blocks)

                                # 检查 metadata 中的媒体信息 v1.1.0
                                metadata = entry.get('metadata', {})
                                media_type = metadata.get('media_type')
                                media_path = metadata.get('media_path')

                                if text_content:
                                    logger.info(f"检测到 Agent 响应: {text_content[:80]}...")

                                    # 计算内容哈希进行额外去重（防止同一内容不同msg_id）
                                    content_hash = hashlib.md5(text_content.encode()).hexdigest()

                                    # 使用锁保护整个处理流程
                                    async with response_lock:
                                        # 再次检查（获取锁后）
                                        if msg_id in self.processed_message_ids or msg_id in processing_ids:
                                            logger.debug(f"响应 {msg_id[:16]}... 已在处理中，跳过")
                                            continue

                                        # 内容级别去重（同一内容10秒内只发送一次）
                                        current_time = time.time()
                                        if content_hash in processed_content_hashes:
                                            logger.warning(f"[DUPLICATE BLOCKED] 相同内容已在10秒内发送过，跳过: {text_content[:50]}...")
                                            # 仍然标记为已处理，防止再次检查
                                            self.processed_message_ids.add(msg_id)
                                            self._save_processed_id(msg_id)
                                            continue

                                        # 标记为正在处理
                                        processing_ids.add(msg_id)

                                        try:
                                            # 先保存到文件（确保即使发送失败也不会重复）
                                            self.processed_message_ids.add(msg_id)
                                            self._save_processed_id(msg_id)

                                            # 记录内容哈希和时间戳
                                            processed_content_hashes[content_hash] = current_time
                                            logger.info(f"[HASH RECORDED] {content_hash[:16]}... for: {text_content[:30]}...")

                                            # 发送响应
                                            await self._send_response_to_wechat(
                                                text_content,
                                                media_type=media_type,
                                                media_path=media_path
                                            )
                                        finally:
                                            # 无论成功失败，都从 processing 中移除
                                            processing_ids.discard(msg_id)

                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            logger.error(f"处理响应消息时出错: {e}")

                # 限制 processing_ids 大小
                if len(processing_ids) > 100:
                    processing_ids.clear()

                # 清理过期的内容哈希（超过10秒的）
                current_time = time.time()
                expired_hashes = [h for h, t in processed_content_hashes.items() if current_time - t > 10]
                for h in expired_hashes:
                    del processed_content_hashes[h]

            except asyncio.CancelledError:
                logger.info("响应监控已停止")
                break
            except Exception as e:
                logger.error(f"响应监控出错: {e}")
                await asyncio.sleep(5)

    def _extract_text_from_content(self, content_blocks: list) -> str:
        """从内容块中提取文本"""
        texts = []
        for block in content_blocks:
            if block.get('type') == 'text':
                texts.append(block.get('text', ''))
        return '\n'.join(texts)

    async def _send_response_to_wechat(self, message: str, media_type: str = None, media_path: str = None):
        """发送响应到企业微信 v1.1.0 支持媒体"""
        # 使用类级别的最近发送记录来去重（基于内容哈希）
        if not hasattr(self, '_recent_sent_messages'):
            self._recent_sent_messages = {}  # {hash: timestamp}

        # 计算消息内容哈希（用于去重）
        content_hash = hashlib.md5(message.encode()).hexdigest()
        current_time = time.time()

        # 检查是否在10秒内发送过相同内容
        if content_hash in self._recent_sent_messages:
            last_sent_time = self._recent_sent_messages[content_hash]
            if current_time - last_sent_time < 10:  # 10秒去重窗口
                logger.warning(f"检测到重复响应（10秒内），跳过发送: {message[:50]}...")
                return

        # 更新发送记录
        self._recent_sent_messages[content_hash] = current_time

        # 清理过期的记录（超过60秒的）
        self._recent_sent_messages = {
            k: v for k, v in self._recent_sent_messages.items()
            if current_time - v < 60
        }

        try:
            logger.info(f"准备发送响应到企微: {message[:80]}...")

            wechat_config = self.wechat_config
            corp_id = wechat_config.get('corp_id', '')
            owner_id = wechat_config.get('owner_id', '')

            # 尝试从 pending_responses 获取目标用户和原始问题（更可靠）
            target_user = None
            original_question = None
            original_sender = None
            if hasattr(self, '_pending_responses') and self._pending_responses:
                # 找到最近添加的 pending 记录
                most_recent_hash = max(self._pending_responses.keys(), key=lambda h: self._pending_responses[h][1])
                target_user, timestamp, original_question, original_sender = self._pending_responses[most_recent_hash]
                # 检查是否过期（5分钟）
                if current_time - timestamp < 300:
                    logger.info(f"[Pending] 使用记录的目标用户: {target_user}, hash={most_recent_hash[:8]}..., sender={original_sender}")
                    # 删除已使用的记录
                    del self._pending_responses[most_recent_hash]
                else:
                    target_user = None
                    original_question = None
                    original_sender = None

            # 回退到使用 last_sender
            if not target_user:
                sender = getattr(self, 'last_sender', None)
                wechat_config = self.wechat_config
                owner_id = wechat_config.get('owner_id', '')
                if sender and sender != owner_id:
                    target_user = f"{sender}|{owner_id}" if owner_id else sender
                    original_sender = sender
                elif sender:
                    target_user = sender
                    original_sender = sender
                else:
                    target_user = owner_id or "@all"
                    original_sender = None
                logger.info(f"[Fallback] 使用 last_sender 的目标用户: {target_user}")

            # 格式化消息：如果是抄送给owner，需要包含原始问题
            wechat_config = self.wechat_config
            owner_id = wechat_config.get('owner_id', '')
            if "|" in target_user and original_sender and original_sender != owner_id and original_question:
                # 非owner用户的问题，需要抄送给owner，格式化消息
                formatted_message = f"【{original_sender}】{original_question}\n\n【回复内容】{message}"
                logger.info(f"[Format] 格式化抄送消息: {formatted_message[:80]}...")
                message = formatted_message

            logger.info(f"最终目标用户: {target_user}")

            # 如果有媒体文件，使用媒体发送 v1.2.0
            if media_type and media_path and os.path.exists(media_path):
                logger.info(f"发送媒体响应: {media_type} - {media_path}")

                try:
                    logger.info(f"使用 multipart 方式发送文件: {media_path}")

                    if media_type == "file":
                        # 文件类型使用文件发送 API
                        result = await self.connector.send_file_to_wechat(
                            file_path=media_path,
                            file_name=os.path.basename(media_path),
                            message=message,
                            touser=target_user
                        )
                    else:
                        # 图片/视频使用媒体发送 API（使用 file_path 参数走 multipart 方式）
                        result = await self.connector.send_media_to_wechat(
                            media_type=media_type,
                            file_path=media_path,
                            message=message,
                            title=os.path.basename(media_path),
                            description=message[:120],
                            touser=target_user
                        )

                    if result.get('status') != 'success':
                        logger.warning(f"媒体发送失败，回退到文本: {result}")
                        result = await self.connector.send_reply_to_wechat(
                            user_id=corp_id,
                            message=f"{message}\n\n[媒体文件: {media_path}]",
                            touser=target_user
                        )
                except Exception as e:
                    logger.error(f"读取或发送媒体文件失败: {e}")
                    result = await self.connector.send_reply_to_wechat(
                        user_id=corp_id,
                        message=f"{message}\n\n[媒体文件: {media_path}]",
                        touser=target_user
                    )
            else:
                # 纯文本回复
                result = await self.connector.send_reply_to_wechat(
                    user_id=corp_id,
                    message=message,
                    touser=target_user
                )

            if result.get('status') == 'success':
                self.stats['responses_sent'] += 1
                logger.info(f"响应已发送到企微 (总计: {self.stats['responses_sent']})")
            else:
                logger.error(f"发送响应失败: {result}")

        except Exception as e:
            logger.error(f"发送响应到企微时出错: {e}")

    def _is_wechat_system_message(self, content: str) -> bool:
        """检查是否是企微系统消息（不需要传给 OpenClaw 的）"""
        if not content:
            return False
        # 企微系统消息关键词
        system_patterns = [
            "收到超大视频，无法在管理端接收",
            "收到超大文件，无法在管理端接收",
            "文件已过期",
            "视频已过期",
            "暂不支持查看此消息",
        ]
        for pattern in system_patterns:
            if pattern in content:
                return True
        return False

    async def _reply_system_message(self, content: str, sender: str):
        """直接回复企微系统消息，不传给 OpenClaw"""
        try:
            wechat_config = self.wechat_config
            corp_id = wechat_config.get('corp_id', '')
            owner_id = wechat_config.get('owner_id', '')

            # 构建目标用户
            if sender and sender != owner_id:
                target_user = f"{sender}|{owner_id}" if owner_id else sender
            elif sender:
                target_user = sender
            else:
                target_user = owner_id or "@all"

            # 回复提示
            if "超大视频" in content or "超大文件" in content:
                reply = "[系统提示] 您发送的文件/视频过大（超过10MB），企微无法处理。请压缩后重新发送，或通过其他方式传输。"
            elif "已过期" in content:
                reply = "[系统提示] 文件/视频已过期，无法下载。"
            else:
                reply = f"[系统提示] 收到无法处理的消息: {content[:50]}"

            logger.info(f"回复系统消息给 {target_user}: {reply[:50]}...")

            result = await self.connector.send_reply_to_wechat(
                user_id=corp_id,
                message=reply,
                touser=target_user
            )

            if result.get('status') == 'success':
                logger.info("系统消息回复成功")
            else:
                logger.error(f"系统消息回复失败: {result}")

        except Exception as e:
            logger.error(f"回复系统消息时出错: {e}")

    # ========== v1.1.0 媒体消息处理方法 ==========

    async def _handle_media_message(self, msg_payload: dict, sender: str):
        """处理媒体消息（图片/视频/语音）v1.1.0"""
        try:
            msg_type = msg_payload.get('type')
            media_id = msg_payload.get('media_id')
            pic_url = msg_payload.get('pic_url')

            logger.info(f"处理 {msg_type} 消息 from {sender}, media_id={media_id}")

            if msg_type == 'image':
                await self._handle_image_message(media_id, pic_url, sender)
            elif msg_type == 'video':
                await self._handle_video_message(media_id, sender)
            elif msg_type == 'voice':
                # 检查企微是否提供语音识别结果
                recognition = msg_payload.get('recognition')
                logger.info(f"[Voice Debug] media_id={media_id}, recognition={recognition}")
                await self._handle_voice_message(
                    media_id,
                    msg_payload.get('format'),
                    sender,
                    recognition=recognition
                )
            elif msg_type == 'file':
                await self._handle_file_message(msg_payload, sender)

            self.stats["messages_forwarded"] += 1

        except Exception as e:
            logger.error(f"处理媒体消息失败: {e}")
            self.stats["messages_failed"] += 1

    async def _handle_image_message(self, media_id: str, pic_url: str, sender: str):
        """处理图片消息"""
        # 记录发送者以便回复
        self.last_sender = sender
        logger.info(f"[Image] 记录发送者: {sender}")

        import base64
        import tempfile

        image_data = None

        # 尝试通过 media_id 下载
        if media_id:
            logger.info(f"下载图片: media_id={media_id}")
            image_data = await self.connector.download_wechat_media(media_id)

        # 如果失败，尝试通过 PicUrl 下载
        if not image_data and pic_url:
            logger.info(f"通过 URL 下载图片: {pic_url}")
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(pic_url) as resp:
                        if resp.status == 200:
                            image_data = await resp.read()
            except Exception as e:
                logger.error(f"下载图片 URL 失败: {e}")

        if not image_data:
            logger.error("无法获取图片数据")
            # 转发文本提示
            await self._forward_to_openclaw("[图片] 下载失败", sender)
            return

        # 保存图片到 file 目录
        image_filename = f"wechat_image_{media_id or 'unknown'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        image_path = str(FILE_STORAGE_DIR / image_filename)

        try:
            with open(image_path, 'wb') as f:
                f.write(image_data)
            logger.info(f"图片已保存: {image_path} ({len(image_data)} bytes)")

            # 转为 base64 用于消息内容
            base64_image = base64.b64encode(image_data).decode('utf-8')

            # 构建消息（包含图片路径和预览）
            message_text = f"[{sender}]: [图片]\n\n路径: {image_path}\n\n预览: data:image/jpeg;base64,{base64_image[:200]}..."

            # 转发到 OpenClaw
            await self._forward_to_openclaw_with_media(
                f"[图片] 路径: {image_path}",
                sender,
                media_type="image",
                media_path=image_path
            )

        except Exception as e:
            logger.error(f"保存图片失败: {e}")
            await self._forward_to_openclaw("[图片] 处理失败", sender)

    async def _handle_video_message(self, media_id: str, sender: str):
        """处理视频消息"""
        # 记录发送者以便回复
        self.last_sender = sender
        logger.info(f"[Video] 记录发送者: {sender}")

        import tempfile

        if not media_id:
            logger.error("视频消息没有 media_id")
            await self._forward_to_openclaw("[视频] 无媒体ID", sender)
            return

        logger.info(f"下载视频: media_id={media_id}")
        video_data = await self.connector.download_wechat_media(media_id)

        if not video_data:
            logger.error("无法获取视频数据")
            await self._forward_to_openclaw("[视频] 下载失败", sender)
            return

        # 检查大小（企微视频通常小于 10MB）
        if len(video_data) > 10 * 1024 * 1024:
            logger.warning(f"视频过大: {len(video_data)} bytes，可能无法处理")

        # 保存视频到 file 目录
        video_filename = f"wechat_video_{media_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        video_path = str(FILE_STORAGE_DIR / video_filename)

        try:
            with open(video_path, 'wb') as f:
                f.write(video_data)
            logger.info(f"视频已保存: {video_path} ({len(video_data)} bytes)")

            # 转发到 OpenClaw
            await self._forward_to_openclaw_with_media(
                f"[视频] 路径: {video_path}\n大小: {len(video_data)} bytes",
                sender,
                media_type="video",
                media_path=video_path
            )

        except Exception as e:
            logger.error(f"保存视频失败: {e}")
            await self._forward_to_openclaw("[视频] 处理失败", sender)

    async def _handle_voice_message(self, media_id: str, format_type: str, sender: str, recognition: str = None):
        """处理语音消息 v1.1.0 增强版 - 支持语音识别和格式转换"""
        # 记录发送者以便回复
        self.last_sender = sender
        logger.info(f"[Voice] 记录发送者: {sender}")

        import tempfile

        if not media_id:
            logger.error("语音消息没有 media_id")
            await self._forward_to_openclaw("[语音] 无媒体ID", sender)
            return

        # 如果企微已经提供了语音识别结果，直接使用
        if recognition:
            logger.info(f"使用企微语音识别结果: {recognition[:50]}...")
            voice_info = f"[语音] 识别结果: {recognition}\n[语音消息，已自动转文字]"
            await self._forward_to_openclaw(voice_info, sender)
            return

        logger.info(f"下载语音: media_id={media_id}, format={format_type}")
        voice_data = await self.connector.download_wechat_media(media_id)

        if not voice_data:
            logger.error("无法获取语音数据")
            await self._forward_to_openclaw("[语音] 下载失败", sender)
            return

        # 保存语音到 file 目录
        voice_ext = format_type or 'amr'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        voice_filename = f"wechat_voice_{media_id}_{timestamp}.{voice_ext}"
        wav_filename = f"wechat_voice_{media_id}_{timestamp}.wav"
        voice_path = str(FILE_STORAGE_DIR / voice_filename)
        wav_path = str(FILE_STORAGE_DIR / wav_filename)

        try:
            with open(voice_path, 'wb') as f:
                f.write(voice_data)
            logger.info(f"语音已保存: {voice_path} ({len(voice_data)} bytes)")

            # 尝试转换为 WAV 格式（OpenClaw 更容易处理）
            conversion_success = False
            try:
                conversion_success = await self._convert_voice_to_wav(voice_path, wav_path, voice_ext)
            except Exception as e:
                logger.warning(f"语音转换失败: {e}")

            # 使用语音识别（如果可用）
            transcribed_text = None
            try:
                transcribed_text = await self._transcribe_voice(wav_path if conversion_success else voice_path)
            except Exception as e:
                logger.warning(f"语音识别失败: {e}")

            # 构建消息内容
            if transcribed_text:
                voice_info = f"[语音] 内容: {transcribed_text}\n文件: {voice_path}"
            else:
                voice_info = f"[语音] 路径: {voice_path}\n格式: {voice_ext}"
                if conversion_success:
                    voice_info += f"\nWAV: {wav_path}"

            # 转发到 OpenClaw
            await self._forward_to_openclaw_with_media(
                voice_info,
                sender,
                media_type="voice",
                media_path=wav_path if conversion_success else voice_path
            )

        except Exception as e:
            logger.error(f"保存语音失败: {e}")
            await self._forward_to_openclaw("[语音] 处理失败", sender)

    async def _convert_voice_to_wav(self, input_path: str, output_path: str, input_format: str) -> bool:
        """
        转换语音格式到 WAV
        支持: amr (企微默认), silk, mp3 等
        """
        try:
            import subprocess

            if input_format.lower() == 'amr':
                # 使用 ffmpeg 转换 AMR 到 WAV
                cmd = [
                    'ffmpeg', '-y', '-i', input_path,
                    '-ar', '16000', '-ac', '1', '-acodec', 'pcm_s16le',
                    output_path
                ]
            elif input_format.lower() == 'silk':
                # SILK 格式（微信语音）
                # 需要 silk_decoder
                cmd = ['silk_decoder', input_path, output_path]
            else:
                # 其他格式直接用 ffmpeg
                cmd = ['ffmpeg', '-y', '-i', input_path, output_path]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0 and os.path.exists(output_path):
                logger.info(f"语音转换成功: {input_path} -> {output_path}")
                return True
            else:
                logger.warning(f"语音转换失败: {stderr.decode()[:200]}")
                return False

        except FileNotFoundError:
            logger.warning("ffmpeg 或 silk_decoder 未安装，跳过语音转换")
            return False
        except Exception as e:
            logger.error(f"语音转换错误: {e}")
            return False

    async def _transcribe_voice(self, voice_path: str) -> str:
        """
        语音识别 (STT) - 优先使用 Sherpa-ONNX，回退到 Whisper
        """
        if not os.path.exists(voice_path):
            logger.error(f"音频文件不存在: {voice_path}")
            return None

        # 首先尝试使用 Sherpa-ONNX (如果可用)
        if SHERPA_AVAILABLE and transcribe_voice_sherpa:
            try:
                logger.info(f"使用 Sherpa-ONNX 识别语音: {voice_path}")

                loop = asyncio.get_event_loop()
                text = await loop.run_in_executor(
                    None,
                    lambda: transcribe_voice_sherpa(voice_path)
                )

                if text:
                    logger.info(f"Sherpa-ONNX 识别成功: {text[:50]}...")
                    return text
                else:
                    logger.warning("Sherpa-ONNX 识别返回空结果，尝试 Whisper")

            except Exception as e:
                logger.warning(f"Sherpa-ONNX 识别失败: {e}，尝试 Whisper")

        # 回退到 Whisper
        try:
            logger.info(f"使用 Whisper 识别语音: {voice_path}")

            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(
                None,
                lambda: transcribe_voice(voice_path, language="zh", model_size="tiny")
            )

            if text:
                logger.info(f"Whisper 识别成功: {text[:50]}...")
                return text
            else:
                logger.warning("Whisper 识别返回空结果")
                return None

        except Exception as e:
            logger.warning(f"Whisper 识别失败: {e}")
            return None

    async def _handle_file_message(self, msg_payload: dict, sender: str):
        """处理文件消息 (MD, TXT, PDF, etc.) v1.2.0 - 支持文件下载"""
        # 记录发送者以便回复
        self.last_sender = sender
        logger.info(f"[File] 记录发送者: {sender}")

        file_key = msg_payload.get('file_key')
        file_name = msg_payload.get('file_name', 'unknown')
        file_ext = msg_payload.get('file_ext', '')
        file_size = msg_payload.get('file_size', 0)

        logger.info(f"处理文件消息: {file_name}.{file_ext} ({file_size} bytes) from {sender}")

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = f"{file_name}_{timestamp}.{file_ext}" if file_ext else f"{file_name}_{timestamp}"
        file_path = str(FILE_STORAGE_DIR / safe_filename)

        # 下载文件
        if file_key and hasattr(self.connector, 'download_wechat_file'):
            try:
                file_data = await self.connector.download_wechat_file(file_key, safe_filename)
                if file_data:
                    with open(file_path, 'wb') as f:
                        f.write(file_data)
                    logger.info(f"文件已下载: {file_path} ({len(file_data)} bytes)")
                else:
                    logger.error(f"文件下载失败: {file_name}")
                    file_path = None
            except Exception as e:
                logger.error(f"下载文件异常: {e}")
                file_path = None
        else:
            logger.warning(f"无法下载文件: 缺少 file_key 或 download_wechat_file 方法")
            file_path = None

        # 转发文件信息到 OpenClaw
        if file_path:
            file_info = f"[文件] {file_name}.{file_ext}\n大小: {file_size} bytes\n路径: {file_path}"
        else:
            file_info = f"[文件] {file_name}.{file_ext}\n大小: {file_size} bytes\n下载失败"

        await self._forward_to_openclaw_with_media(
            file_info,
            sender,
            media_type="file",
            media_path=file_path
        )

        logger.info(f"文件信息已转发: {file_name}")

    def _forward_to_openclaw_with_media_sync(self, content: str, sender: str, media_type: str = None, media_path: str = None) -> dict:
        """同步方式转发媒体消息到 OpenClaw"""
        try:
            import subprocess
            import hashlib
            import time

            # 防护：确保 content 不为 None 或空
            if not content:
                logger.warning(f"尝试转发空内容（媒体消息），跳过: sender={sender}")
                return {"success": False, "error": "Empty content"}

            # 在消息内容中添加[sender]标识
            message_text = f"[{sender}] {content}"

            # 计算内容哈希，用于后续关联响应
            content_hash = hashlib.md5(content.encode()).hexdigest()

            # 构建目标用户（用于后续回复）- 发给发送者，抄送owner
            wechat_config = self.wechat_config
            owner_id = wechat_config.get('owner_id', '')
            if sender and sender != owner_id:
                # 发给发送者 + 抄送owner
                target_user = f"{sender}|{owner_id}" if owner_id else sender
            elif sender:
                # 发送者就是owner，只发给owner
                target_user = sender
            else:
                target_user = owner_id or "@all"

            # 记录待处理响应的预期目标用户和问题内容（5分钟过期）
            self._pending_responses[content_hash] = (target_user, time.time(), content, sender)
            logger.info(f"[Pending-Media] 记录响应目标: {target_user}, hash={content_hash[:8]}..., sender={sender}")

            # 清理过期的pending记录（超过5分钟）
            current_time = time.time()
            expired_hashes = [h for h, (_, ts, _, _) in self._pending_responses.items() if current_time - ts > 300]
            for h in expired_hashes:
                del self._pending_responses[h]

            # 注意：不要直接写入 session 文件，让 OpenClaw agent 自己处理
            # 直接触发 Agent
            try:
                # 将媒体信息附加到消息文本中（openclaw agent 不支持 --media-type 和 --media-path 参数）
                if media_type and media_path:
                    message_text = f"{message_text}\n\n[媒体:{media_type}] {media_path}"
                    logger.info(f"[Media] 消息中附加媒体信息: type={media_type}, path={media_path}")

                cmd = [
                    self.openclaw_cmd,
                    "agent",
                    "--session-id", self.openclaw_session_id,
                    "--message", message_text,
                    "--thinking", "low"
                ]

                logger.info(f"触发 OpenClaw agent: {self.openclaw_cmd}")

                subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=(sys.platform == 'win32')
                )
                logger.info("Agent 已触发")
            except Exception as e:
                logger.warning(f"触发 agent 失败: {e}")

            return {"success": True}

        except Exception as e:
            logger.error(f"写入 session 文件失败: {e}")
            return {"success": False, "error": str(e)}

    async def _forward_to_openclaw_with_media(self, content: str, sender: str, media_type: str = None, media_path: str = None) -> dict:
        """转发媒体消息到 OpenClaw"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._forward_to_openclaw_with_media_sync,
            content,
            sender,
            media_type,
            media_path
        )

    async def run(self):
        """运行桥接器"""
        # 首先异步初始化（获取配置）
        try:
            await self.initialize()
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            return

        logger.info("=" * 60)
        logger.info("企微 <-> OpenClaw 双向消息桥接器")
        logger.info("=" * 60)
        logger.info(f"Session ID: {self.openclaw_session_id}")
        logger.info(f"Session File: {self.openclaw_session_file}")
        logger.info(f"Device: {self.server_config.device_id}")
        logger.info("=" * 60)

        # 检查 session 文件
        if not os.path.exists(self.openclaw_session_file):
            logger.error(f"Session 文件不存在: {self.openclaw_session_file}")
            return

        # 初始化行数
        with open(self.openclaw_session_file, 'r', encoding='utf-8') as f:
            self.last_line_count = len(f.readlines())
        logger.info(f"当前 session 文件行数: {self.last_line_count}")

        # 连接 SillyMD
        logger.info("连接 SillyMD WebSocket...")
        connected = await self.connector.connect_websocket()
        if not connected:
            logger.error("无法连接到 SillyMD")
            return

        logger.info("SillyMD 连接成功，启动响应监控...")

        # 启动响应监控任务
        self.response_monitor_task = asyncio.create_task(self._monitor_responses())

        try:
            await self.connector.run_websocket_loop()
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在关闭...")
        finally:
            if self.response_monitor_task:
                self.response_monitor_task.cancel()
                try:
                    await self.response_monitor_task
                except asyncio.CancelledError:
                    pass

            logger.info("桥接器已停止")
            logger.info(f"统计: 接收={self.stats['messages_received']}, "
                       f"转发={self.stats['messages_forwarded']}, "
                       f"响应={self.stats['responses_sent']}, "
                       f"失败={self.stats['messages_failed']}")


if __name__ == "__main__":
    bridge = WeComToOpenClawBridge(session_key="main")
    asyncio.run(bridge.run())
