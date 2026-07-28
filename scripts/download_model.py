"""Download FinBERT sekali dan simpan di dalam proyek."""
from pathlib import Path

from transformers import AutoModelForSequenceClassification, AutoTokenizer


MODEL_NAME = "ProsusAI/finbert"
TARGET = Path(__file__).resolve().parents[1] / "models" / "finbert"

print("Downloading FinBERT... (~440MB)")
TARGET.mkdir(parents=True, exist_ok=True)
AutoTokenizer.from_pretrained(MODEL_NAME).save_pretrained(TARGET)
AutoModelForSequenceClassification.from_pretrained(MODEL_NAME).save_pretrained(TARGET)
print(f"Model tersimpan di {TARGET}")
