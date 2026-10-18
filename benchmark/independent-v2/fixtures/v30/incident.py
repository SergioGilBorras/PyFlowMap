def resolve(code, reporter, release):
    try:
        match code:
            case 0:
                return "ok"
            case 1 | 2:
                raise ValueError("temporary")
            case _:
                return "unknown"
    except ValueError as exc:
        reporter.warn(exc)
        return "retry"
    finally:
        release()
