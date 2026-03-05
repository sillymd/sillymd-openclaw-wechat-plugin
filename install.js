#!/usr/bin/env node
/**
 * Post-install script for sillymd-wechat
 * Runs Python install.py with --skip for non-interactive install
 */

const { execSync } = require('child_process');
const path = require('path');

console.log('[INFO] Running SillyMD WeChat Plugin installer...');

try {
  const installScript = path.join(__dirname, 'install.py');
  // Use --skip for non-interactive install (auto-download models/wheels, use defaults)
  execSync(`python "${installScript}" --skip`, {
    stdio: 'inherit',
    cwd: __dirname
  });
  console.log('[OK] Installation complete!');
} catch (error) {
  console.error('[FAIL] Installation failed:', error.message);
  console.log('[INFO] Please run manually: python install.py');
  process.exit(1);
}
