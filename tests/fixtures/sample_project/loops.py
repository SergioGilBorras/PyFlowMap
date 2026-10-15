def process(row):
    return row


def finish():
    return None


def run(rows):
    for row in rows:
        process(row)
    finish()
