def get_data():
    return 1


def transform(data):
    return data


def save(data):
    return data


def task(enabled):
    data = get_data()
    if enabled:
        data = transform(data)
    save(data)
