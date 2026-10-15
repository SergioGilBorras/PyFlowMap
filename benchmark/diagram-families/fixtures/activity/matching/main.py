def main(event):
    match event:
        case {"kind": "add", "amount": amount} if amount > 0:
            return amount
        case {"kind": "delete"}:
            return -1
        case _:
            return 0
