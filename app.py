"""Kirana Voice Orders: multilingual voice ordering for a neighbourhood kirana.
Gnani Prisma v2.5 (speech to text) + Gnani Timbre v2.5 (text to speech), 10 Indian languages.
Synthetic catalog and prices. Order parsing is plain rules, no LLM."""
import os, base64, asyncio, hashlib, time
import httpx
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse, Response
from lang import LANGS, CATALOG
from orderparser import parse_order, total, reply_text, detect_and_parse

BASE = "https://api.vachana.ai"
app = FastAPI(title="Kirana Voice Orders (demo, synthetic data)")
HERE = os.path.dirname(__file__)

def _headers():
    key = os.environ.get("GNANI_API_KEY")
    if not key:
        raise RuntimeError("GNANI_API_KEY not set")
    return {"X-API-Key-ID": key}

async def _retry(fn, *a):
    for attempt in range(3):
        try:
            return await fn(*a)
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 429 or attempt == 2:
                raise
            await asyncio.sleep(1.5 * (attempt + 1))

async def _stt(audio, filename, language_code):
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"{BASE}/stt/v3", headers=_headers(),
                         files={"audio_file": (filename, audio)}, data={"language_code": language_code})
        r.raise_for_status()
        return r.json()["transcript"]

async def _tts(text, voice, language):
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"{BASE}/api/v1/tts/inference", headers=_headers(),
                         json={"text": text, "voice": voice, "model": "timbre-v2.5", "language": language,
                               "audio_config": {"sample_rate": 24000, "num_channels": 1, "sample_width": 2,
                                                "encoding": "linear_pcm", "container": "wav"}})
        r.raise_for_status()
        return r.content

stt = lambda a, f, l: _retry(_stt, a, f, l)
tts = lambda t, v, l: _retry(_tts, t, v, l)

def _result(lang, items, transcript=None):
    return {"lang": lang, "lang_name": LANGS[lang]["name"], "transcript": transcript, "items": items,
            "total": total(items), "reply": reply_text(items, lang)}

@app.get("/health")
def health():
    return {"ok": True, "languages": list(LANGS)}

@app.get("/languages")
def languages():
    return [{"code": c, "name": L["name"], "native": L["native"], "stt": L["stt"], "voice": L["voice"],
             "samples": L["samples"], "ui": L["ui"]} for c, L in LANGS.items()]

@app.get("/catalog")
def catalog(lang: str = "en"):
    L = LANGS.get(lang, LANGS["en"])
    return [{"item": k, "name": L["names"][k][0], "english": LANGS["en"]["names"][k][0], "emoji": v["emoji"],
             "unit": v["unit"], "unit_label": L["units"][v["unit"]], "price": v["price"]} for k, v in CATALOG.items()]

@app.post("/order/text")
async def order_text(payload: dict):
    text, lang = payload.get("text", ""), payload.get("lang", "auto")
    if lang == "auto" or lang not in LANGS:
        lang, items = detect_and_parse(text)
    else:
        items = parse_order(text, lang)
    r = _result(lang, items, text)
    if payload.get("speak"):
        try:
            L = LANGS[lang]
            r["reply_audio_b64"] = base64.b64encode(await tts(r["reply"], L["voice"], L["tts"])).decode()
        except Exception as e:
            r["audio_error"] = "Voice reply unavailable right now. Text reply shown instead."
    return r

@app.post("/order/voice")
async def order_voice(audio: UploadFile = File(...), lang: str = Form("auto")):
    data = await audio.read()
    wav, audio_error = None, None
    try:
        if lang in LANGS:
            transcript = await stt(data, audio.filename or "audio.wav", LANGS[lang]["stt"])
            items = parse_order(transcript, lang)
        else:
            # auto: ask Gnani to detect the language, fall back to Hindi
            try:
                transcript = await stt(data, audio.filename or "audio.wav", "indic-auto")
            except httpx.HTTPStatusError as e:
                if e.response.status_code not in (400, 422):
                    raise
                transcript = await stt(data, audio.filename or "audio.wav", "hi-IN")
            lang, items = detect_and_parse(transcript)
        r = _result(lang, items, transcript)
        try:
            L = LANGS[lang]
            wav = await tts(r["reply"], L["voice"], L["tts"])
        except httpx.HTTPStatusError as e:
            audio_error = f"Voice reply unavailable (Gnani TTS {e.response.status_code}). Text reply shown instead."
    except httpx.HTTPStatusError as e:
        return JSONResponse({"error": f"Gnani API returned {e.response.status_code} on {e.request.url.path}: {e.response.text[:160]}"}, status_code=502)
    except RuntimeError as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {str(e)[:160]}"}, status_code=502)
    r["reply_audio_b64"] = base64.b64encode(wav).decode() if wav else None
    r["audio_error"] = audio_error
    return r

@app.post("/order/confirm")
async def confirm(payload: dict):
    """Demo confirmation: builds an order id and a spoken confirmation. Nothing is placed anywhere."""
    lang = payload.get("lang", "hi"); lang = lang if lang in LANGS else "hi"
    items = payload.get("items", [])
    amount = round(sum(float(i.get("line_total", 0)) for i in items), 2)
    oid = "KV" + hashlib.sha1(f"{time.time()}{amount}".encode()).hexdigest()[:6].upper()
    return {"order_id": oid, "total": amount, "eta_min": 10}

@app.get("/sample")
async def sample(lang: str = "hi", n: int = 0):
    """Synthetic customer audio made with Timbre, one of two phrases per language (cached per instance)."""
    lang = lang if lang in LANGS else "hi"; L = LANGS[lang]
    n = n % len(L["samples"]); key = (lang, n)
    try:
        if key not in _cache:
            _cache[key] = await tts(L["samples"][n], L["voice"], L["tts"])
    except Exception as e:
        return JSONResponse({"error": str(e)[:160]}, status_code=502)
    return Response(_cache[key], media_type="audio/wav", headers={"X-Sample-Text": base64.b64encode(L["samples"][n].encode()).decode()})

_cache = {}

@app.get("/")
def index():
    return FileResponse(os.path.join(HERE, "index.html"))
