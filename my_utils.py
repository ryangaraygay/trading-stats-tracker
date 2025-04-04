from datetime import timedelta, datetime
from constants import CONST

def find_key_with_lowest_order_id(data):
    """
    Finds the key in a defaultdict(list) that contains the Trade object with the
    lowest order_id among all Trade objects in all lists.

    Args:
        data: The defaultdict(list) where values are lists of Trade objects.

    Returns:
        The key with the lowest order_id, or None if the defaultdict is empty.
    """
    lowest_order_id = float('inf')  # Initialize with positive infinity
    key_with_lowest = None

    for key, trades in data.items():
        for trade in trades:
            number_only_order_id = int(re.sub(r"[^0-9]", "", trade.order_id))
            if number_only_order_id < lowest_order_id:
            # if trade.order_id < lowest_order_id:
                lowest_order_id = number_only_order_id
                key_with_lowest = key

    return key_with_lowest

def filter_namedtuples(list_of_namedtuples, attribute_name, target_value):
    """
    Filters a list of namedtuples based on the value of a specific attribute.

    Args:
    list_of_namedtuples: A list of namedtuples.
    attribute_name: The name of the attribute to filter by (as a string).
    target_value: The value to filter for.

    Returns:
    A new list containing only the namedtuples where the specified
    attribute's value matches the target_value.
    """
    filtered_list = [
        item
        for item in list_of_namedtuples
        if getattr(item, attribute_name) == target_value
    ]
    return filtered_list

def average_timedelta(timedelta_list):
    """Calculates the average of a list of timedelta objects using lambda."""

    if not timedelta_list:
        return timedelta(0)  # Return 0 if the list is empty

    total_seconds = sum(map(lambda td: td.total_seconds(), timedelta_list))
    average_seconds = total_seconds / len(timedelta_list)
    return timedelta(seconds=average_seconds)

def max_timedelta(timedelta_list):
    """Calculates the maximum timedelta from a list."""
    if not timedelta_list:
        return timedelta(0) #return 0 if empty

    return max(timedelta_list)

def format_timedelta(timedelta_obj):
    """
    Formats a timedelta object into mm:ss format.

    Args:
        timedelta_obj: A timedelta object.

    Returns:
        A string representing the duration in mm:SS format, or "00:00" if the timedelta is None.
    """
    if timedelta_obj is None:
        return "00:00"

    total_seconds = int(timedelta_obj.total_seconds())
    minutes = total_seconds // 60
    seconds = (total_seconds % 60) // 60
    return f"{minutes:02d}:{seconds:02d}"

def calculate_mins(open_entry_time_str, reference_time):
    if not open_entry_time_str:
        return 0
    try:
        open_entry_time = datetime.strptime(open_entry_time_str, CONST.DAY_TIME_FORMAT)
        current_year = reference_time.year
        open_entry_time = open_entry_time.replace(year=current_year)
        time_difference = reference_time - open_entry_time
        minutes = int(time_difference.total_seconds() / 60)
        return minutes
    except ValueError as e:
        print(e)
        return 0
