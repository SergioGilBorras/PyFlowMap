def flush_messages(groups, consumer, audit):
    count = 0
    try:
        for group in groups:
            for msg in group:
                if msg is None:
                    continue
                if not consumer(msg):
                    break
                count += 1
            else:
                continue
            break
        else:
            return ('all', count)
        return ('partial', count)
    finally:
        audit(count)
