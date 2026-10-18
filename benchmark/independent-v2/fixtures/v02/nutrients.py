def select_formula(records, threshold):
    selected = []
    for record in records:
        try:
            value = float(record["value"])
        except (KeyError, ValueError):
            continue
        if value < 0:
            break
        if value >= threshold:
            selected.append(value)
    else:
        return sum(selected) / len(selected) if selected else 0
    return None
