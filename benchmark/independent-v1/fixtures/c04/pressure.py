def stabilize(readings, maximum):
    position = 0
    adjustment = 0
    while position < len(readings):
        reading = readings[position]
        position += 1
        if reading is None:
            continue
        if reading > maximum:
            adjustment += 1
            break
        adjustment -= 1
    else:
        adjustment = 0
    return adjustment
