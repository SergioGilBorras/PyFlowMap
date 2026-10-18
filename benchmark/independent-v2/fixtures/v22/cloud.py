def cluster(layers, threshold, compare):
    points = [compare(p) for layer in layers if layer for p in layer if p.valid]
    lookup = {p.id: p.value for p in points if p.value > threshold}
    deferred = (p.value for p in points if p.id not in lookup)
    return lookup, deferred
