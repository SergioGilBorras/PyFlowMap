def clip_range(value, lower, upper):
    if not lower <= value <= upper:
        if value < lower:
            return lower
        elif value > upper:
            return upper
        raise ValueError('incomparable')
    return value
