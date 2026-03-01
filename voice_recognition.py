# -*- coding: utf-8 -*-
"""
语音识别模块 - 支持本地 Whisper 和远程 ASR 服务 v1.2.0
作为 SillyMD 桥接器的内置能力
"""
import os
import sys
import logging
import tempfile
import json
import base64
import asyncio
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 将本地 whisper 添加到路径
WHISPER_PATH = Path(__file__).parent / "whisper_local"
if str(WHISPER_PATH) not in sys.path:
    sys.path.insert(0, str(WHISPER_PATH))

# 远程 ASR 服务配置
REMOTE_ASR_URL = os.getenv("REMOTE_ASR_URL", "ws://47.96.152.144:10095")

class VoiceRecognizer:
    """语音识别器 - 使用本地 Whisper"""

    def __init__(self, model_size: str = "tiny"):
        """
        初始化语音识别器

        Args:
            model_size: 模型大小 (tiny, base, small, medium, large)
        """
        self.model_size = model_size
        self.model = None
        self.device = "cpu"  # 默认使用 CPU

    def load_model(self):
        """加载 Whisper 模型"""
        if self.model is not None:
            return True

        try:
            # 延迟导入，避免启动时加载
            import torch
            from whisper_local import load_model

            logger.info(f"正在加载 Whisper 模型: {self.model_size}")

            # 检查模型文件是否存在
            model_dir = Path.home() / ".cache" / "whisper"
            model_file = model_dir / f"{self.model_size}.pt"

            if not model_file.exists():
                logger.warning(f"模型文件不存在: {model_file}")
                logger.info("尝试下载模型...")
                # 模型会自动下载

            self.model = load_model(self.model_size)
            logger.info(f"Whisper 模型加载成功: {self.model_size}")
            return True

        except ImportError as e:
            logger.error(f"Whisper 依赖未安装: {e}")
            logger.error("请安装: pip install torch tqdm")
            return False
        except Exception as e:
            logger.error(f"加载 Whisper 模型失败: {e}")
            return False

    def transcribe(self, audio_path: str, language: str = "zh") -> str:
        """
        识别语音文件

        Args:
            audio_path: 音频文件路径
            language: 语言代码 (zh=中文, en=英文)

        Returns:
            识别出的文字
        """
        if not os.path.exists(audio_path):
            logger.error(f"音频文件不存在: {audio_path}")
            return None

        # 尝试加载模型
        if not self.load_model():
            return None

        try:
            from whisper_local.transcribe import transcribe
            from whisper_local.audio import load_audio

            logger.info(f"开始识别: {audio_path}")

            # 加载音频
            audio = load_audio(audio_path)

            # 识别
            result = transcribe(
                self.model,
                audio,
                language=language,
                task="transcribe",
                fp16=False  # CPU 模式
            )

            text = result.get("text", "").strip()
            logger.info(f"识别结果: {text[:50]}...")

            return text

        except Exception as e:
            logger.error(f"语音识别失败: {e}")
            return None

    def transcribe_sync(self, audio_path: str, language: str = "zh") -> str:
        """同步方式识别（用于异步环境中调用）"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return self.transcribe(audio_path, language)


# ========== 远程 ASR 服务识别器 (FunASR) ==========

class RemoteASRRecognizer:
    """远程 ASR 服务识别器 - 使用部署在服务器上的 FunASR"""

    def __init__(self, service_url: str = None):
        """
        初始化远程 ASR 识别器

        Args:
            service_url: ASR 服务 WebSocket 地址
        """
        self.service_url = service_url or REMOTE_ASR_URL
        self.connected = False

    async def transcribe(self, audio_path: str) -> Optional[str]:
        """
        使用远程 ASR 服务识别语音

        Args:
            audio_path: 音频文件路径 (WAV 格式, 16kHz, 16bit, 单声道)

        Returns:
            识别出的文字
        """
        # 转换为绝对路径
        audio_path = os.path.abspath(audio_path)

        if not os.path.exists(audio_path):
            logger.error(f"音频文件不存在: {audio_path}")
            return None

        try:
            import websockets
        except ImportError:
            logger.error("websockets 模块未安装，请运行: pip install websockets")
            return None

        try:
            logger.info(f"连接远程 ASR 服务: {self.service_url}")

            # 等待文件完全写入（避免 ffmpeg 正在写入时读取）
            import time
            time.sleep(0.5)

            # 读取音频文件
            with open(audio_path, 'rb') as f:
                audio_data = f.read()

            # 使用 WebSocket 连接 FunASR 服务
            async with websockets.connect(self.service_url) as websocket:
                # 发送配置消息
                config_msg = {
                    "mode": "offline",
                    "wav_format": "pcm",
                    "wav_name": "voice_msg",
                    "is_speaking": True
                }
                await websocket.send(json.dumps(config_msg))
                logger.info(f"已发送配置: {config_msg}")

                # 发送音频数据（分块）
                chunk_size = 3200  # 100ms @ 16kHz 16bit
                for i in range(0, len(audio_data), chunk_size):
                    chunk = audio_data[i:i+chunk_size]
                    await websocket.send(chunk)
                    await asyncio.sleep(0.1)

                # 发送结束标记
                await websocket.send(json.dumps({"is_speaking": False}))
                logger.info(f"已发送音频数据: {len(audio_data)} bytes")

                # 接收识别结果
                results = []
                try:
                    while True:
                        response = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=60.0
                        )

                        if isinstance(response, str):
                            data = json.loads(response)
                            logger.debug(f"收到响应: {data}")

                            # 检查是否是最终结果
                            if data.get('is_final') or data.get('mode') == 'offline':
                                text = data.get('text', '')
                                if text:
                                    results.append(text)
                                break
                            else:
                                # 中间结果
                                text = data.get('text', '')
                                if text:
                                    results.append(text)
                        else:
                            # 二进制数据，忽略
                            pass

                except asyncio.TimeoutError:
                    logger.warning("ASR 服务响应超时")

                final_text = ' '.join(results).strip()
                logger.info(f"远程 ASR 识别结果: {final_text[:50]}...")
                return final_text

        except Exception as e:
            logger.error(f"远程 ASR 识别失败: {e}")
            return None

    def transcribe_sync(self, audio_path: str) -> Optional[str]:
        """同步方式识别"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.transcribe(audio_path))


