#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SillyMD WeCom Channel Plugin Installer
Supports offline installation of all dependencies
"""

import os
import sys
import subprocess
import glob
import urllib.request
import shutil
import json
from pathlib import Path

SILLYHUB_URL = "https://resource.sillymd.com/sillyhub"

# Directories to download from SillyHub
DOWNLOAD_DIRS = ["models", "wheels"]

# Fix Windows terminal encoding
if sys.platform == 'win32':
    import ctypes
    try:
        ctypes.windll.kernel32.SetConsoleCP(65001)
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except:
        pass
    os.environ['PYTHONIOENCODING'] = 'utf-8'

def print_banner():
    print("=" * 60)
    print("SillyMD WeCom Channel Plugin - Installer")
    print("=" * 60)
    print()

def find_openclaw_installation():
    """Find OpenClaw installation directory"""
    possible_paths = []

    # Common OpenClaw installation locations
    if sys.platform == 'win32':
        # User's home directory
        home = Path.home()
        possible_paths.extend([
            home / "OpenClaw",
            home / ".openclaw",
            Path("D:/OpenClaw"),
            Path("C:/OpenClaw"),
        ])
        # Check environment variable
        if "OPENCLAW_DIR" in os.environ:
            possible_paths.append(Path(os.environ["OPENCLAW_DIR"]))
    else:
        home = Path.home()
        possible_paths.extend([
            home / "OpenClaw",
            home / ".openclaw",
            Path("/opt/OpenClaw"),
            Path("/usr/local/OpenClaw"),
        ])

    # Check which paths exist
    for path in possible_paths:
        if path.exists():
            return path

    return None

def find_openclaw_skills_dir(openclaw_dir):
    """Find OpenClaw skills directory"""
    skills_dir = openclaw_dir / "skills"
    if skills_dir.exists():
        return skills_dir
    return None

def ask_install_location():
    """Ask user for installation location"""
    print("\n选择安装方式:")
    print("1. 自动安装到 OpenClaw skills 目录")
    print("2. 自定义安装位置")

    while True:
        choice = input("\n请输入选项 (1/2): ").strip()
        if choice in ['1', '2']:
            return choice
        print("请输入 1 或 2")

def ask_custom_location():
    """Ask user for custom installation location"""
    print("\n请输入自定义安装路径 (直接回车取消):")
    path = input("路径: ").strip()
    if path:
        return Path(path)
    return None

def install_to_openclaw(skills_dir):
    """Install plugin to OpenClaw skills directory"""
    plugin_name = "sillymd"
    target_dir = skills_dir / plugin_name
    source_dir = Path(__file__).parent

    print(f"\n安装到: {target_dir}")
    print("-" * 60)

    # Create symlink or copy
    if target_dir.exists():
        print(f"[INFO] 目录已存在: {target_dir}")
        response = input("是否覆盖? (y/n): ").strip().lower()
        if response == 'y':
            if target_dir.is_symlink():
                target_dir.unlink()
            else:
                shutil.rmtree(target_dir)
        else:
            print("[SKIP] 跳过安装")
            return target_dir

    # Create symlink (works better with git)
    try:
        if sys.platform == 'win32':
            # On Windows, use junction for directories
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(target_dir), str(source_dir)],
                         shell=True, check=True, capture_output=True)
            print(f"[OK] 创建目录联接: {target_dir}")
        else:
            target_dir.symlink_to(source_dir)
            print(f"[OK] 创建符号链接: {target_dir}")
    except Exception:
        # Fallback to copy
        print(f"[INFO] 符号链接失败，使用复制方式")
        shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
        print(f"[OK] 复制完成: {target_dir}")

    return target_dir

def register_to_openclaw_channel(openclaw_dir, plugin_dir):
    """Register plugin as OpenClaw channel"""
    print("\n注册到 OpenClaw Channel...")
    print("-" * 60)

    # Check if OpenClaw config exists
    config_file = openclaw_dir / ".openclaw" / "openclaw.json"
    if not config_file.exists():
        print(f"[WARN] OpenClaw 配置文件不存在: {config_file}")
        return False

    try:
        # Read existing config
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # Check if sillymd channel already exists
        channels = config.get('channels', {})

        # Add sillymd channel config
        channels['sillymd'] = {
            "enabled": True,
            "type": "sillymd-wechat",
            "config": {
                "skill_path": str(plugin_dir)
            }
        }

        config['channels'] = channels

        # Backup original config
        backup_file = config_file.with_suffix('.json.bak')
        shutil.copy(config_file, backup_file)
        print(f"[OK] 备份配置文件: {backup_file}")

        # Write updated config
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        print("[OK] 已添加 SillyMD Channel 配置")
        print(f"  配置文件: {config_file}")
        return True

    except Exception as e:
        print(f"[FAIL] 注册 Channel 失败: {e}")
        return False

def check_python_version():
    """Check Python version"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"[FAIL] Python 3.8+ required, current: {version.major}.{version.minor}")
        return False
    print(f"[OK] Python version: {version.major}.{version.minor}.{version.micro}")
    return True

