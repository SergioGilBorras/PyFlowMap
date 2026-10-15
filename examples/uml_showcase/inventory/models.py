"""Simple source-declared classes and generalization."""

class Item:
    sku: str

    def __init__(self, sku: str):
        self.sku = sku

    def available(self) -> bool:
        return True


class PhysicalItem(Item):
    stock: int

    def __init__(self, sku: str, stock: int):
        super().__init__(sku)
        self.stock = stock

    def available(self) -> bool:
        return self.stock > 0
