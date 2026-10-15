class Stock:
    amount: int

class Receipt:
    pass

class Checkout:
    def reserve(self, stock: Stock) -> Receipt:
        return Receipt()
