
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
