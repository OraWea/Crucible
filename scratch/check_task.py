import os
import sys
# Go up 3 levels to reach C:\Users\qingz\Desktop so 'import Crucible' works
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import dashscope
from dashscope.audio.asr import Transcription
from Crucible.config import Config

dashscope.api_key = Config.LLM_API_KEY
print("API Key:", dashscope.api_key[:8] + "..." if dashscope.api_key else None)

task_id = "f6e8b4fb-b10c-47ca-8aff-ace7f522d6ed"
response = Transcription.fetch(task=task_id)
print("Status Code:", response.status_code)
print("Message:", response.message)
print("Output:", response.output)
