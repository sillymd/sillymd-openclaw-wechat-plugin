# -*- coding: utf-8 -*-
"""
配置管理模块
管理服务器连接配置和应用配置
"""
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, asdict
from logging_config import get_module_logger

logger = get_module_logger("config_manager")


@dataclass
class ServerConfig:
    """服务器配置"""
    # 服务器基础地址 (HTTPS REST API)
    base_url: str = "https://websocket.sillymd.com"
    # WebSocket URL (WSS)
    ws_url: str = "wss://websocket.sillymd.com/ws"
    # API Key (必要)
    api_key: str = ""
    # JWT Token (自动获取)
    jwt_token: str = ""
    # 租户 ID (自动获取)
    tenant_id: str = ""
    # 设备 ID (格式: tenant_id:device_name, 自动获取)
    device_id: str = ""
    # 企业微信配置 (从后端获取)
    wechat: dict = None
    # OpenClaw 配置 (自动创建)
    openclaw: dict = None
    # 桥接器配置
    bridge: dict = None

    def __post_init__(self):
        """初始化后处理"""
        if self.wechat is None:
            self.wechat = {}
        if self.openclaw is None:
            self.openclaw = {}
        if self.bridge is None:
            self.bridge = {
                "save_chat_history": True,
                "save_voice_files": False,
                "health_check_enabled": True
            }
        # 如果 ws_url 为空，从 base_url 自动生成
        if not self.ws_url and self.base_url:
            self.ws_url = self.base_url.replace('https://', 'wss://').replace('http://', 'ws://') + '/ws'

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)

    def validate(self) -> Tuple[bool, str]:
        """
        验证配置

        Returns:
            tuple: (是否有效, 错误信息)
        """
        if not self.api_key:
            return False, "API Key 不能为空"

        if not self.base_url:
            return False, "服务器地址不能为空"

        # device_id 和 tenant_id 可以自动获取，不需要强制
        return True, ""

    def validate_runtime(self) -> Tuple[bool, str]:
        """
        运行时验证（自动获取配置后）

        Returns:
            tuple: (是否有效, 错误信息)
        """
        if not self.api_key:
            return False, "API Key 不能为空"

        if not self.jwt_token:
            return False, "JWT Token 未获取"

        if not self.tenant_id:
            return False, "Tenant ID 未获取"

        return True, ""

    @classmethod
    def from_dict(cls, data: dict) -> 'ServerConfig':
        """从字典创建配置"""
        return cls(**{
            k: v for k, v in data.items()
            if k in cls.__dataclass_fields__
        })


@dataclass
class AppConfig:
    """应用配置"""
    # 数据库路径
    db_path: str = "sillymd.db"
    # 日志级别
    log_level: str = "INFO"
    # 是否启用 WebSocket
    enable_websocket: bool = True
    # 是否启用消息去重
    enable_deduplication: bool = True
    # 是否启用日志记录
    enable_logging: bool = True
    # WebSocket 重连最大次数
    max_reconnect_attempts: int = 5
    # WebSocket 心跳间隔（秒）
    ws_ping_interval: int = 20

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'AppConfig':
        """从字典创建配置"""
        return cls(**{
            k: v for k, v in data.items()
            if k in cls.__dataclass_fields__
        })


