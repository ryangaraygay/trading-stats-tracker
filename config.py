import configparser
import os
from concern_level import ConcernLevel

class Config:
    def __init__(self):
        self.config = self.load_config()
        self.alert_enabled = self.get_bool('alert', 'enabled')
        self.alert_duration_default = int(self.config['alert']['duration_default'])
        self.alert_duration_warning = int(self.config['alert']['duration_warning'])
        self.alert_duration_critical = int(self.config['alert']['duration_critical'])
        self.alert_min_interval_secs_default = int(self.config['alert']['min_interval_secs_default'])
        self.directory_path = self.config['general']['directory_path']
        self.auto_refresh_ms = int(self.config['general']['auto_refresh_ms'])
        self.contract_symbol = self.config['general']['contract_symbol']
        self.contract_value = int(self.config['general']['contract_value'])
        self.open_trade_duration_notice_mins = int(self.config['alert']['open_trade_duration_notice_mins'])
        self.open_duration_refresh_ms = int(self.config['alert']['open_duration_refresh_ms'])
        self.block_app_on_critical_alerts = self.get_bool('alert', 'block_app_on_critical_alerts')
        self.block_app_name = self.config['alert']['block_app_name']
        self.print_streak_followtrade_stats = self.get_bool('general', 'print_streak_followtrade_stats')
        self.interval_stats_print = self.get_bool('interval_stats', 'print')
        self.interval_stats_min = self.get_int('interval_stats', 'interval_mins')

        # for section in self.config.sections():
        #     print(f"[{section}]")
        #     for key, value in self.config.items(section):
        #         print(f"  {key} = {value}")

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
        
    def load_config(self, config_base_name="config"):
        config = configparser.ConfigParser()

        # use app directory as config directory
        config_dir = os.path.dirname(os.path.abspath(__file__))
        default_config_path = os.path.join(config_dir, f"{config_base_name}.ini")
        config.read(default_config_path)

        env = os.environ.get("CONFIG_ENV")
        if env:
            env_config_path = os.path.join(config_dir, f"{config_base_name}.{env}.ini")
            if os.path.exists(env_config_path):
                config.read(env_config_path)
                print(f"Loaded configuration for environment: {env}")
            else:
                print(f"Environment '{env}' specified, but config file '{env_config_path}' not found. Using default.")
        else:
            print("Using default configuration.")

        return config

    def get_bool(self, section, option, default=False):
        """Safely retrieves a boolean value from the configuration."""
        try:
            value_str = self.config.get(section, option)
            if value_str.lower() in ('true', 'yes', 'on', '1'):
                return True
            elif value_str.lower() in ('false', 'no', 'off', '0'):
                return False
            else:
                print(f"Warning: Invalid boolean value '{value_str}' for '{section}.{option}'. Using default: {default}")
                return default
        except (configparser.NoSectionError, configparser.NoOptionError):
            print(f"Warning: Option '{option}' not found in section '{section}'. Using default: {default}")
            return default

    def get_int(self, section, option):
        return int(self.config[section][option])
    
    def get_string(self, section, option):
        return self.config[section][option]