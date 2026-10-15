"""An example activity entry with explicit cross-package dependencies."""

from inventory.models import PhysicalItem
from orders.service import OrderService


class Dashboard:
    def summarize(self, item: PhysicalItem) -> str:
        if item.available():
            return "Ready"
        return "Out of stock"


def main(stock: int = 3) -> str:
    item = PhysicalItem("SKU-001", stock)
    order = OrderService()
    if order.reserve(item):
        return Dashboard().summarize(item)
    return "Pending"