def download_from_sillyhub():
    """Download models and wheels from SillyHub"""
    base_dir = Path(__file__).parent

    # Collect all files to download from models/ and wheels/ directories
    files_to_download = []
    for dir_name in DOWNLOAD_DIRS:
        dir_path = base_dir / dir_name
        if dir_path.exists():
            for file_path in dir_path.rglob("*"):
                if file_path.is_file():
                    rel_path = str(file_path.relative_to(base_dir))
                    files_to_download.append(rel_path)

    if not files_to_download:
        print("[SKIP] No files to download")
        return True

    # Check if all files exist
    all_exist = all((base_dir / f).exists() for f in files_to_download)
    if all_exist:
        print("[SKIP] All files already exist")
        return True

    print("\nDownloading from SillyHub...")
    print("-" * 60)

    success_count = 0
    fail_count = 0

    for rel_path in files_to_download:
        target_path = base_dir / rel_path
        if target_path.exists():
            continue

        url = f"{SILLYHUB_URL}/{rel_path}"
        target_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"Downloading {rel_path}...", end=" ")
        try:
            urllib.request.urlretrieve(url, target_path)
            print("[OK]")
            success_count += 1
        except Exception as e:
            print(f"[FAIL] {e}")
            fail_count += 1

    print("-" * 60)
    print(f"Download complete: {success_count} success, {fail_count} failed")
    return fail_count == 0

def install_from_wheels():
    """Install dependencies from wheels directory"""
    wheels_dir = Path(__file__).parent / "wheels"

    if not wheels_dir.exists():
        print("[FAIL] wheels directory not found, skipping offline install")
        return False

    wheels = list(wheels_dir.glob("*.whl"))
    if not wheels:
        print("[FAIL] wheels directory is empty")
        return False

    print(f"\nInstalling from wheels ({len(wheels)} packages)...")
    print("-" * 60)

    success_count = 0
    fail_count = 0

    for wheel in sorted(wheels):
        wheel_name = wheel.name
        print(f"Installing: {wheel_name[:50]}...", end=" ")

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
                print(f"  Error: {result.stderr[:100]}")
                fail_count += 1
        except Exception as e:
            print(f"[FAIL] ({e})")
            fail_count += 1

    print("-" * 60)
    print(f"Installation complete: {success_count} success, {fail_count} failed")
    return fail_count == 0

def install_other_dependencies():
    """Install other dependencies via pip"""
    print("\nInstalling other dependencies...")
    print("-" * 60)

    basic_deps = [
        "requests",
        "websockets",
        "python-dotenv",
        "cryptography",
    ]

    for dep in basic_deps:
        print(f"Installing: {dep}...", end=" ")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", dep, "-q"],
                capture_output=True,
                timeout=60
            )
            print("[OK]" if result.returncode == 0 else "Skip")
        except Exception as e:
            print(f"Skip ({e})")

    print("-" * 60)

def check_models():
    """Check model files"""
    print("\nChecking model files...")
    print("-" * 60)

    models_dir = Path(__file__).parent / "models"

    required_models = [
        ("models/sherpa-onnx/ASR/sherpa-onnx-paraformer-zh-2023-09-14/model.int8.onnx", "Sherpa-ONNX Chinese Model"),
        ("models/tiny.pt", "Whisper tiny Model"),
    ]

    all_exist = True
    for model_path, model_name in required_models:
        full_path = Path(__file__).parent / model_path
        if full_path.exists():
            size_mb = full_path.stat().st_size / (1024 * 1024)
            print(f"[OK] {model_name}: {size_mb:.1f} MB")
        else:
            print(f"[FAIL] {model_name}: not found ({model_path})")
            all_exist = False

    print("-" * 60)
    return all_exist

def create_env_file():
    """Create environment variable file"""
    env_file = Path(__file__).parent / ".env"
    env_example = Path(__file__).parent / ".env.example"

    if env_file.exists():
        print(f"\n.env file already exists, skipping creation")
        return

    if env_example.exists():
        print(f"\nCreating .env file...")
        import shutil
        shutil.copy(env_example, env_file)
        print("[OK] Please edit .env file with your configuration")
    else:
        print(f"\n[WARN] .env.example file not found")

