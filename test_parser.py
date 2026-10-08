from app import parse_order, total, reply_text

def test_hinglish_basic():
    items = parse_order("bhaiya do kilo atta aur ek packet doodh dena")
    d = {i["item"]: i for i in items}
    assert d["atta"]["qty"] == 2 and d["doodh"]["qty"] == 1
    assert total(items) == 2*45 + 28

def test_digits_and_half():
    items = parse_order("5 kg chawal aur aadha tel")
    d = {i["item"]: i["qty"] for i in items}
    assert d == {"chawal": 5, "tel": 0.5}

def test_devanagari():
    items = parse_order("दो चीनी और एक नमक")
    assert {i["item"] for i in items} == {"cheeni", "namak"}

def test_unknown():
    assert parse_order("kuch nahi chahiye") == []
    assert "samajh nahi" in reply_text([])

def test_multiword():
    items = parse_order("teen chai patti")
    assert items[0]["item"] == "chai patti" and items[0]["qty"] == 3

def test_devanagari_transcript():
    items = parse_order("भाया 2 किलो आता और एक पैकेट दूध देना।")
    d = {i["item"]: i["qty"] for i in items}
    assert d == {"atta": 2, "doodh": 1}

def test_danda():
    items = parse_order("5 किलो चीनी, एक किलो दाल और 2 पैकेट नमक।")
    assert {i["item"]: i["qty"] for i in items} == {"cheeni": 5, "dal": 1, "namak": 2}
