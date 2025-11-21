import json
from pathlib import Path

from scripts import export_mw_fills


def make_fill_line(
    order_id: int,
    account: str = "ACC123",
    symbol: str = "ES",
    side: str = "BUY",
    qty: str = "1.00",
    time_str: str = "02/03/2024 9:15 AM",
    price: str = "5020.50",
) -> str:
    return (
        f"2024-02-03 09:15:00 INFO OrderDirectory::orderFilled() order: ID: SIM-{order_id} "
        f"{account} {symbol}.CME meta Filled {side} meta Qty:{qty} meta Last Fill Time: {time_str} "
        f"meta fill price: {price}"
    )


def test_export_cli_writes_partitions_and_dedupes(tmp_path: Path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    session1 = input_dir / "session1.log"
    session1.write_text(
        "\n".join(
            [
                make_fill_line(order_id=101, side="BUY"),
                make_fill_line(order_id=102, side="SELL"),
            ]
        )
    )

    exit_code = export_mw_fills.main(
        ["--input", str(input_dir), "--output", str(output_dir)]
    )
    assert exit_code == 0

    partitions = list(output_dir.rglob("fills.jsonl"))
    assert len(partitions) == 1
    with partitions[0].open("r", encoding="utf-8") as file:
        lines = [line for line in file.read().splitlines() if line.strip()]
    assert len(lines) == 2

    state = json.loads((output_dir / "state.json").read_text())
    assert str(session1) in state["sessions"]

    session2 = input_dir / "session2.log"
    # Duplicate of order 101 plus a new order 103 in the same partition
    session2.write_text(
        "\n".join(
            [
                make_fill_line(order_id=101, side="BUY"),
                make_fill_line(order_id=103, side="BUY", price="5100.25"),
            ]
        )
    )

    exit_code = export_mw_fills.main(
        ["--input", str(input_dir), "--output", str(output_dir)]
    )
    assert exit_code == 0

    with partitions[0].open("r", encoding="utf-8") as file:
        lines = [line for line in file.read().splitlines() if line.strip()]
    # Only one new record should be appended
    assert len(lines) == 3


def test_export_cli_latest_only_uses_newest_file(tmp_path: Path, monkeypatch):
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    older = input_dir / "older.log"
    newer = input_dir / "newer.log"
    older.write_text(make_fill_line(order_id=1, time_str="02/01/2024 9:15 AM"))
    newer.write_text(make_fill_line(order_id=2, time_str="02/02/2024 9:15 AM"))

    # Ensure mtime ordering
    import os
    os.utime(older, (older.stat().st_atime, older.stat().st_mtime - 60))

    exit_code = export_mw_fills.main(
        ["--input", str(input_dir), "--output", str(output_dir), "--latest"]
    )
    assert exit_code == 0

    partitions = list(output_dir.rglob("fills.jsonl"))
    assert len(partitions) == 1
    with partitions[0].open("r", encoding="utf-8") as file:
        lines = [line for line in file.read().splitlines() if line.strip()]
    records = [json.loads(line) for line in lines]
    assert len(records) == 1
    assert records[0]["order_id"] == 2
