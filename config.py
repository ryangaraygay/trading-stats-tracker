from default import DEFAULT
from concern_level import ConcernLevel

class Config:
    def __init__(self):
        self.alert_enabled = DEFAULT.alert_enabled
        self.alert_duration_default = DEFAULT.alert_duration_default
        self.alert_duration_critical = DEFAULT.alert_duration_critical
        self.alert_min_interval_secs_default = DEFAULT.alert_min_interval_secs_default
        self.directory_path = DEFAULT.directory_path
        self.auto_refresh_ms = DEFAULT.auto_refresh_ms
        self.contract_symbol = DEFAULT.contract_symbol
        self.contract_value = DEFAULT.contract_value
        self.open_trade_duration_notice_mins = DEFAULT.open_trade_duration_notice_mins
        self.open_duration_refresh_ms = DEFAULT.open_duration_refresh_ms
        self.block_app_on_critical_alerts = DEFAULT.block_app_on_critical_alerts
        self.block_app_name = DEFAULT.block_app_name

    def get_alert_duration(self, level: ConcernLevel):
        if level == ConcernLevel.CRITICAL:
            return self.alert_duration_critical
        elif level == ConcernLevel.WARNING:
            return self.alert_duration_warning
        else:
            return self.alert_duration_default
        
    def get_min_interval_secs(self, level: ConcernLevel): 
        if level == ConcernLevel.CRITICAL:
            return self.alert_min_interval_secs_default
        elif level == ConcernLevel.WARNING:
            return self.alert_min_interval_secs_default
        else:
            return self.alert_min_interval_secs_default