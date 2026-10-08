"""Rule-based multilingual order parser (no LLM). Deterministic and unit-testable.
Works on the transcript text in any of the 10 supported languages."""
import re, unicodedata
from lang import CATALOG, LANGS, GRAM_WORDS

_PUNCT = "\u0964\u0965,;:!?\"'()[]{}|\u2018\u2019\u201c\u201d"

def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s.lower())
    out = []
    for ch in s:
        if ch.isdigit() and not ch.isascii():
            try: ch = str(unicodedata.digit(ch))
            except ValueError: pass
        out.append(ch)
    return "".join(out)

def tokenize(text: str):
    toks = []
    for t in norm(text).split():
        t = t.strip(_PUNCT).strip(".")
        for p in _PUNCT:
            t = t.replace(p, "")
        if t: toks.append(t)
    return toks

def _is_num(t):
    return re.fullmatch(r"\d+(\.\d+)?", t) is not None

_VIRAMAS = "\u094d\u09cd\u0a4d\u0acd\u0bcd\u0c4d\u0ccd\u0d4d"
_EXACT = set()

def _match(tok, name):
    if tok == name: return True
    if len(name) <= 2 or tok in _EXACT: return False
    stem = name.rstrip(_VIRAMAS) if not name.isascii() else name
    if len(stem) < 2 or not tok.startswith(stem): return False
    return len(tok) - len(stem) <= (2 if name.isascii() else 6)

for _L in LANGS.values():
    for _names in _L["names"].values():
        _EXACT.update(norm(n) for n in _names if " " not in n)

def parse_order(text: str, lang: str = "hi"):
    L = LANGS[lang]
    toks = tokenize(text)
    nums_map = {norm(k): v for k, v in L["nums"].items()}
    # numbers
    nums = []  # (idx, value)
    for i, t in enumerate(toks):
        v = float(t) if _is_num(t) else nums_map.get(t)
        if v is None: continue
        if i + 1 < len(toks) and any(toks[i + 1].startswith(norm(g)) for g in GRAM_WORDS) and v >= 10:
            v = v / 1000.0
        nums.append([i, v, False])
    # item occurrences (first match per catalog item)
    occ = []  # (start, end, key, matched_name)
    for key in CATALOG:
        names = sorted({norm(n) for n in L["names"][key]}, key=lambda n: -len(n.split()))
        hit = None
        for name in names:
            nt = name.split()
            for i in range(len(toks) - len(nt) + 1):
                if all(_match(toks[i + j], nt[j]) for j in range(len(nt))):
                    hit = (i, i + len(nt), key); break
            if hit: break
        if hit: occ.append(hit)
    occ.sort()
    qty = {}
    def before(n, s, e, key):
        lo = occ[n - 1][1] if n else 0
        cand = [x for x in nums if not x[2] and lo <= x[0] < s]
        return max(cand, key=lambda x: x[0]) if cand else None
    def after(n, s, e, key):
        hi = occ[n + 1][0] if n + 1 < len(occ) else len(toks)
        cand = [x for x in nums if not x[2] and e <= x[0] < hi]
        return min(cand, key=lambda x: x[0]) if cand else None
    # Style: number-first ("2 kilo atta", the usual order) unless the first number comes after the first item ("atta 2 kilo")
    style = [before, after] if (not occ or not nums or nums[0][0] < occ[0][0]) else [after, before]
    for fn in style:
        for n, (s, e, key) in enumerate(occ):
            if key in qty: continue
            x = fn(n, s, e, key)
            if x: x[2] = True; qty[key] = x[1]
    items = []
    for s, e, key in occ:
        q = qty.get(key); assumed = q is None
        q = 1.0 if assumed else q
        meta = CATALOG[key]
        items.append({"item": key, "name": L["names"][key][0], "emoji": meta["emoji"], "qty": q, "unit": meta["unit"],
                      "unit_label": L["units"][meta["unit"]], "price": meta["price"],
                      "line_total": round(q * meta["price"], 2), "assumed_qty": assumed})
    return items

def total(items):
    return round(sum(i["line_total"] for i in items), 2)

def reply_text(items, lang="hi"):
    L = LANGS[lang]
    if not items: return L["miss"]
    parts = [f"{i['qty']:g} {i['unit_label']} {i['name']}" for i in items]
    return L["reply"].format(items=", ".join(parts), total=f"{total(items):g}")

def detect_and_parse(text: str):
    """Pick the best language for a transcript: by script, then by how many items match."""
    best = None
    for code in LANGS:
        its = parse_order(text, code)
        score = (len(its), sum(1 for i in its if not i["assumed_qty"]))
        if best is None or score > best[0]:
            best = (score, code, its)
    return best[1], best[2]
