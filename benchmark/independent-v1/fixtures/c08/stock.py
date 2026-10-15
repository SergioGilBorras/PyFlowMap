def reconcile(current, update, audit):
    try:
        value = update(current)
    except LookupError:
        audit('missing')
        return None
    except Exception as exc:
        audit(type(exc).__name__)
        raise
    else:
        return value
    finally:
        audit('finished')
