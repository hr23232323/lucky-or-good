from lucky.ledger import Ledger


def test_chain_intact(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    for i in range(3):
        led.append({"kind": "trial", "n": i})
    assert led.verify() == []
    assert [e["seq"] for e in led.entries()] == [1, 2, 3]


def test_edit_is_detected(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    for i in range(3):
        led.append({"kind": "trial", "sharpe": i})
    lines = led.path.read_text().splitlines()
    lines[1] = lines[1].replace('"sharpe": 1', '"sharpe": 9')
    led.path.write_text("\n".join(lines) + "\n")
    assert led.verify()


def test_deletion_is_detected(tmp_path):
    led = Ledger(tmp_path / "l.jsonl")
    for i in range(3):
        led.append({"kind": "trial", "n": i})
    lines = led.path.read_text().splitlines()
    led.path.write_text("\n".join([lines[0], lines[2]]) + "\n")
    assert led.verify()
