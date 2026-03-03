# v1.0.3 - Wheel 文件名修复

## Bug Fix

修复 wheel 文件名格式错误导致安装失败的问题。

## 问题原因

Python wheel 文件名缺少 ABI 标签，格式为：
- 错误：`torch-2.0.1-cp38-win_amd64.whl`
- 正确：`torch-2.0.1-cp38-cp38-win_amd64.whl`

## 修复的文件

| 文件名 | 状态 |
|--------|------|
| torch-2.0.1-cp38-win_amd64.whl | → torch-2.0.1-cp38-cp38-win_amd64.whl |
| torch-2.0.1+cpu-cp38-win_amd64.whl | → torch-2.0.1+cpu-cp38-cp38-win_amd64.whl |
| torchaudio-2.0.2-cp38-win_amd64.whl | → torchaudio-2.0.2-cp38-cp38-win_amd64.whl |
| torchaudio-2.0.2+cpu-cp38-win_amd64.whl | → torchaudio-2.0.2+cpu-cp38-cp38-win_amd64.whl |

## 下载

- [wheels-v1.0.3-fix.zip](https://github.com/sillymd/sillymd-openclaw-wechat-plugin/releases/download/v1.0.3/wheels-v1.0.3-fix.zip) (356 MB)

## 使用方法

1. 解压 `wheels-v1.0.3-fix.zip` 覆盖原 `wheels/` 目录
2. 重新运行安装：`python install.py`

或直接手动重命名 wheel 文件（在 wheels 目录下）：

```bash
# Windows
ren torch-2.0.1-cp38-win_amd64.whl torch-2.0.1-cp38-cp38-win_amd64.whl
ren torch-2.0.1+cpu-cp38-win_amd64.whl torch-2.0.1+cpu-cp38-cp38-win_amd64.whl
ren torchaudio-2.0.2-cp38-win_amd64.whl torchaudio-2.0.2-cp38-cp38-win_amd64.whl
ren torchaudio-2.0.2+cpu-cp38-win_amd64.whl torchaudio-2.0.2+cpu-cp38-cp38-win_amd64.whl
```
