"""
Sherpa-ONNX 语音识别模块
使用本地 ONNX 模型进行语音识别
"""

import os
import sys
from pathlib import Path

# 模型路径
MODEL_DIR = Path(__file__).parent / "models" / "sherpa-onnx" / "ASR" / "sherpa-onnx-paraformer-zh-2023-09-14"
MODEL_PATH = MODEL_DIR / "model.int8.onnx"
TOKENS_PATH = MODEL_DIR / "tokens.txt"
CMVN_PATH = MODEL_DIR / "am.mvn"


class SherpaOnnxASR:
    """Sherpa-ONNX 语音识别器"""

    def __init__(self, model_path=None, tokens_path=None, cmvn_path=None):
        """初始化语音识别器"""
        self.model_path = model_path or MODEL_PATH
        self.tokens_path = tokens_path or TOKENS_PATH
        self.cmvn_path = cmvn_path or CMVN_PATH

        self.session = None
        self.tokens = {}
        self.neg_mean = None
        self.inv_std = None

        self._check_model_files()
        self._load_tokens()
        self._load_cmvn()

    def _check_model_files(self):
        """检查模型文件是否存在"""
        if not self.model_path.exists():
            raise FileNotFoundError(f"模型文件不存在: {self.model_path}")
        if not self.tokens_path.exists():
            raise FileNotFoundError(f"词表文件不存在: {self.tokens_path}")
        if not self.cmvn_path.exists():
            raise FileNotFoundError(f"CMVN文件不存在: {self.cmvn_path}")

    def _load_tokens(self):
        """加载词表"""
        self.tokens = {}
        with open(self.tokens_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                token = line.strip().split()[0]
                self.tokens[i] = token

    def _load_audio(self, audio_path: str) -> 'np.ndarray':
        """加载音频文件 (支持 wav, mp3 等格式)"""
        import numpy as np

        # 首先尝试使用 scipy
        try:
            from scipy.io import wavfile
            sample_rate, data = wavfile.read(audio_path)

            # 转换为 float32, -1.0 到 1.0
            if data.dtype == np.int16:
                data = data.astype(np.float32) / 32768.0
            elif data.dtype == np.int32:
                data = data.astype(np.float32) / 2147483648.0
            else:
                data = data.astype(np.float32)

            # 转换为单声道
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)

            # 重采样到 16kHz (如果需要)
            if sample_rate != 16000:
                # 简单的重采样
                from scipy import signal
                num_samples = int(len(data) * 16000 / sample_rate)
                data = signal.resample(data, num_samples)

            return data

        except ImportError:
            # 如果没有 scipy,使用标准库 wave
            import wave
            import struct

            with wave.open(audio_path, 'rb') as wf:
                n_channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()

                raw_data = wf.readframes(n_frames)

                if sample_width == 2:
                    fmt = f'{n_frames * n_channels}h'
                    data = np.array(struct.unpack(fmt, raw_data), dtype=np.float32) / 32768.0
                else:
                    data = np.frombuffer(raw_data, dtype=np.int8).astype(np.float32) / 128.0

                # 转换为单声道
                if n_channels > 1:
                    data = data.reshape(-1, n_channels).mean(axis=1)

                return data

    def _load_cmvn(self):
        """加载 CMVN (倒谱均值方差归一化) 参数"""
        import numpy as np

        self.neg_mean = None
        self.inv_std = None

        with open(self.cmvn_path, 'r') as f:
            for line in f:
                if not line.startswith("<LearnRateCoef>"):
                    continue
                values = line.split()[3:-1]
                values = [float(x) for x in values]

                if self.neg_mean is None:
                    self.neg_mean = np.array(values, dtype=np.float32)
                else:
                    self.inv_std = np.array(values, dtype=np.float32)

    def _init_session(self):
        """初始化 ONNX Runtime 会话"""
        if self.session is not None:
            return

        try:
            import onnxruntime as ort

            session_opts = ort.SessionOptions()
            session_opts.log_severity_level = 3  # error level
            session_opts.intra_op_num_threads = 4

            self.session = ort.InferenceSession(
                str(self.model_path),
                session_opts
            )

        except ImportError:
            raise ImportError("请先安装 onnxruntime: pip install onnxruntime")

    def compute_features(self, audio_path: str) -> 'np.ndarray':
        """计算音频特征 (Fbank)"""
        import numpy as np

        try:
            import kaldi_native_fbank as knf
        except ImportError:
            raise ImportError("请先安装 kaldi-native-fbank: pip install kaldi-native-fbank")

        # 加载音频 (使用 scipy/wave 替代 librosa)
        samples = self._load_audio(audio_path)
        sample_rate = 16000  # _load_audio 已经重采样到 16kHz

        # 计算 Fbank 特征
        opts = knf.FbankOptions()
        opts.frame_opts.dither = 0
        opts.frame_opts.snip_edges = False
        opts.frame_opts.samp_freq = sample_rate
        opts.mel_opts.num_bins = 80

        online_fbank = knf.OnlineFbank(opts)
        online_fbank.accept_waveform(sample_rate, (samples * 32768).tolist())
        online_fbank.input_finished()

        features = np.stack(
            [online_fbank.get_frame(i) for i in range(online_fbank.num_frames_ready)]
        )

        # LFR (Low Frame Rate) 处理
        window_size = 7  # lfr_m
        window_shift = 6  # lfr_n

        T = (features.shape[0] - window_size) // window_shift + 1
        features = np.lib.stride_tricks.as_strided(
            features,
            shape=(T, features.shape[1] * window_size),
            strides=((window_shift * features.shape[1]) * 4, 4),
        )

        # CMVN 归一化
        features = (features + self.neg_mean) * self.inv_std

        return features

    def transcribe(self, audio_path: str) -> str:
        """
        识别音频文件

        Args:
            audio_path: 音频文件路径 (支持 wav, mp3 等格式)

        Returns:
            识别文本
        """
        import numpy as np

        # 初始化会话
        self._init_session()

        # 计算特征
        features = self.compute_features(audio_path)
        features = np.expand_dims(features, axis=0)
        features_length = np.array([features.shape[1]], dtype=np.int32)

        # 运行推理
        inputs = {
            "speech": features,
            "speech_lengths": features_length,
        }
        output_names = ["logits", "token_num", "us_alphas", "us_cif_peak"]

        try:
            outputs = self.session.run(output_names, input_feed=inputs)
        except Exception as e:
            print(f"推理失败: {e}")
            return ""

        # 解码结果
        log_probs = outputs[0][0]
        token_num = outputs[1][0]

        # 取最大概率的token
        y = log_probs.argmax(axis=-1)[:token_num]

        # 转换为文本 (跳过 <blank> (0) 和 <sos/eos> (2))
        text = "".join([self.tokens[i] for i in y if i not in (0, 2)])

        return text


def transcribe_voice_sherpa(audio_path: str) -> str:
    """
    使用 Sherpa-ONNX 识别语音的便捷函数

    Args:
        audio_path: 音频文件路径

    Returns:
        识别文本
    """
    try:
        asr = SherpaOnnxASR()
        return asr.transcribe(audio_path)
    except Exception as e:
        print(f"Sherpa-ONNX 识别失败: {e}")
        return ""


if __name__ == "__main__":
    # 测试
    import sys

    if len(sys.argv) < 2:
        print("用法: python asr_sherpa_onnx.py <音频文件>")
        sys.exit(1)

    audio_file = sys.argv[1]
    if not os.path.exists(audio_file):
        print(f"文件不存在: {audio_file}")
        sys.exit(1)

    print(f"识别文件: {audio_file}")
    text = transcribe_voice_sherpa(audio_file)
    print(f"识别结果: {text}")
