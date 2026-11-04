import os, sys, time, json
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
KEY = os.environ["MODEL_API_KEY"]
BASE = "https://api.meta.ai/v1"
AUDIO = Path(__file__).resolve().parent / "audio"
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
KEYWORDS = ["긴급탈출","맨다운","메이데이","대원고립","공기잔량","한빛구조대","누리구조대","김하늘","신속동료구조팀","인화물질"]
def scrub(s):
    return str(s).replace(KEY, "<KEY>")
