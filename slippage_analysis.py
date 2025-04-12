import re
import collections
import file_utils
from datetime import datetime
from config import Config
from constants import CONST

def analyze_slippage_by_interval(log_content, filename):
    """
    Analyzes trading log content to calculate slippage statistics per 5-minute interval.

    Args:
        log_content (str): A string containing the entire log file content.
        filename (str): The name of the file being analyzed (for reporting).

    Returns:
        dict: A dictionary where keys are 5-minute interval start time strings (HH:MM)
              and values are dictionaries containing {'total_slippage': float, 'trade_count': int}.
              Returns an empty dict if no STP orders found or in case of errors.
    """
    interval_data = collections.defaultdict(lambda: {'total_slippage': 0.0, 'trade_count': 0})

    # Regex to find filled STP order lines and capture timestamp, type, aux, fill
    # Groups: 1=Timestamp (HH:MM:SS), 2=Order Type (BUY STP/SELL STP), 3=Aux Price, 4=Fill Price
    order_fill_regex = re.compile(
        r"(\d{2}:\d{2}:\d{2}).*?OrderDirectory::orderFilled\(\).*?\s(BUY STP|SELL STP)\s.*?Aux:(\d+\.?\d*).*?fill price:\s(\d+\.?\d*)"
    )

    line_num = 0
    for line in log_content.splitlines():
        line_num += 1
        match = order_fill_regex.search(line)
        if match:
            try:
                timestamp_str = match.group(1)
                order_type = match.group(2)
                stop_price = float(match.group(3))
                fill_price = float(match.group(4))
                slippage_this_order = 0.0

                # Parse timestamp to determine the interval
                try:
                    trade_time = datetime.strptime(timestamp_str, '%H:%M:%S')
                    interval_minute = (trade_time.minute // 5) * 5
                    interval_start_time = trade_time.replace(minute=interval_minute, second=0, microsecond=0)
                    interval_key = interval_start_time.strftime('%H:%M')
                except ValueError:
                    print(f"Warning [File: {filename}, Line: {line_num}]: Could not parse timestamp: {timestamp_str}")
                    continue

                if order_type == "BUY STP":
                    slippage_this_order = fill_price - stop_price
                elif order_type == "SELL STP":
                    slippage_this_order = stop_price - fill_price
                else:
                    continue

                # Aggregate data for the interval
                interval_data[interval_key]['total_slippage'] += slippage_this_order
                interval_data[interval_key]['trade_count'] += 1

            except ValueError as e:
                print(f"Warning [File: {filename}, Line: {line_num}]: Could not parse prices - Error: {e}")
            except Exception as e:
                print(f"Warning [File: {filename}, Line: {line_num}]: Error processing line - Error: {e}")

    # Sort by time interval
    sorted_interval_data = dict(sorted(interval_data.items()))
    return sorted_interval_data

def main():
    # --- Overall Aggregation Variables ---
    overall_interval_data = collections.defaultdict(lambda: {'total_slippage': 0.0, 'trade_count': 0})
    grand_total_slippage = 0.0
    grand_total_orders = 0
    processed_files_count = 0
    # ------------------------------------

    config = Config()
    matching_file_paths = file_utils.get_all_matching_files(config.directory_path, CONST.LOG_FILENAME_PATTERN)
    for logfile_path in matching_file_paths:
        print(f">>> Processing file: {logfile_path}")
        try:
            with open(logfile_path, 'r') as f:
                log_content = f.read()

            interval_results = analyze_slippage_by_interval(log_content, logfile_path)

            if interval_results:
                processed_files_count += 1
                file_total_slippage = 0.0
                file_trade_count = 0

                for interval, data in interval_results.items():
                    count = data['trade_count']
                    total_slip = data['total_slippage']
                    avg_slip = total_slip / count if count > 0 else 0.0
                
                    # Aggregate for overall summary
                    overall_interval_data[interval]['total_slippage'] += total_slip
                    overall_interval_data[interval]['trade_count'] += count
                    file_total_slippage += total_slip
                    file_trade_count += count

                grand_total_slippage += file_total_slippage
                grand_total_orders += file_trade_count
            else:
                print(f"No filled Stop (STP) orders found or processed in {logfile_path}.")

        except FileNotFoundError:
            print(f"Error: Log file not found at {logfile_path}. Skipping.")
        except Exception as e:
            print(f"An unexpected error occurred while processing {logfile_path}: {e}. Skipping.")

    # --- Print Overall Aggregated Results ---
    print(f"\n=== Overall Aggregated Slippage Analysis Across {processed_files_count} File(s) ===")
    if grand_total_orders > 0:
        print("-" * 65)
        print(f"{'Interval':<10} | {'Total Trades':<12} | {'Total Slippage (pts)':<20} | {'Avg Slippage/Trade (pts)':<20}")
        print("-" * 65)
        sorted_overall_intervals = dict(sorted(overall_interval_data.items()))
        for interval, data in sorted_overall_intervals.items():
                count = data['trade_count']
                total_slip = data['total_slippage']
                avg_slip = total_slip / count if count > 0 else 0.0
                print(f"{interval:<10} | {count:<12} | {total_slip:<20.2f} | {avg_slip:<20.3f}")

        print("-" * 65)
        print("\n--- Grand Total Summary ---")
        print(f"Analyzed {grand_total_orders} filled Stop (STP) orders across all processed files.")
        print(f"Total Slippage: {grand_total_slippage:.2f} points")
        print(f"Estimated Total Slippage Cost (ESM5 @ $50/pt): ${grand_total_slippage * 50.0:.2f}")
        print(f"Overall Average Slippage per Stop Order: {grand_total_slippage / grand_total_orders:.3f} points")
        print("---------------------------")
        print("\nNote: Positive slippage indicates unfavorable fills.")
    else:
        print("No STP orders processed across any files.")
    # -----------------------------------------

if __name__ == "__main__":
    main()