def main(values):
    total = 0
    for item in values:
        if item < 0:
            continue
        if item == 0:
            break
        total += item
    return total
