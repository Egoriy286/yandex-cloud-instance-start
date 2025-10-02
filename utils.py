from dateutil import parser

def iso_to_unix(iso_string: str) -> int:
    """
    Convert an ISO 8601 datetime string to a Unix timestamp.
    
    Args:
        iso_string (str): ISO 8601 formatted date-time string.
    
    Returns:
        int: Unix timestamp (seconds since epoch).
    """
    dt = parser.isoparse(iso_string)
    return int(dt.timestamp())

# Example usage
iso_string = "2021-12-25T12:34:56+00:00"
timestamp = iso_to_unix(iso_string)
#print(timestamp)  # Output: 1640434496
