def parse_item(record):
    assert isinstance(record, dict)
    if (title := record.get('title')) is None:
        raise KeyError('title')
    if (year := record.get('year')) and year < 1500:
        return ('old', title)
    return ('new', title, year)
