from collections import namedtuple

Trade = namedtuple("Trade", ["account_name", "order_id", "order_type", "quantity", "fill_price", "fill_time"])
