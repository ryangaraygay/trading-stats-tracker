from collections import namedtuple

Trade = namedtuple("Trade", ["account_name", "order_id", "order_type", "contract_symbol", "quantity", "fill_price", "fill_time"])
