def traced(func):
    def wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        finally:
            log_event(func.__name__)
    return wrapped

def log_event(message):
    pass

@traced
def transfer(balance, amount):
    if amount <= 0:
        raise ValueError('amount')
    if amount > balance:
        return ('denied', balance)
    return ('done', balance - amount)
