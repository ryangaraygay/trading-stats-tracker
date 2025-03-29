import threading
import time
import datetime
import subprocess

class HammerspoonAlertManager:
    """
    Manages Hammerspoon alerts with account-specific display limits.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._account_message_data = {}  # Store display data per account and message

    def _execute_hammerspoon_lua(self, lua_code: str):
        """Executes Lua code in Hammerspoon using hammerspoon_bridge with -c."""
        try:
            subprocess.run(["hs", "-c", lua_code], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error executing Hammerspoon Lua: {e}")

    def display_alert(self, message: str, account: str, duration_secs: float = 2.0, display_once: bool = False, min_interval_secs: int = 0):
        """
        Displays a Hammerspoon alert with account-specific display limits.

        Args:
            message: The message to display.
            account: The account associated with the message.
            duration_secs: The duration of the alert in seconds.
            display_once: If True, the message will only be displayed once per account.
            min_interval_secs: Minimum interval in seconds between displaying the same message per account.
        """
        threading.Thread(target=self._display_alert_thread, args=(message, account, duration_secs, display_once, min_interval_secs)).start()

    def _display_alert_thread(self, message: str, account: str, duration_secs: float, display_once: bool, min_interval_secs: int):
        with self._lock:
            now = datetime.datetime.now()

            # Get or create account-specific message data
            if account not in self._account_message_data:
                self._account_message_data[account] = {}
            if message not in self._account_message_data[account]:
                self._account_message_data[account][message] = {
                    "last_display_time": None,
                    "displayed": False,
                }
            message_info = self._account_message_data[account][message]

            # Check display_once limit
            if display_once and message_info["displayed"]:
                return

            # Check min_interval limit
            if message_info["last_display_time"] and min_interval_secs > 0:
                time_since_last_display = (now - message_info["last_display_time"]).total_seconds()
                if time_since_last_display < min_interval_secs:
                    return

            # Display the alert via hammerspoon_bridge
            lua_code = f'hs.alert.show("{message}", {duration_secs})'
            self._execute_hammerspoon_lua(lua_code)

            # Update message data
            message_info["last_display_time"] = now
            if display_once:
                message_info["displayed"] = True

# # Example usage (app.py)
# if __name__ == "__main__":
#     alert_manager = HammerspoonAlertManager()

#     # Display a message only once for Account1
#     alert_manager.display_alert("Unique Message", "Account1", display_once=True)
#     alert_manager.display_alert("Unique Message", "Account1", display_once=True) # Will not display again for Account1

#     # Display the same message for Account2 (should display)
#     alert_manager.display_alert("Unique Message", "Account2", display_once=True)

#     # Display a message with a minimum interval for Account1
#     alert_manager.display_alert("Interval Message", "Account1", min_interval_secs=10)
#     alert_manager.display_alert("Interval Message", "Account1", min_interval_secs=10) # Will not display again for 10 seconds for Account1
#     time.sleep(11)
#     alert_manager.display_alert("Interval Message", "Account1", min_interval_secs=10) #Will display after 10 seconds for Account 1.

#     # Display the same message for Account2 (should display)
#     alert_manager.display_alert("Interval Message", "Account2", min_interval_secs=10)