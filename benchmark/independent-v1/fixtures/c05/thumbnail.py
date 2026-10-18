def make_preview(source, renderer, log):
    log.append('start')
    try:
        if not source:
            return 'missing'
        result = renderer(source)
        if result is None:
            return 'unsupported'
        return result
    finally:
        log.append('closed')
