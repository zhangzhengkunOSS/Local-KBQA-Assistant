import json
from vosk import Model as VoskModel, KaldiRecognizer
from config import VOSK_MODEL_PATH, SAMPLE_RATE


class VoiceHandler:
    def __init__(self):
        if not VOSK_MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Vosk 模型不存在: {VOSK_MODEL_PATH}\n"
                "请先运行: python init_project.py"
            )
        print(f"加载 Vosk 模型: {VOSK_MODEL_PATH}")
        self.model = VoskModel(str(VOSK_MODEL_PATH))

    def transcribe(self, pcm_data: bytes) -> str:
        recognizer = KaldiRecognizer(self.model, SAMPLE_RATE)
        recognizer.SetWords(True)
        texts = []
        step = 4000
        for i in range(0, len(pcm_data), step):
            if recognizer.AcceptWaveform(pcm_data[i:i + step]):
                r = json.loads(recognizer.Result())
                if r.get("text"):
                    texts.append(r["text"])
        r = json.loads(recognizer.FinalResult())
        if r.get("text"):
            texts.append(r["text"])
        return "".join(texts).strip()