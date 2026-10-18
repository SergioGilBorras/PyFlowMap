from factory_one.steps import apply as apply_one
from factory_two.steps import apply as apply_two
def run_build(record):
    value = apply_one(record)
    if value is None:
        return None
    return apply_two(value)
