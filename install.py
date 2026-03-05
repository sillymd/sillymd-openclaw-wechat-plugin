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
import tarfile
import urllib.request
from pathlib import Path

SILLYHUB_URL = "https://resource.sillymd.com/sillyhub"

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
    models_dir = base_dir / "models"
    wheels_dir = base_dir / "wheels"

    # Check if already exists
    if models_dir.exists() and wheels_dir.exists():
        models_ok = (models_dir / "sherpa-onnx").exists() or (models_dir / "tiny.pt").exists()
        wheels_ok = list(wheels_dir.glob("*.whl"))
        if models_ok and wheels_ok:
            print("[SKIP] models/ and wheels/ already exist")
            return True

    print("\nDownloading models and wheels from SillyHub...")
    print("-" * 60)

    # Download models
    models_archive = base_dir / "models.tar.gz"
    print("Downloading models...")
    try:
        urllib.request.urlretrieve(f"{SILLYHUB_URL}/models.tar.gz", models_archive)
        print("Extracting models...")
        with tarfile.open(models_archive, "r:gz") as tar:
            tar.extractall(base_dir)
        os.remove(models_archive)
        print("[OK] models/")
    except Exception as e:
        print(f"[FAIL] models: {e}")

    # Download wheels
    wheels_archive = base_dir / "wheels.tar.gz"
    print("Downloading wheels...")
    try:
        urllib.request.urlretrieve(f"{SILLYHUB_URL}/wheels.tar.gz", wheels_archive)
        print("Extracting wheels...")
        with tarfile.open(wheels_archive, "r:gz") as tar:
            tar.extractall(base_dir)
        os.remove(wheels_archive)
        print("[OK] wheels/")
    except Exception as e:
        print(f"[FAIL] wheels: {e}")

    print("-" * 60)
    return True

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
        Path("D:/OpenClaw/IDENTITY.md"),
        Path("C:/OpenClaw/IDENTITY.md"),
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
python "D:\\OpenClaw\\skills\\sillymd\\openclaw_send_file.py" "<file_path>" "<display_name>"
```

**Example:**
```bash
python "D:\\OpenClaw\\skills\\sillymd\\openclaw_send_file.py" "D:\\OpenClaw\\skills\\sillymd\\file\\image.jpg" "Image"
```

**Note:**
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

    print("\n" + "=" * 60)
    print("Installation Complete!")
    print("=" * 60)

    if wheels_ok and models_ok and imports_ok:
        print("\n[OK] All components installed successfully!")
        print("\nNext steps:")
        print("1. Edit .env file with your configuration")
        print("2. Edit config.json with your API key and owner_id")
        print("3. Run: python wecom_to_openclaw_bridge.py")
    else:
        print("\n[WARN] Some components may not be installed correctly, please check logs above")
        if not models_ok:
            print("\nModel files missing, please ensure models/ directory is complete")

    print()

if __name__ == "__main__":
    main()
