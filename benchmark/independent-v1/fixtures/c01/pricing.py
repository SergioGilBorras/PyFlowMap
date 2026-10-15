def compute_offer(subtotal, member, coupon):
    if subtotal < 0:
        raise ValueError('negative')
    if subtotal == 0:
        return {'amount': 0, 'tag': 'empty'}
    discount = 0
    if member and coupon:
        discount = 12
    elif member or coupon:
        discount = 6
    amount = subtotal - discount if subtotal > discount else 0
    return {'amount': amount, 'tag': 'ready'}
