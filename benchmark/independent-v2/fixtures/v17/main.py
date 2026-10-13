from components.api import prepare as normalize
from components.dispatch import Worker
def process_message(message):
    try:
        item = normalize(message)
    except ValueError:
        return None
    return Worker().submit(item)