def update_openclaw_identity():
    """Update OpenClaw IDENTITY.md file with file sending tool instructions"""
    print("\nUpdating OpenClaw configuration...")
    print("-" * 60)

    home_dir = Path.home()
    possible_paths = [
        home_dir / ".openclaw" / "IDENTITY.md",
        home_dir / "OpenClaw" / "IDENTITY.md",
    ]

    identity_file = None
    for path in possible_paths:
        if path.exists():
            identity_file = path
            break

    if not identity_file:
        print("[WARN] IDENTITY.md not found, skipping configuration update")
        print("  Please manually add file sending tool instructions to IDENTITY.md")
        return False

    try:
        content = identity_file.read_text(encoding='utf-8')

        if "openclaw_send_file.py" in content:
            print(f"[OK] IDENTITY.md already contains file sending configuration")
            return True

        file_send_section = """

---

## Tool Usage Guide

### Sending Files to WeCom

When you receive media files (images, videos, audio, documents) and need to send them to users, use the following script:

```bash
python "<path_to_openclaw_send_file.py>" "<file_path>" "<display_name>"
```

**Example:**
```bash
python "<path_to_openclaw_send_file.py>" "D:\\path\\to\\file.jpg" "Image"
```

**Note:**
- Replace `<path_to_openclaw_send_file.py>` with the actual path to openclaw_send_file.py in your installation directory
- File path must be a complete absolute path
- Display name is what users see in WeCom
- Supported types: images (.jpg/.png/.gif), videos (.mp4), audio (.wav/.mp3), documents (.pdf/.doc etc.)

When users say "send file", "send to me", "transfer to me" or similar intent, actively use this script to send files.
"""

        with open(identity_file, 'a', encoding='utf-8') as f:
            f.write(file_send_section)

        print(f"[OK] Updated {identity_file}")
        print("  Added file sending tool instructions")
        return True

    except Exception as e:
        print(f"[FAIL] Failed to update IDENTITY.md: {e}")
        return False

def test_imports():
    """Test key module imports"""
    print("\nTesting key module imports...")
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

    if not check_python_version():
        sys.exit(1)

    print("\nStarting installation...")
    print("=" * 60)

    # Download models and wheels from SillyHub if not present
    download_from_sillyhub()

    wheels_ok = install_from_wheels()
    install_other_dependencies()

    models_ok = check_models()

    create_env_file()

    update_openclaw_identity()

    imports_ok = test_imports()

    # Ask for installation location
    print("\n" + "=" * 60)
    install_choice = ask_install_location()

    installed_path = None
    openclaw_dir = None

    if install_choice == '1':
        # Auto find OpenClaw
        openclaw_dir = find_openclaw_installation()
        if openclaw_dir:
            print(f"\n[OK] 找到 OpenClaw: {openclaw_dir}")
            skills_dir = find_openclaw_skills_dir(openclaw_dir)
            if skills_dir:
                installed_path = install_to_openclaw(skills_dir)
            else:
                print(f"[FAIL] 未找到 skills 目录")
        else:
            print("[FAIL] 未找到 OpenClaw 安装目录")
            print("请选择自定义安装位置或确保 OpenClaw 已安装")
    else:
        # Custom location
        custom_path = ask_custom_location()
        if custom_path:
            if not custom_path.exists():
                custom_path.mkdir(parents=True)
            installed_path = custom_path
            print(f"\n[OK] 安装到自定义位置: {installed_path}")

    # Register to OpenClaw if installed to OpenClaw skills
    if installed_path and openclaw_dir:
        register_to_openclaw_channel(openclaw_dir, installed_path)

    print("\n" + "=" * 60)
    print("Installation Complete!")
    print("=" * 60)

    if wheels_ok and models_ok and imports_ok:
        print("\n[OK] All components installed successfully!")
        print("\nNext steps:")
        print("1. Edit .env file with your configuration")
        print("2. Edit config.json with your API key and owner_id")
        print("3. Run: python wecom_to_openclaw_bridge.py")
        if installed_path:
            print(f"\n[INFO] 插件已安装到: {installed_path}")
    else:
        print("\n[WARN] Some components may not be installed correctly, please check logs above")
        if not models_ok:
            print("\nModel files missing, please ensure models/ directory is complete")

    print()

if __name__ == "__main__":
    main()
