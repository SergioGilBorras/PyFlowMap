def choose(cache, fetcher, key):
    if (cached := cache.get(key)) is not None:
        return cached
    return fetcher.load(key) if fetcher.available(key) else (cache.fallback(key) or None)
