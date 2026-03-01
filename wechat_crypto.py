"""
企业微信消息加解密工具
使用 AES-CBC 模式， PKCS7 填充
"""

import base64
import hashlib
import random
import string
import struct
import time
from Crypto.Cipher import AES


class WeChatCrypto:
    """企业微信消息加解密类"""

    def __init__(self, token: str, encoding_aes_key: str, corp_id: str):
        """
        初始化
        :param token: 企业微信后台设置的 Token
        :param encoding_aes_key: 企业微信后台设置的 EncodingAESKey (43字符)
        :param corp_id: 企业ID
        """
        self.token = token
        self.corp_id = corp_id

        # EncodingAESKey 需要 Base64 解码，前面补上 16 字节得到 32 字节密钥
        self.aes_key = base64.b64decode(encoding_aes_key + '=')
        # 注意：每次加密/解密都需要创建新的 cipher 实例

    def verify_url(self, signature: str, timestamp: str, nonce: str, echostr: str) -> str:
        """
        验证 URL 并返回解密后的 echostr
        :param signature: 签名
        :param timestamp: 时间戳
        :param nonce: 随机数
        :param echostr: 加密的随机字符串
        :return: 解密后的 echostr
        """
        # 验证签名（URL验证时签名包含echostr）
        if not self._verify_signature(signature, timestamp, nonce, echostr):
            raise ValueError("Invalid signature")

        # 解密 echostr
        return self._decrypt(echostr)

    def decrypt_msg(self, signature: str, timestamp: str, nonce: str, msg_encrypt: str) -> str:
        """
        解密消息
        :param signature: 签名
        :param timestamp: 时间戳
        :param nonce: 随机数
        :param msg_encrypt: 加密的消息
        :return: 解密后的消息 XML
        """
        # 验证签名（消息加解密时签名包含加密消息）
        if not self._verify_signature(signature, timestamp, nonce, msg_encrypt):
            raise ValueError("Invalid signature")

        # 解密消息
        return self._decrypt(msg_encrypt)

    def encrypt_msg(self, msg: str, nonce: str = None, timestamp: str = None) -> tuple:
        """
        加密消息
        :param msg: 明文消息
        :param nonce: 随机数（可选）
        :param timestamp: 时间戳（可选）
        :return: (signature, timestamp, nonce, msg_encrypt)
        """
        if nonce is None:
            nonce = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        if timestamp is None:
            timestamp = str(int(time.time()))

        # 加密消息
        msg_encrypt = self._encrypt(msg)

        # 生成签名
        signature = self._generate_signature(timestamp, nonce, msg_encrypt)

        return signature, timestamp, nonce, msg_encrypt

    def _verify_signature(self, signature: str, timestamp: str, nonce: str, msg_encrypt: str = None) -> bool:
        """验证签名"""
        expected = self._generate_signature(timestamp, nonce, msg_encrypt)
        return signature == expected

    def _generate_signature(self, timestamp: str, nonce: str, msg_encrypt: str = None) -> str:
        """生成签名
        注意：URL验证时msg_encrypt为None，不包含在签名中
              消息加解密时msg_encrypt有值，需要包含在签名中
        """
        # URL验证时只使用 token, timestamp, nonce
        if msg_encrypt is None:
            data = [self.token, timestamp, nonce]
        else:
            # 消息加解密时使用 token, timestamp, nonce, msg_encrypt
            data = [self.token, timestamp, nonce, msg_encrypt]
        data.sort()
        sha1 = hashlib.sha1()
        sha1.update(''.join(data).encode())
        return sha1.hexdigest()

    def _encrypt(self, msg: str) -> str:
        """加密消息"""
        # 随机 16 字节 + 4字节消息长度 + 消息 + corp_id + PKCS7 填充
        random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        msg_len = struct.pack('>I', len(msg.encode()))  # 使用大端序（网络字节序）
        msg_bytes = msg.encode()
        corp_id_bytes = self.corp_id.encode()

        to_encrypt = random_str.encode() + msg_len + msg_bytes + corp_id_bytes
        to_encrypt = self._pkcs7_encode(to_encrypt)

        # 创建新的 cipher 实例（PyCryptoDome cipher 不能复用）
        cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_key[:16])
        encrypted = cipher.encrypt(to_encrypt)
        return base64.b64encode(encrypted).decode()

    def _decrypt(self, msg_encrypt: str) -> str:
        """解密消息
        格式：random(16B) + msg_len(4B, network order) + msg + CorpID
        """
        encrypted = base64.b64decode(msg_encrypt)

        # 创建新的 cipher 实例（PyCryptoDome cipher 不能复用）
        cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_key[:16])
        decrypted = cipher.decrypt(encrypted)

        # 去除 PKCS7 填充
        decrypted = self._pkcs7_decode(decrypted)

        # 解析：16字节随机 + 4字节长度(网络字节序) + 消息 + corp_id
        random_bytes = decrypted[:16]
        msg_len = struct.unpack('>I', decrypted[16:20])[0]  # 大端序(网络字节序)
        msg = decrypted[20:20 + msg_len].decode('utf-8')
        corp_id = decrypted[20 + msg_len:].decode('utf-8')

        return msg

    def _pkcs7_encode(self, data: bytes) -> bytes:
        """PKCS7 填充"""
        block_size = 32
        pad_len = block_size - (len(data) % block_size)
        padding = bytes([pad_len] * pad_len)
        return data + padding

    def _pkcs7_decode(self, data: bytes) -> bytes:
        """去除 PKCS7 填充"""
        pad_len = data[-1]
        return data[:-pad_len]


def verify_wechat_signature(token: str, signature: str, timestamp: str, nonce: str, msg_encrypt: str = None) -> bool:
    """
    验证企业微信签名
    :param token: 企业微信Token
    :param signature: 签名
    :param timestamp: 时间戳
    :param nonce: 随机数
    :param msg_encrypt: 加密消息（URL验证时为None，消息加解密时有值）
    :return: 验证结果
    """
    if msg_encrypt is None:
        # URL验证时只使用 token, timestamp, nonce
        data = [token, timestamp, nonce]
    else:
        # 消息加解密时包含 msg_encrypt
        data = [token, timestamp, nonce, msg_encrypt]
    data.sort()
    sha1 = hashlib.sha1()
    sha1.update(''.join(data).encode())
    return signature == sha1.hexdigest()
