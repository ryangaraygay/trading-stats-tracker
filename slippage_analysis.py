import re
import argparse
import collections

def analyze_slippage(log_content):
    """
    Analyzes trading log content to calculate total and separate slippage for STP orders.

    Args:
        log_content (str): A string containing the entire log file content.

    Returns:
        dict: A dictionary containing slippage analysis results:
              {'total_slippage_points': float, 'total_stop_orders': int,
               'buy_slippage_points': float, 'buy_stop_orders': int,
               'sell_slippage_points': float, 'sell_stop_orders': int}
               Returns dict with zeros if no STP orders found or in case of errors.
    """
    results = collections.defaultdict(float)
    results['total_stop_orders'] = 0
    results['buy_stop_orders'] = 0
    results['sell_stop_orders'] = 0


    # Regex to find filled STP order lines and capture relevant parts
    # Groups: 1=Order Type (BUY STP/SELL STP), 2=Aux Price, 3=Fill Price
    order_fill_regex = re.compile(
        r"OrderDirectory::orderFilled\(\).*?\s(BUY STP|SELL STP)\s.*?Aux:(\d+\.?\d*).*?fill price:\s(\d+\.?\d*)"
    )

    for line in log_content.splitlines():
        match = order_fill_regex.search(line)
        if match:
            try:
                order_type = match.group(1)
                stop_price = float(match.group(2))
                fill_price = float(match.group(3))
                slippage_this_order = 0.0

                results['total_stop_orders'] += 1

                if order_type == "BUY STP":
                    # Slippage = Fill Price - Stop Price
                    # Positive means unfavorable (paid more)
                    slippage_this_order = fill_price - stop_price
                    results['buy_slippage_points'] += slippage_this_order
                    results['buy_stop_orders'] += 1
                elif order_type == "SELL STP":
                    # Slippage = Stop Price - Fill Price
                    # Positive means unfavorable (received less)
                    slippage_this_order = stop_price - fill_price
                    results['sell_slippage_points'] += slippage_this_order
                    results['sell_stop_orders'] += 1
                else:
                    continue # Should not happen

                results['total_slippage_points'] += slippage_this_order

                # Optional: Print details for each order
                # print(f"Found {order_type}: Stop={stop_price}, Fill={fill_price}, Slippage={slippage_this_order:.2f} points")

            except ValueError as e:
                print(f"Warning: Could not parse prices in line: {line} - Error: {e}")
            except Exception as e:
                print(f"Warning: Error processing line: {line} - Error: {e}")

    # Convert defaultdict back to regular dict for clarity
    return dict(results)

def main():
    filepath = ""

    try:
        with open(filepath, 'r') as f:
            log_content = f.read()

        results = analyze_slippage(log_content)
        total_slippage = results['total_slippage_points']
        total_count = results['total_stop_orders']
        buy_slippage = results['buy_slippage_points']
        buy_count = results['buy_stop_orders']
        sell_slippage = results['sell_slippage_points']
        sell_count = results['sell_stop_orders']


        if total_count > 0:
            print(f"\n--- Slippage Analysis Results ---")
            print(f"Analyzed {total_count} filled Stop (STP) orders.")

            print("\n--- Overall ---")
            print(f"Total Slippage: {total_slippage:.2f} points")
            # Assuming ES contract where 1 point = $50
            print(f"Estimated Total Slippage Cost (ESM5 @ $50/pt): ${total_slippage * 50.0:.2f}")
            print(f"Average Slippage per Stop Order: {total_slippage / total_count:.3f} points")

            if buy_count > 0:
                print(f"\n--- BUY Stops ({buy_count} orders) ---")
                print(f"Total BUY Slippage: {buy_slippage:.2f} points")
                print(f"Estimated BUY Slippage Cost: ${buy_slippage * 50.0:.2f}")
                print(f"Average BUY Slippage per Order: {buy_slippage / buy_count:.3f} points")
            else:
                print("\n--- BUY Stops (0 orders) ---")


            if sell_count > 0:
                print(f"\n--- SELL Stops ({sell_count} orders) ---")
                print(f"Total SELL Slippage: {sell_slippage:.2f} points")
                print(f"Estimated SELL Slippage Cost: ${sell_slippage * 50.0:.2f}")
                print(f"Average SELL Slippage per Order: {sell_slippage / sell_count:.3f} points")
            else:
                 print("\n--- SELL Stops (0 orders) ---")

            print("---------------------------------")
            print("\nNote: Positive slippage indicates unfavorable fills ")
            print("(paying more for BUY STPs, receiving less for SELL STPs).")
        else:
            print(f"No filled Stop (STP) orders found in {filepath}.")

    except FileNotFoundError:
        print(f"Error: Log file not found at {filepath}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
