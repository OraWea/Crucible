"""
快速测试：验证百炼实时流式 ASR 能否正确识别本地 WAV 文件
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Crucible.config import Config
Config.init_paths()

from Crucible.models.whisper_model import WhisperTranscriber

wav_path = os.path.join(Config.TEMP_DIR, "processed_audio.wav")
if not os.path.exists(wav_path):
    print(f"测试音频文件不存在: {wav_path}")
    sys.exit(1)

print(f"音频文件: {wav_path} ({os.path.getsize(wav_path)} bytes)")
print(f"API Key: {Config.LLM_API_KEY[:8]}..." if Config.LLM_API_KEY else "未设置 API Key!")
print("---")

transcriber = WhisperTranscriber()
segments = transcriber.transcribe(wav_path, language="zh")

print(f"\n=== 识别结果: 共 {len(segments)} 个片段 ===")
for seg in segments:
    print(f"  [{seg['start']:.2f}s - {seg['end']:.2f}s]: {seg['text']}")
