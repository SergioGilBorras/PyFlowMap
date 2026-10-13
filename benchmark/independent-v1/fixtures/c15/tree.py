def aggregate(node, visited):
    if node is None:
        return 0
    if node.key in visited:
        raise RuntimeError('cycle')
    visited.add(node.key)
    try:
        subtotal = node.value
        for child in node.children:
            subtotal += aggregate(child, visited)
        return subtotal
    finally:
        visited.remove(node.key)
