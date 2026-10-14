"""Generic source for Phase 4.1 evaluator mutations."""


def consume(value):
    return value


def reject():
    return False


def finish():
    return True


async def operation():
    return None


def dispatch(value):
    match value:
        case ("item", captured) if captured:
            consume(captured)
        case False:
            reject()
    return finish()


def single_return(value):
    if value:
        return 17
    return 23


class MultiRouteExit:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is not None:
            return False
        return False


def use_context(flag):
    with MultiRouteExit():
        if flag:
            return "done"
        raise ValueError("failure")


async def use_async_context(manager):
    async with manager:
        await operation()


def literal_values(kind):
    if kind == 0:
        return b"payload"
    if kind == 1:
        return {1, 2}
    return 3j
