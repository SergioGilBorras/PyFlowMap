def main(balance: int, limit: int) -> str:
    if balance >= limit:
        return "over"
    return "within"
