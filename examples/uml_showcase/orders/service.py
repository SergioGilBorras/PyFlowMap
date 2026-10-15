"""An example package depending on inventory."""

from inventory.models import PhysicalItem


class OrderService:
    def reserve(self, item: PhysicalItem) -> bool:
        if item.available():
            return True
        return False
