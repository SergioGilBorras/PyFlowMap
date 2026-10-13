"""General logic: short-circuit and/or and ternary with observable side effects."""


def audit_access(user):
    return bool(user)


def check_token(token):
    return token is not None


def count_attempt():
    return 1


def authorize(user, token):
    allowed = audit_access(user) and check_token(token)  # BENCH:critical
    fallback = count_attempt() if not allowed else 0  # BENCH:critical
    if allowed or fallback > 1:
        return True
    return False
