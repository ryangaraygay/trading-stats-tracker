from collections import namedtuple

AlertMessage = namedtuple("AlertMessage", ["message", "account", "duration_secs", "min_interval_secs", "level", "extra_msg"])
