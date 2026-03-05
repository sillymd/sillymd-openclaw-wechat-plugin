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
    # Use default option 1 in non-interactive mode
    if SKIP_INTERACTIVE:
        print("\n[SKIP] Using default: Auto install to OpenClaw skills directory")
        return '1'

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
    # In non-interactive mode, return None to skip custom location
    if SKIP_INTERACTIVE:
        print("\n[SKIP] Using default: Auto find OpenClaw")
        return None

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

def setup_health_check(openclaw_dir: Path, plugin_dir: Path):
    """设置健康检测，定时检查桥接器是否运行"""
    print("\n配置健康检测...")
    print("-" * 60)

    # 确保 logs 目录存在
    logs_dir = plugin_dir / "logs"
    logs_dir.mkdir(exist_ok=True)

    # 检查 .bridge_pid 文件是否存在来判断进程是否运行
    bridge_script = plugin_dir / "wecom_to_openclaw_bridge.py"

    if not bridge_script.exists():
        print(f"[WARN] 桥接器脚本不存在: {bridge_script}")
        return False

    # 获取 Python 解释器路径
    python_path = sys.executable

    if sys.platform == 'win32':
        # Windows: 使用计划任务
        task_name = "SillyMDWeChatBridge"
        # 检查任务是否已存在
        check_result = subprocess.run(
            ['schtasks', '/Query', '/TN', task_name],
            capture_output=True,
            text=True
        )

        if check_result.returncode == 0:
            print(f"[INFO] 健康检测任务已存在: {task_name}")
            response = input("是否重新创建? (y/n): ").strip().lower()
            if response != 'y':
                return True

        # 创建 PowerShell 脚本用于健康检测
        health_check_script = plugin_dir / "health_check.ps1"
        script_content = f'''# SillyMD WeChat Bridge Health Check
$pidFile = "{plugin_dir / ".bridge_pid"}"
$bridgeScript = "{bridge_script}"
$pythonExe = "{python_path}"
$logFile = "{plugin_dir / "logs" / "health_check.log"}"

# 检查 PID 文件是否存在
if (Test-Path $pidFile) {{
    $pid = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($pid) {{
        # 检查进程是否仍在运行
        $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($process) {{
            exit 0  # 进程正在运行
        }}
    }}
}}

# 进程未运行，记录日志并启动
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"$timestamp - Bridge not running, starting..." | Out-File -FilePath $logFile -Append

# 启动桥接器
Start-Process -FilePath $pythonExe -ArgumentList $bridgeScript -WindowStyle Hidden
'''

        try:
            with open(health_check_script, 'w', encoding='utf-8') as f:
                f.write(script_content)
            print(f"[OK] 健康检测脚本: {health_check_script}")
        except Exception as e:
            print(f"[FAIL] 创建健康检测脚本失败: {e}")
            return False

        # 创建计划任务
        # 每5分钟检查一次
        cmd = [
            'schtasks', '/Create',
            '/TN', task_name,
            '/TR', f'powershell -ExecutionPolicy Bypass -File "{health_check_script}"',
            '/SC', 'MINUTE',
            '/MO', '5',
            '/F'  # 强制覆盖
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"[OK] 已创建计划任务: {task_name}")
            print(f"  检查间隔: 5分钟")
            return True
        except Exception as e:
            print(f"[FAIL] 创建计划任务失败: {e}")
            return False

    else:
        # Linux/Mac: 使用 cron
        # 创建健康检查脚本
        health_check_script = plugin_dir / "health_check.sh"
        script_content = f'''#!/bin/bash
# SillyMD WeChat Bridge Health Check

PID_FILE="{plugin_dir / ".bridge_pid"}"
BRIDGE_SCRIPT="{bridge_script}"
PYTHON="{python_path}"
LOG_FILE="{plugin_dir / "logs" / "health_check.log"}"

# 检查 PID 文件是否存在
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    # 检查进程是否仍在运行
    if kill -0 "$PID" 2>/dev/null; then
        exit 0  # 进程正在运行
    fi
fi

# 进程未运行，记录日志并启动
echo "$(date '+%Y-%m-%d %H:%M:%S') - Bridge not running, starting..." >> "$LOG_FILE"

# 启动桥接器
nohup "$PYTHON" "$BRIDGE_SCRIPT" > /dev/null 2>&1 &
'''

        try:
            with open(health_check_script, 'w', encoding='utf-8') as f:
                f.write(script_content)
            os.chmod(health_check_script, 0o755)
            print(f"[OK] 健康检测脚本: {health_check_script}")
        except Exception as e:
            print(f"[FAIL] 创建健康检测脚本失败: {e}")
            return False

        # 添加 cron 任务
        cron_entry = f'*/5 * * * * {health_check_script}'

        try:
            # 读取现有 crontab
            result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
            existing_cron = result.stdout if result.returncode == 0 else ""

            # 检查是否已存在
            if 'health_check.sh' in existing_cron:
                print(f"[INFO] 健康检测 cron 已存在")
                return True

            # 添加新任务
            new_cron = existing_cron.strip() + '\n' + cron_entry + '\n'
            proc = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            proc.communicate(input=new_cron.encode())

            print(f"[OK] 已添加 cron 健康检测")
            print(f"  检查间隔: 5分钟")
            return True
        except Exception as e:
            print(f"[FAIL] 添加 cron 失败: {e}")
            return False

