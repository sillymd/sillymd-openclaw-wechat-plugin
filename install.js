#!/usr/bin/env node
/**
 * Post-install script for sillymd-wechat
 * Runs Python install.py with --skip for non-interactive install
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

console.log('[INFO] Running SillyMD WeChat Plugin installer...');

// Clean up any locked files before installation
const filesToCheck = ['config.json', '.env'];
filesToCheck.forEach(file => {
  const filePath = path.join(__dirname, file);
  if (fs.existsSync(filePath)) {
    try {
      // Try to make file writable
      fs.chmodSync(filePath, 0o644);
    } catch (e) {
      // Ignore - file might be locked by another process
    }
  }
});

try {
  const installScript = path.join(__dirname, 'install.py');
  // Use --skip for non-interactive install (auto-download models/wheels, use defaults)
  execSync(`python "${installScript}" --skip`, {
    stdio: 'inherit',
    cwd: __dirname
  });
  console.log('[OK] Installation complete!');
} catch (error) {
  // If installation fails due to locked files, try again after a short delay
  if (error.message && error.message.includes('EBUSY')) {
    console.log('[INFO] Detected file lock, retrying...');
    setTimeout(() => {
      try {
        execSync(`python "${installScript}" --skip`, {
          stdio: 'inherit',
          cwd: __dirname
        });
        console.log('[OK] Installation complete on retry!');
      } catch (retryError) {
        console.error('[FAIL] Installation failed:', retryError.message);
        console.log('[INFO] Please run manually: python install.py');
        process.exit(1);
      }
    }, 2000);
  } else {
    console.error('[FAIL] Installation failed:', error.message);
    console.log('[INFO] Please run manually: python install.py');
    process.exit(1);
  }
}
