class DataLoader:
    def load(self):
        return [1, 2, 3]


class Preprocessor:
    def clean(self, data):
        return [value for value in data if value is not None]


class Predictor:
    def predict(self, data):
        return data[0]


class Repository:
    def save(self, result):
        print(result)


def validate(data):
    return bool(data)


def main():
    loader = DataLoader()
    data = loader.load()
    processor = Preprocessor()
    data = processor.clean(data)
    if validate(data):
        model = Predictor()
        result = model.predict(data)
        Repository().save(result)
    else:
        print('invalid')
