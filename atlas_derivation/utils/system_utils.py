import numpy as np

def bytes_to_readable(size_in_bytes, digits=2):
    """
    Convert the number of bytes to a human-readable string format.

    Parameters:
    size_in_bytes (int): The size in bytes that you want to convert.
    digits (int, optional): The number of decimal places to format the output. Default is 2.

    Returns:
    str: A string representing the human-readable format of the size.

    Examples:
    >>> bytes_to_readable(123456789)
    '117.74 MB'

    >>> bytes_to_readable(9876543210)
    '9.20 GB'

    >>> bytes_to_readable(123456789, digits=4)
    '117.7383 MB'

    >>> bytes_to_readable(999, digits=1)
    '999.0 B'
    """
    for unit in ['B', 'kB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']:
        if abs(size_in_bytes) < 1024.0:
            return f"{size_in_bytes:.{digits}f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.{digits}f} YB"