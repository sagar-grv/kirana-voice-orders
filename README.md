# Kirana Voice Orders

Hinglish voice order assistant for a neighbourhood kirana store, built for the Great Indian AI Internship Challenge.

Flow: customer speaks -> Gnani Prisma v2.5 (STT) -> rule-based Hinglish order parser -> total -> Gnani Timbre v2.5 (TTS) spoken confirmation.

Gnani models used: Prisma v2.5 and Timbre v2.5. The parser is plain Python rules over a synthetic catalog. No LLM is used. All data is synthetic.

Run: `pip install -r requirements.txt && GNANI_API_KEY=... uvicorn app:app`
Test: `pytest`
