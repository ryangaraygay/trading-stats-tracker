from collections import namedtuple

AlertMessage = namedtuple("AlertMessage", ["message", "account", "duration_secs", "display_once", "min_interval_secs", "critical", "extra_msg"])
