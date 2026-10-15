def route_request(message, registry):
    match message:
        case {"op": "borrow", "book": str(title) as text, **extras} if title and not extras.get("closed"):
            return registry.borrow(text)
        case {"op": "return", "book": title}:
            return registry.put_back(title)
        case ["find", *terms] if terms:
            return registry.search(terms)
        case _:
            return {"ok": False}
