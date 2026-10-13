def dispatch_action(handler, action, payload):
    method = getattr(handler, action, None)
    if method is None:
        return {'error': 'unknown'}
    try:
        return method(payload)
    except ValueError:
        return {'error': 'bad payload'}
