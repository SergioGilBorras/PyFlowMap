def extract(payload, validate):
    try:
        first, *middle, last = payload
        if not validate(first, last):
            raise ValueError("invalid")
        return middle
    except (TypeError, ValueError) as error:
        raise RuntimeError("rejected") from error
