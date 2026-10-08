from orderparser import parse_order, total, detect_and_parse
from lang import LANGS

def q(items): return {i["item"]: i["qty"] for i in items}

def test_hindi_basic():
    assert q(parse_order("भैया दो किलो आटा और एक पैकेट दूध दे दो", "hi")) == {"atta": 2, "milk": 1}

def test_danda_and_hinglish():
    assert q(parse_order("5 किलो चीनी, एक किलो दाल और 2 पैकेट नमक।", "hi")) == {"sugar": 5, "dal": 1, "salt": 2}
    assert q(parse_order("do kilo atta aur ek packet doodh", "hi")) == {"atta": 2, "milk": 1}

def test_english_and_after_quantity():
    assert q(parse_order("two kilos of atta and one packet of milk please", "en")) == {"atta": 2, "milk": 1}
    assert q(parse_order("rice 3 kg and oil 2 litre", "en")) == {"rice": 3, "oil": 2}

def test_missing_qty_is_assumed_not_stolen():
    items = parse_order("2 किलो आटा, दूध", "hi")
    d = {i["item"]: i for i in items}
    assert d["milk"]["assumed_qty"] and d["atta"]["qty"] == 2

def test_half_and_grams():
    assert q(parse_order("आधा किलो दाल", "hi")) == {"dal": 0.5}
    assert q(parse_order("500 gram sugar", "en")) == {"sugar": 0.5}

def test_native_digits():
    assert q(parse_order("२ किलो आटा", "hi")) == {"atta": 2}

def test_every_language_sample_parses():
    for code, L in LANGS.items():
        for s in L["samples"]:
            items = parse_order(s, code)
            assert len(items) >= 2, (code, s, items)
            assert all(not i["assumed_qty"] for i in items), (code, s, items)

def test_agglutinative_suffix():
    assert q(parse_order("இரண்டு கிலோ அரிசியும் ஒரு பாக்கெட் பாலும்", "ta")) == {"rice": 2, "milk": 1}

def test_detect_script():
    code, items = detect_and_parse("ਭਾਜੀ ਦੋ ਕਿਲੋ ਆਟਾ ਤੇ ਇੱਕ ਪੈਕੇਟ ਦੁੱਧ")
    assert code == "pa" and len(items) == 2

def test_ml_transcript_variant():
    assert q(parse_order("ചേട്ടാ രണ്ടു കിലോ അരി ഒരു പാക്കറ്റ് പാൽ തരൂ", "ml")) == {"rice": 2, "milk": 1}
