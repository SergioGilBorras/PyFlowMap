"""Authorization domain: denial, raising, finally audit and early return."""


def record_decision(subject):
    return subject


def check_permission(subject, resource):
    if subject is None:
        raise PermissionError('missing subject')
    try:
        if resource.startswith('private'):
            raise PermissionError('denied')
        return True
    finally:
        record_decision(subject)  # BENCH:critical
