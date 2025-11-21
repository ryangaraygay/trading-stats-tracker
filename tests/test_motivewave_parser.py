import datetime
from pathlib import Path

from motivewave_parser import parse_fills, parse_fills_from_file


def make_fill_line(
    order_id: int,
    account: str = "ACC123",
    symbol: str = "ES",
    side: str = "BUY",
    qty: str = "2.00",
    time_str: str = "02/03/2024 9:15 AM",
    price: str = "5020.50",
) -> str:
    return (
        f"2024-02-03 09:15:00 INFO OrderDirectory::orderFilled() order: ID: SIM-{order_id} "
        f"{account} {symbol}.CME meta Filled {side} meta Qty:{qty} meta Last Fill Time: {time_str} "
        f"meta fill price: {price}"
    )


def test_parse_fills_from_file_parses_trade(tmp_path: Path):
    log_path = tmp_path / "session1.log"
    log_path.write_text(
        "\n".join(
            [
                "noise line",
                make_fill_line(order_id=12),
                "trailer",
            ]
        )
    )

    fills = parse_fills_from_file(str(log_path))
    assert len(fills) == 1
    trade = fills[0]
    assert trade.account_name == "ACC123"
    assert trade.order_id == 12
    assert trade.contract_symbol == "ES"
    assert trade.fill_price == 5020.50
    assert trade.quantity == 2.00
    # Ensure timestamp is parsed to datetime
    assert trade.fill_time == datetime.datetime(2024, 2, 3, 9, 15)


def test_parse_fills_dedupes_by_account_and_order(tmp_path: Path):
    input_dir = tmp_path
    file_one = input_dir / "one.log"
    file_two = input_dir / "two.log"

    file_one.write_text(make_fill_line(order_id=33, account="ACC999"))
    file_two.write_text(make_fill_line(order_id=33, account="ACC999"))

    fills = parse_fills([str(file_one), str(file_two)])
    # deduped by (account, order_id)
    assert len(fills) == 1
    assert fills[0].order_id == 33
