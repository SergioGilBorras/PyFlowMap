"""Standalone example: pyflowmap analyze examples/basic_pipeline.py --entry main."""


def load_data():
    return [1, 2, 3]


def normalize(data):
    return data


def train(data):
    return {"model": data}


def save(model):
    return model


def main():
    records = load_data()
    records = normalize(records)
    if records:
        model = train(records)
        save(model)
