def move_train(stations, blocked):
    at = 0
    while at < len(stations):
        for name in blocked:
            if name == stations[at]:
                break
        else:
            at += 1
            continue
        if at == 0:
            return "held"
        break
    else:
        return "arrived"
    return "diverted"
