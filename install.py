#!/usr/bin/env python3
"""
SillyMD 企业微信通道插件安装脚本
支持离线安装所有依赖
"""

import os
import sys
import subprocess
import glob
from pathlib import Path

def print_banner():
    print("=" * 60)
    print("SillyMD 企业微信通道插件 - 安装程序")
    print("SillyMD WeCom Channel Plugin Installer")
    print("=" * 60)
    print()

def check_python_version():
    """检查 Python 版本"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"错误: 需要 Python 3.8+，当前版本: {version.major}.{version.minor}")
        return False
    print(f"[OK] Python 版本: {version.major}.{version.minor}.{version.micro}")
    return True

def install_from_wheels():
    """从 wheels 目录安装依赖"""
    wheels_dir = Path(__file__).parent / "wheels"

    if not wheels_dir.exists():
        print("[FAIL] 未找到 wheels 目录，跳过离线安装")
        return False

    wheels = list(wheels_dir.glob("*.whl"))
    if not wheels:
        print("[FAIL] wheels 目录为空")
        return False

    print(f"\n正在从 wheels 安装依赖 ({len(wheels)} 个包)...")
    print("-" * 60)

    success_count = 0
    fail_count = 0

    for wheel in sorted(wheels):
        wheel_name = wheel.name
        print(f"安装: {wheel_name[:50]}...", end=" ")

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", str(wheel), "--no-deps"],
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode == 0:
                print("[OK]")
                success_count += 1
            else:
                print("[FAIL]")
                print(f"  错误: {result.stderr[:100]}")
                fail_count += 1
        except Exception as e:
            print(f"[FAIL] ({e})")
            fail_count += 1

    print("-" * 60)
    print(f"安装完成: 成功 {success_count} 个, 失败 {fail_count} 个")
    return fail_count == 0

def install_other_dependencies():
    """安装其他依赖（通过 pip）"""
    print("\n安装其他依赖...")
    print("-" * 60)

    # 基础依赖（通常已有）
    basic_deps = [
        "requests",
        "websockets",
        "python-dotenv",
        "cryptography",
    ]

    for dep in basic_deps:
        print(f"安装: {dep}...", end=" ")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", dep, "-q"],
                capture_output=True,
                timeout=60
            )
            print("[OK]" if result.returncode == 0 else "跳过")
        except Exception as e:
            print(f"跳过 ({e})")

    print("-" * 60)

def check_models():
    """检查模型文件"""
    print("\n检查模型文件...")
    print("-" * 60)

    models_dir = Path(__file__).parent / "models"

    required_models = [
        ("models/sherpa-onnx/ASR/sherpa-onnx-paraformer-zh-2023-09-14/model.int8.onnx", "Sherpa-ONNX 中文模型"),
        ("models/tiny.pt", "Whisper tiny 模型"),
    ]

    all_exist = True
    for model_path, model_name in required_models:
        full_path = Path(__file__).parent / model_path
        if full_path.exists():
            size_mb = full_path.stat().st_size / (1024 * 1024)
            print(f"[OK] {model_name}: {size_mb:.1f} MB")
        else:
            print(f"[FAIL] {model_name}: 未找到 ({model_path})")
            all_exist = False

    print("-" * 60)
    return all_exist

def create_env_file():
    """创建环境变量文件"""
    env_file = Path(__file__).parent / ".env"
    env_example = Path(__file__).parent / ".env.example"

    if env_file.exists():
        print(f"\n.env 文件已存在，跳过创建")
        return

    if env_example.exists():
        print(f"\n创建 .env 文件...")
        import shutil
        shutil.copy(env_example, env_file)
        print("[OK] 请编辑 .env 文件填入你的配置")
    else:
        print(f"\n警告: 未找到 .env.example 文件")

def update_openclaw_identity():
    """更新 OpenClaw 的 IDENTITY.md 文件，添加文件发送工具说明"""
    print("\n更新 OpenClaw 配置...")
    print("-" * 60)

    # 查找 IDENTITY.md 文件
    home_dir = Path.home()
    possible_paths = [
        home_dir / ".openclaw" / "IDENTITY.md",
        home_dir / "OpenClaw" / "IDENTITY.md",
        Path("D:/OpenClaw/IDENTITY.md"),
        Path("C:/OpenClaw/IDENTITY.md"),
    ]

    identity_file = None
    for path in possible_paths:
        if path.exists():
            identity_file = path
            break

    if not identity_file:
        print("[WARN] 未找到 IDENTITY.md 文件，跳过配置更新")
        print("  请手动将以下内容添加到 IDENTITY.md:")
        print("  - 文件发送工具使用说明")
        return False

    try:
        # 读取现有内容
        content = identity_file.read_text(encoding='utf-8')

        # 检查是否已包含文件发送说明
        if "openclaw_send_file.py" in content:
            print(f"[OK] IDENTITY.md 已包含文件发送配置")
            return True

        # 添加文件发送工具说明
        file_send_section = """
