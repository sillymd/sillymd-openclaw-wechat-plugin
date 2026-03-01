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
            console.log('[WARN] Please edit config.json with your API key and owner_id');
        }
        return false;
    }
    return true;
}

function installDeps() {
    console.log('[INFO] Installing Python dependencies...');
    try {
        execSync('python install.py', {
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
  config      Show configuration guide
  help        Show this help message

Examples:
  sillymd-wechat start
  sillymd-wechat install

Configuration:
  Edit config.json with your API key from https://websocket.sillymd.com
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

3. Start the plugin:
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
