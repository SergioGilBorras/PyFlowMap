def evaluate(tree, mapper):
    visits = 0
    def term(node):
        nonlocal visits
        visits += 1
        if isinstance(node, tuple):
            return combine(node)
        return mapper(node)
    def combine(nodes):
        if not nodes:
            return 0
        return term(nodes[0]) + combine(nodes[1:])
    return term(tree), visits
