#!/usr/bin/env node
/**
 * SillyMD WeChat Plugin CLI
 * npm install -g sillymd-wechat
 * sillymd-wechat start
 */

const { execSync, spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const PLUGIN_DIR = path.dirname(__dirname);
const PYTHON_SCRIPT = path.join(PLUGIN_DIR, 'wecom_to_openclaw_bridge.py');

function checkPython() {
    try {
        const version = execSync('python --version', { encoding: 'utf8' });
        console.log('[OK] Python found:', version.trim());
        return true;
    } catch (e) {
        console.error('[FAIL] Python not found. Please install Python 3.8+');
        return false;
    }
}

function checkConfig() {
    const configPath = path.join(PLUGIN_DIR, 'config.json');
    if (!fs.existsSync(configPath)) {
        const examplePath = path.join(PLUGIN_DIR, 'config.json.example');
        if (fs.existsSync(examplePath)) {
            fs.copyFileSync(examplePath, configPath);
            console.log('[INFO] Created config.json from example');
        }
        return false;
    }

    // Check if config is valid
    try {
        const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
        if (!config.api_key || config.api_key === 'YOUR_API_KEY_HERE') {
            console.log('[WARN] API key not configured');
            return false;
        }
        if (!config.wechat || !config.wechat.owner_id) {
            console.log('[WARN] owner_id not configured');
            return false;
        }
        return true;
    } catch (e) {
        console.log('[WARN] Invalid config.json');
        return false;
    }
}

function runInstallCheck() {
    console.log('[INFO] Running configuration check...\n');
    try {
        execSync('python install.py --check', {
            cwd: PLUGIN_DIR,
            stdio: 'inherit'
        });
        return true;
    } catch (e) {
        console.error('[FAIL] Configuration check failed');
        return false;
    }
}

function installDeps() {
    console.log('[INFO] Installing Python dependencies...');
    try {
        execSync('python install.py --skip', {
            cwd: PLUGIN_DIR,
            stdio: 'inherit'
        });
        return true;
    } catch (e) {
        console.error('[FAIL] Failed to install dependencies');
        return false;
    }
}

function startPlugin() {
    console.log('[INFO] Starting SillyMD WeChat Plugin...');
    console.log('[INFO] Press Ctrl+C to stop\n');

    const child = spawn('python', [PYTHON_SCRIPT], {
        cwd: PLUGIN_DIR,
        stdio: 'inherit'
    });

    child.on('exit', (code) => {
        console.log(`\n[INFO] Plugin exited with code ${code}`);
        process.exit(code);
    });

    process.on('SIGINT', () => {
        console.log('\n[INFO] Stopping plugin...');
        child.kill('SIGINT');
    });
}

function showHelp() {
    console.log(`
SillyMD WeChat Plugin CLI

Usage:
  sillymd-wechat [command]

Commands:
  start       Start the plugin
  install     Install Python dependencies
  check       Interactive configuration check (configure API key, etc.)
  config      Show configuration guide
  help        Show this help message

Examples:
  sillymd-wechat start
  sillymd-wechat check
  sillymd-wechat install

Configuration:
  Edit config.json with your API key from https://websocket.sillymd.com
  Or run: sillymd-wechat check
`);
}

function main() {
    const command = process.argv[2] || 'start';

    switch (command) {
        case 'start':
            if (!checkPython()) process.exit(1);
            if (!checkConfig()) {
                console.log('\nPlease configure the plugin first:');
                console.log('1. Edit config.json');
                console.log('2. Get API key from https://websocket.sillymd.com');
                process.exit(1);
            }
            startPlugin();
            break;

        case 'install':
            if (!checkPython()) process.exit(1);
            installDeps();
            break;

        case 'check':
            if (!checkPython()) process.exit(1);
            runInstallCheck();
            break;

        case 'config':
            console.log(`
Configuration Guide:

1. Get API Key:
   Visit https://websocket.sillymd.com to get your API key

2. Edit config.json:
   {
     "api_key": "YOUR_API_KEY",
     "wechat": {
       "owner_id": "YOUR_WECHAT_ID"
     }
   }

3. Or run interactive check:
   sillymd-wechat check

4. Start the plugin:
   sillymd-wechat start
`);
            break;

        case 'help':
        case '-h':
        case '--help':
            showHelp();
            break;

        default:
            console.error(`Unknown command: ${command}`);
            showHelp();
            process.exit(1);
    }
}

main();
