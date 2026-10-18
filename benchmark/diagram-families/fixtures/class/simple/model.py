class Item:
    id: int
    def price(self) -> float:
        return 1.0

class PhysicalItem(Item):
    location: str