# 全局识别器实例
_recognizer = None
_remote_recognizer = None

def get_recognizer(model_size: str = "tiny") -> VoiceRecognizer:
    """获取本地识别器实例"""
    global _recognizer
    if _recognizer is None:
        _recognizer = VoiceRecognizer(model_size)
    return _recognizer


def get_remote_recognizer(service_url: str = None) -> RemoteASRRecognizer:
    """获取远程 ASR 识别器实例"""
    global _remote_recognizer
    if _remote_recognizer is None:
        _remote_recognizer = RemoteASRRecognizer(service_url)
    return _remote_recognizer


def transcribe_voice(audio_path: str, language: str = "zh", model_size: str = "tiny", use_remote: bool = True) -> str:
    """
    便捷函数：识别语音文件

    Args:
        audio_path: 音频文件路径
        language: 语言代码
        model_size: 模型大小 (本地 Whisper 使用)
        use_remote: 是否优先使用远程 ASR 服务

    Returns:
        识别出的文字
    """
    # 优先使用远程 ASR 服务
    if use_remote and REMOTE_ASR_URL:
        try:
            recognizer = get_remote_recognizer()
            result = recognizer.transcribe_sync(audio_path)
            if result:
                return result
            logger.warning("远程 ASR 识别失败，尝试本地 Whisper")
        except Exception as e:
            logger.warning(f"远程 ASR 不可用: {e}")

    # 使用本地 Whisper
    recognizer = get_recognizer(model_size)
    return recognizer.transcribe(audio_path, language)


# 测试代码
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # 测试识别
    test_file = "file/wechat_voice_xxx.wav"
    if os.path.exists(test_file):
        result = transcribe_voice(test_file)
        print(f"识别结果: {result}")
    else:
        print(f"测试文件不存在: {test_file}")
        print("请先生成语音文件后再测试")
