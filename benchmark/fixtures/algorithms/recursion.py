"""Algorithm domain: recursion, base case, bounded expansion and nested calls."""


def transform(value):
    return value * 2


def walk_tree(node):
    if node is None:
        return 0
    if not node.children:
        return transform(node.value)  # BENCH:critical
    total = 0
    for child in node.children:
        total += walk_tree(child)  # BENCH:critical
    return total
