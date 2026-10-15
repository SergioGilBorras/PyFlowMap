from helpers import offset as shift
from helpers import limit

def calibrate(values, threshold):
    total = 0
    for value in values:
        total += shift(value)
        if not limit(total, threshold):
            break
    return total
