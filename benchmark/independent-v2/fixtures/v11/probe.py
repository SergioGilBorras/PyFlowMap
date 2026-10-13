def activate(registry, factory, label):
    endpoint = registry.lookup(factory(label).identifier())
    if endpoint is None:
        return False
    return endpoint.start(retries=registry.count(label))