---

## 工具使用说明

### 发送文件到企微

当你收到媒体文件（图片、视频、音频、文件）并需要发送给用户时，请使用以下脚本：

```bash
python "D:\\\\OpenClaw\\\\skills\\\\sillymd\\\\openclaw_send_file.py" "<文件路径>" "<显示名称>"
```

**示例：**
```bash
python "D:\\\\OpenClaw\\\\skills\\\\sillymd\\\\openclaw_send_file.py" "D:\\\\OpenClaw\\\\skills\\\\sillymd\\\\file\\\\image.jpg" "图片"
```

**注意：**
- 文件路径必须是完整绝对路径
- 显示名称是用户在企微中看到的文件名
- 支持类型：图片(.jpg/.png/.gif)、视频(.mp4)、音频(.wav/.mp3)、文件(.pdf/.doc等)

当用户说"发送文件"、"发给我"、"传给我"等意图时，请主动使用此脚本发送文件。
"""

        # 追加到文件末尾
        with open(identity_file, 'a', encoding='utf-8') as f:
            f.write(file_send_section)

        print(f"[OK] 已更新 {identity_file}")
        print("  添加了文件发送工具使用说明")
        return True

    except Exception as e:
        print(f"[FAIL] 更新 IDENTITY.md 失败: {e}")
        return False

def test_imports():
    """测试关键导入"""
    print("\n测试关键模块导入...")
    print("-" * 60)

    modules = [
        ("numpy", "NumPy"),
        ("onnxruntime", "ONNX Runtime"),
        ("websockets", "WebSockets"),
    ]

    all_ok = True
    for module_name, display_name in modules:
        try:
            __import__(module_name)
            print(f"[OK] {display_name}")
        except ImportError:
            print(f"[FAIL] {display_name}")
            all_ok = False

    # 测试 Sherpa-ONNX
    try:
        from asr_sherpa_onnx import SherpaOnnxASR
        print("[OK] Sherpa-ONNX ASR")
    except Exception as e:
        print(f"[FAIL] Sherpa-ONNX ASR: {e}")
        all_ok = False

    print("-" * 60)
    return all_ok

def main():
    print_banner()

    # 检查 Python 版本
    if not check_python_version():
        sys.exit(1)

    print("\n开始安装...")
    print("=" * 60)

    # 安装依赖
    wheels_ok = install_from_wheels()
    install_other_dependencies()

    # 检查模型
    models_ok = check_models()

    # 创建 .env 文件
    create_env_file()

    # 更新 OpenClaw IDENTITY.md
    update_openclaw_identity()

    # 测试导入
    imports_ok = test_imports()

    # 总结
    print("\n" + "=" * 60)
    print("安装完成!")
    print("=" * 60)

    if wheels_ok and models_ok and imports_ok:
        print("\n[OK] 所有组件安装成功!")
        print("\n下一步:")
        print("1. 编辑 .env 文件填入你的配置")
        print("2. 运行: python wecom_to_openclaw_bridge.py")
    else:
        print("\n[WARN] 部分组件可能未正确安装，请检查上方日志")
        if not models_ok:
            print("\n模型文件缺失，请确认 models/ 目录完整")

    print()

if __name__ == "__main__":
    main()
