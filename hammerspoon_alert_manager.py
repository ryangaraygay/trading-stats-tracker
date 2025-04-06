import threading
import time
import datetime
import subprocess
import urllib.parse
import os

from urllib.parse import quote
from concern_level import ConcernLevel

class HammerspoonAlertManager:
    """
    Manages Hammerspoon alerts with account-specific display limits.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._account_message_data = {}  # Store display data per account and message
        self._last_event_call = {}  # Store last call time per event name

    def trigger_event(self, event_name: str, params: dict = None, min_interval_secs: int = 60):
        """
        Triggers a Hammerspoon event via its URL scheme, respecting the minimum interval.

        Args:
            event_name: The name of the Hammerspoon event to trigger.
            params: A dictionary of parameters to pass with the event. These will be URL-encoded.
            min_interval_secs: Minimum interval in seconds since the last call for this event name.
        """
        threading.Thread(target=self._trigger_event_thread, args=(event_name, params, min_interval_secs)).start()

    def _trigger_event_thread(self, event_name: str, params: dict, min_interval_secs: int):
        with self._lock:
            now = datetime.datetime.now()

            if event_name in self._last_event_call:
                last_call_time = self._last_event_call[event_name]
                time_since_last_call = (now - last_call_time).total_seconds()
                if time_since_last_call < min_interval_secs:
                    return  # Discard the call

            encoded_params = ""
            if params:
                encoded_params = quote(urllib.parse.urlencode(params))

            url = f"hammerspoon://{event_name}?p={encoded_params}"
            open_path = "/usr/bin/open"

            if os.path.exists(open_path):
                try:
                    subprocess.run([open_path, "-g", url], check=True)
                    self._last_event_call[event_name] = now
                except subprocess.CalledProcessError as e:
                    print(f"Error triggering Hammerspoon event '{event_name}': {e}")
            else:
                print(f"Error: '{open_path}' not found.")

    def _execute_hammerspoon_lua(self, lua_code: str):
        """Executes Lua code in Hammerspoon using hammerspoon_bridge with -c."""
        try:
            # print(f'lua {lua_code}')
            hs_path = "/usr/local/bin/hs"
            subprocess.run([hs_path,'-c', lua_code], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error executing Hammerspoon Lua: {e}")

    def display_alert(self, message: str, account: str, duration_secs: float = 2.0, min_interval_secs: int = 0, concern_level: ConcernLevel = ConcernLevel.DEFAULT, extra_msg: str = ""):
        """
        Displays a Hammerspoon alert with account-specific display limits.

        Args:
            message: The message to display.
            account: The account associated with the message.
            duration_secs: The duration of the alert in seconds.
            min_interval_secs: Minimum interval in seconds between displaying the same message per account.
            concern_level: The level of concern associated with the message (default: ConcernLevel.DEFAULT).
            extra_msg: An extra message to display but will not have an effect on interval between displaying same message per account.
        """
        threading.Thread(target=self._display_alert_thread, args=(message, account, duration_secs, min_interval_secs, concern_level, extra_msg)).start()

    def _display_alert_thread(self, message: str, account: str, duration_secs: float, min_interval_secs: int, concern_level: ConcernLevel, extra_msg: str):
        with self._lock:
            now = datetime.datetime.now()

            # Get or create account-specific message data
            if account not in self._account_message_data:
                self._account_message_data[account] = {}
            if message not in self._account_message_data[account]:
                self._account_message_data[account][message] = {
                    "last_display_time": None,
                }
            message_info = self._account_message_data[account][message]

            # Check min_interval limit
            if message_info["last_display_time"] and min_interval_secs > 0:
                time_since_last_display = (now - message_info["last_display_time"]).total_seconds()
                if time_since_last_display < min_interval_secs:
                    return

            # Display the alert via hammerspoon_bridge
            # alert_customization = "{ }"
            fill_color = self.get_fill_color(concern_level)
            alert_customization = "{ fillColor = " + fill_color + ", textColor = { white=0.1, alpha=1 }, radius = 20, textSize = 40, padding = 30}"

            lua_code = f'hs.alert.show("{message} {extra_msg}", {alert_customization}, hs.screen.primaryScreen(), {duration_secs})'
            self._execute_hammerspoon_lua(lua_code)

            # Update message data
            message_info["last_display_time"] = now

    def get_fill_color(self, level: ConcernLevel):
        if level == ConcernLevel.CRITICAL:
            return "{ red = 1, green = 0, blue = 0, alpha = 0.7 }" # red
        elif level == ConcernLevel.WARNING:
            return "{ red = 1, green = 0.65, blue = 0, alpha = 0.7 }" # orange
        elif level == ConcernLevel.OK:
            return "{ red = 0.56, green = 0.93, blue = 0.56, alpha = 0.7 }" # soft green
        else:
            return "{ red = 0.67, green = 0.85, blue = 0.90, alpha = 0.7 }" # soft blue

# # Example usage (app.py)
# if __name__ == "__main__":
#     alert_manager = HammerspoonAlertManager()

#     # Display a message with a minimum interval for Account1
#     alert_manager.display_alert("Interval Message", "Account1", min_interval_secs=10)
#     alert_manager.display_alert("Interval Message", "Account1", min_interval_secs=10) # Will not display again for 10 seconds for Account1
#     time.sleep(11)
#     alert_manager.display_alert("Interval Message", "Account1", min_interval_secs=10) #Will display after 10 seconds for Account 1.

#     # Display the same message for Account2 (should display)
#     alert_manager.display_alert("Interval Message", "Account2", min_interval_secs=10)