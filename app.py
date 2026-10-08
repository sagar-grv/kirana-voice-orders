"""Kirana Voice Orders: Hinglish voice ordering on Gnani Prisma v2.5 (STT) and Timbre v2.5 (TTS). Synthetic catalog."""
import os, re, base64, httpx
# Synthetic kirana catalog. Prices are made up for the demo.
CATALOG = {
    "atta": {"names": ["atta", "aata", "आटा", "flour"], "unit": "kg", "price": 45},
    "chawal": {"names": ["chawal", "rice", "चावल"], "unit": "kg", "price": 60},
    "cheeni": {"names": ["cheeni", "chini", "sugar", "चीनी"], "unit": "kg", "price": 48},
    "dal": {"names": ["dal", "daal", "दाल"], "unit": "kg", "price": 120},
    "tel": {"names": ["tel", "oil", "तेल"], "unit": "litre", "price": 150},
    "doodh": {"names": ["doodh", "milk", "दूध"], "unit": "packet", "price": 28},
    "chai patti": {"names": ["chai patti", "chai", "tea", "चाय पत्ती"], "unit": "packet", "price": 90},
    "namak": {"names": ["namak", "salt", "नमक"], "unit": "packet", "price": 25},
}

"""Rule-based Hinglish order parser. No LLM; deterministic and testable."""

NUM_WORDS = {
    "ek": 1, "one": 1, "एक": 1, "do": 2, "two": 2, "दो": 2, "teen": 3, "three": 3, "तीन": 3,
    "char": 4, "chaar": 4, "four": 4, "चार": 4, "paanch": 5, "panch": 5, "five": 5, "पांच": 5,
    "chhe": 6, "six": 6, "saat": 7, "seven": 7, "aath": 8, "eight": 8, "nau": 9, "nine": 9,
    "das": 10, "ten": 10, "aadha": 0.5, "adha": 0.5, "half": 0.5, "आधा": 0.5,
}

def _qty_before(tokens, idx):
    for j in range(max(0, idx - 3), idx):
        t = tokens[j]
        if re.fullmatch(r"\d+(\.\d+)?", t):
            return float(t)
        if t in NUM_WORDS:
            return float(NUM_WORDS[t])
    return None

def parse_order(text: str):
    """Return (items, unmatched_hint). items: [{item, qty, unit, price}]."""
    low = text.lower()
    tokens = re.findall(r"[\w\u0900-\u097F.]+", low)
    items, seen = [], set()
    for key, meta in CATALOG.items():
        for name in sorted(meta["names"], key=len, reverse=True):
            nt = name.split()
            for i in range(len(tokens) - len(nt) + 1):
                if tokens[i:i + len(nt)] == nt and key not in seen:
                    q = _qty_before(tokens, i)
                    qty = q if q is not None else 1.0
                    seen.add(key)
                    items.append({"item": key, "qty": qty, "unit": meta["unit"],
                                  "price": meta["price"], "line_total": round(qty * meta["price"], 2),
                                  "assumed_qty": q is None})
    return items

def total(items):
    return round(sum(i["line_total"] for i in items), 2)

def reply_text(items):
    if not items:
        return "Maaf kijiye, mujhe order samajh nahi aaya. Kripya dobara bolein."
    parts = [f"{i['qty']:g} {i['unit']} {i['item']}" for i in items]
    return f"Aapka order: {', '.join(parts)}. Kul {total(items):g} rupaye. Confirm karein?"

"""Thin client for Gnani Prisma v2.5 (STT) and Timbre v2.5 (TTS). Needs GNANI_API_KEY."""

BASE = "https://api.vachana.ai"

def _headers():
    key = os.environ.get("GNANI_API_KEY")
    if not key:
        raise RuntimeError("GNANI_API_KEY not set")
    return {"X-API-Key-ID": key}

async def stt(audio: bytes, filename: str, language_code="hi-en") -> str:
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"{BASE}/stt/v3", headers=_headers(),
                         files={"audio_file": (filename, audio)},
                         data={"language_code": language_code})
        r.raise_for_status()
        return r.json()["transcript"]

async def tts(text: str, voice="Nalini", language="hi-en") -> bytes:
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"{BASE}/api/v1/tts/inference", headers=_headers(),
                         json={"text": text, "voice": voice, "model": "timbre-v2.5",
                               "language": language,
                               "audio_config": {"sample_rate": 24000, "num_channels": 1,
                                                "sample_width": 2, "encoding": "linear_pcm",
                                                "container": "wav"}})
        r.raise_for_status()
        return r.content

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse

app = FastAPI(title="Kirana Voice Orders (demo, synthetic data)")

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/order/text")
async def order_text(payload: dict):
    """Text path (also used to test the parser without any API call)."""
    items = parse_order(payload.get("text", ""))
    return {"items": items, "total": total(items), "reply": reply_text(items)}

@app.post("/order/voice")
async def order_voice(audio: UploadFile = File(...), language_code: str = "hi-en"):
    data = await audio.read()
    transcript = await stt(data, audio.filename or "audio.wav", language_code)
    items = parse_order(transcript)
    reply = reply_text(items)
    wav = await tts(reply)
    return {"transcript": transcript, "items": items, "total": total(items),
            "reply": reply, "reply_audio_b64": base64.b64encode(wav).decode()}

@app.get("/")
def index():
    return FileResponse(os.path.join(os.path.dirname(__file__),"index.html"))
