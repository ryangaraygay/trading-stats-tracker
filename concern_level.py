from enum import IntEnum

class ConcernLevel(IntEnum):
    """Represents different levels of concern with inherent ordering and color mapping."""
    OK = 1
    DEFAULT = 2
    CAUTION = 3
    WARNING = 4
    CRITICAL = 5

    def get_color(self) -> str:
        """
        Returns a color string corresponding to the current ConcernLevel.

        Returns:
            A string representing the color.
        """
        if self == ConcernLevel.CRITICAL:
            return "red"
        elif self == ConcernLevel.WARNING:
            return "orange"
        elif self == ConcernLevel.CAUTION:
            return "yellow"
        elif self == ConcernLevel.OK:
            return "#90EE90"
        else:
            return "white"