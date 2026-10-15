"""Commerce domain: conditional payment, inventory, and fulfilment."""


def reserve_item(sku, qty):
    return qty > 0


def charge_payment(total):
    return total > 0


def release_reservation(sku):
    return True


def ship_order(sku):
    return 'sent'


def checkout(sku, qty, total):
    if not reserve_item(sku, qty):  # BENCH:critical
        return 'out-of-stock'
    if not charge_payment(total):  # BENCH:critical
        release_reservation(sku)  # BENCH:critical
        return 'payment-declined'
    ship_order(sku)  # BENCH:critical
    return 'completed'