class ConfigManager:
    """配置管理器"""

    def __init__(self, config_dir: Optional[Path] = None):
        """
        初始化配置管理器

        Args:
            config_dir: 配置文件目录，默认为当前目录
        """
        self.logger = logger
        self.config_dir = config_dir or Path(__file__).parent
        # 使用新的简化配置文件 config.json
        self.server_config_file = self.config_dir / "config.json"
        self.app_config_file = self.config_dir / "config_app.json"

        self.server_config: Optional[ServerConfig] = None
        self.app_config: Optional[AppConfig] = None

    def load_server_config(self, config_file: Optional[Path] = None) -> ServerConfig:
        """
        加载服务器配置
        支持简化配置 (config.json) 或完整配置 (config_server.json)

        Args:
            config_file: 配置文件路径，默认为 config.json

        Returns:
            ServerConfig: 服务器配置对象
        """
        # 优先使用指定的配置文件
        if config_file:
            config_files = [config_file]
        else:
            # 优先查找简化配置 config.json，然后兼容旧版 config_server.json
            config_files = [self.config_dir / "config.json", self.server_config_file]

        for cfg_file in config_files:
            if cfg_file.exists():
                try:
                    with open(cfg_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    self.server_config = ServerConfig.from_dict(data)

                    # 验证必要配置 (api_key)
                    is_valid, error_msg = self.server_config.validate()
                    if not is_valid:
                        self.logger.warning(f"服务器配置验证失败: {error_msg}")
                    else:
                        self.logger.info(f"服务器配置已加载: {cfg_file}")
                        return self.server_config

                except Exception as e:
                    self.logger.error(f"加载配置文件失败 {cfg_file}: {e}")
                    continue

        # 没有找到有效配置文件，返回默认配置
        self.logger.warning("未找到有效配置文件，使用默认配置")
        self.logger.info("请创建 config.json 文件，包含 api_key 和 wechat.owner_id")
        self.server_config = ServerConfig()
        return self.server_config

    def save_server_config(self, config: ServerConfig, config_file: Optional[Path] = None) -> bool:
        """
        保存服务器配置（完整配置，向后兼容）

        Args:
            config: 服务器配置对象
            config_file: 配置文件路径，默认为 config_server.json

        Returns:
            bool: 是否保存成功
        """
        config_file = config_file or self.server_config_file

        try:
            # 验证配置
            is_valid, error_msg = config.validate()
            if not is_valid:
                self.logger.error(f"配置验证失败: {error_msg}")
                return False

            # 保存配置
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)

            self.server_config = config
            self.logger.info(f"服务器配置已保存: {config_file}")
            return True

        except Exception as e:
            self.logger.error(f"保存服务器配置失败: {e}", exc_info=e)
            return False

    def save_minimal_config(self, config: ServerConfig, config_file: Optional[Path] = None) -> bool:
        """
        保存最小化配置（仅保存用户必填字段）
        从API获取的配置（tenant_id, wechat等）不保存到文件，只在内存中使用

        Args:
            config: 服务器配置对象
            config_file: 配置文件路径，默认为 config.json

        Returns:
            bool: 是否保存成功
        """
        config_file = config_file or (self.config_dir / "config.json")

        try:
            # 只保存必要的用户配置
            minimal_data = {
                "api_key": config.api_key,
                "wechat": {
                    "owner_id": config.wechat.get('owner_id', '') if config.wechat else ''
                }
            }

            # 保存最小配置
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(minimal_data, f, ensure_ascii=False, indent=2)

            self.logger.info(f"最小化配置已保存: {config_file}")
            return True

        except Exception as e:
            self.logger.error(f"保存最小化配置失败: {e}", exc_info=e)
            return False

    def load_app_config(self, config_file: Optional[Path] = None) -> AppConfig:
        """
        加载应用配置

        Args:
            config_file: 配置文件路径，默认为 config_app.json

        Returns:
            AppConfig: 应用配置对象
        """
        config_file = config_file or self.app_config_file

        if not config_file.exists():
            self.logger.info(f"应用配置文件不存在: {config_file}，使用默认配置")
            self.app_config = AppConfig()
            return self.app_config

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.app_config = AppConfig.from_dict(data)
            self.logger.info(f"应用配置已加载: {config_file}")
            return self.app_config

        except Exception as e:
            self.logger.error(f"加载应用配置失败: {e}", exc_info=e)
            self.app_config = AppConfig()
            return self.app_config

    def save_app_config(self, config: AppConfig, config_file: Optional[Path] = None) -> bool:
        """
        保存应用配置

        Args:
            config: 应用配置对象
            config_file: 配置文件路径，默认为 config_app.json

        Returns:
            bool: 是否保存成功
        """
        config_file = config_file or self.app_config_file

        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)

            self.app_config = config
            self.logger.info(f"应用配置已保存: {config_file}")
            return True

        except Exception as e:
            self.logger.error(f"保存应用配置失败: {e}", exc_info=e)
            return False

    def load_all_configs(self) -> Tuple[ServerConfig, AppConfig]:
        """
        加载所有配置

        Returns:
            tuple: (服务器配置, 应用配置)
        """
        server_config = self.load_server_config()
        app_config = self.load_app_config()
        return server_config, app_config

    def get_server_config(self) -> ServerConfig:
        """获取服务器配置"""
        if self.server_config is None:
            self.server_config = self.load_server_config()
        return self.server_config

    def get_app_config(self) -> AppConfig:
        """获取应用配置"""
        if self.app_config is None:
            self.app_config = self.load_app_config()
        return self.app_config


# 便捷函数

def get_config_manager(config_dir: Optional[Path] = None) -> ConfigManager:
    """
    获取配置管理器实例

    Args:
        config_dir: 配置文件目录

    Returns:
        ConfigManager: 配置管理器实例
    """
    return ConfigManager(config_dir)


def load_server_config(config_file: Optional[Path] = None) -> ServerConfig:
    """
    快捷加载服务器配置

    Args:
        config_file: 配置文件路径

    Returns:
        ServerConfig: 服务器配置对象
    """
    manager = ConfigManager()
    return manager.load_server_config(config_file)


def load_app_config(config_file: Optional[Path] = None) -> AppConfig:
    """
    快捷加载应用配置

    Args:
        config_file: 配置文件路径

    Returns:
        AppConfig: 应用配置对象
    """
    manager = ConfigManager()
    return manager.load_app_config(config_file)


if __name__ == "__main__":
    # 测试配置管理器
    manager = get_config_manager()

    # 加载配置
    server_config, app_config = manager.load_all_configs()

    print("服务器配置:")
    print(json.dumps(server_config.to_dict(), indent=2, ensure_ascii=False))

    print("\n应用配置:")
    print(json.dumps(app_config.to_dict(), indent=2, ensure_ascii=False))