def add_npm_to_path():
    """Add npm global path to system PATH"""
    if sys.platform != 'win32':
        print("[SKIP] 仅 Windows 支持自动配置 PATH")
        return False

    print("\n配置 npm 全局命令...")
    print("-" * 60)

    # Get npm global path
    try:
        result = subprocess.run(
            ['npm', 'config', 'get', 'prefix'],
            capture_output=True,
            text=True,
            timeout=10
        )
        npm_prefix = result.stdout.strip()
        npm_path = Path(npm_prefix) / "npm"

        if not npm_path.exists():
            print(f"[WARN] npm 全局路径不存在: {npm_path}")
            return False

        print(f"[INFO] npm 全局路径: {npm_path}")

        # Check current PATH
        current_path = os.environ.get('PATH', '')
        if str(npm_path) in current_path:
            print("[OK] npm 路径已在 PATH 中")
            return True

        # Add to PATH (using setx for permanent effect)
        new_path = f"{current_path};{npm_path}"

        # Use setx to update system PATH
        try:
            subprocess.run(
                ['setx', 'PATH', new_path],
                check=True,
                capture_output=True
            )
            print("[OK] 已添加 npm 到系统 PATH")
            print("  请重启终端使更改生效")
            return True
        except Exception as e:
            print(f"[WARN] 自动配置 PATH 失败: {e}")
            print(f"  请手动添加以下路径到系统 PATH:")
            print(f"  {npm_path}")
            return False

    except Exception as e:
        print(f"[WARN] 获取 npm 路径失败: {e}")
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

def run_check_mode():
    """Run in check mode - interactive configuration without full installation"""
    print("\n" + "=" * 60)
    print("SillyMD WeChat Plugin - Configuration Check")
    print("=" * 60 + "\n")

    plugin_dir = Path(__file__).parent

    # Check config
    config_path = plugin_dir / "config.json"
    example_path = plugin_dir / "config.json.example"

    if not config_path.exists() and example_path.exists():
        shutil.copy(example_path, config_path)
        print(f"[INFO] Created config.json from example")

    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            api_key = config.get('api_key', '')
            owner_id = config.get('wechat', {}).get('owner_id', '')

            print(f"Current configuration:")
            print(f"  API Key: {'*' * 20 if api_key else '(not set)'}")
            print(f"  Owner ID: {owner_id or '(not set)'}")
            print()

            # Ask for new values
            print("Enter new values (press Enter to keep current):")

            new_api_key = input(f"API Key [{'*' * 20 if api_key else ''}]: ").strip()
            if new_api_key:
                config['api_key'] = new_api_key

            new_owner_id = input(f"Owner ID [{owner_id}]: ").strip()
            if new_owner_id:
                if 'wechat' not in config:
                    config['wechat'] = {}
                config['wechat']['owner_id'] = new_owner_id

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            print("\n[OK] Configuration saved!")

        except Exception as e:
            print(f"[ERROR] Failed to update config: {e}")
    else:
        print("[ERROR] config.json not found")

    # Test connection
    print("\nTesting connection...")
    try:
        from server_connector import SillyMDConnector
        # Just test basic import
        print("[OK] Dependencies OK")
    except ImportError as e:
        print(f"[WARN] Some dependencies may be missing: {e}")
        print("       Run 'sillymd-wechat install' to install dependencies")

    print("\nConfiguration check complete!")

# Global flag for non-interactive mode
SKIP_INTERACTIVE = '--skip' in sys.argv

def main():
    # Check for --check flag
    if len(sys.argv) > 1 and sys.argv[1] == '--check':
        run_check_mode()
        sys.exit(0)

    # Check for --skip flag and remove it from args
    global SKIP_INTERACTIVE
    if '--skip' in sys.argv:
        SKIP_INTERACTIVE = True
        sys.argv.remove('--skip')
        print("[INFO] Running in non-interactive mode (--skip)")

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

    # Setup health check
    if installed_path and openclaw_dir:
        # 读取配置检查是否启用健康检测
        config_file = installed_path / "config.json"
        health_check_enabled = True  # 默认开启

        if config_file.exists():
            try:
                import json
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    bridge_config = config.get('bridge', {})
                    health_check_enabled = bridge_config.get('health_check_enabled', True)
            except Exception:
                pass

        if not health_check_enabled:
            print("\n[INFO] 健康检测已在配置中禁用，跳过配置")
        else:
            if SKIP_INTERACTIVE:
                print("\n[SKIP] Using default: Enable health check")
                setup_health_check(openclaw_dir, installed_path)
            else:
                print("\n是否配置健康检测? (自动检测桥接器是否运行，未运行则自动启动)")
                print("建议: 开启以确保桥接器持续运行")
                response = input("配置健康检测 (y/n)? 默认 y: ").strip().lower()
                if response == '' or response == 'y':
                    setup_health_check(openclaw_dir, installed_path)

    # Configure npm PATH
    if sys.platform == 'win32':
        if SKIP_INTERACTIVE:
            print("\n[SKIP] Using default: Add npm to PATH")
            add_npm_to_path()
        else:
            print("\n是否将 npm 全局路径添加到系统 PATH?")
            print("这样可以全局使用 sillymd-wechat 命令")
            response = input("添加 PATH (y/n)? 默认 y: ").strip().lower()
            if response == '' or response == 'y':
                add_npm_to_path()

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
