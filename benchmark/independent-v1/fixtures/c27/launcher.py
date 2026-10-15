from package.pipeline import run as execute
from package.validators import check

def launch(raw):
    if not check(raw):
        return {'status': 'invalid'}
    output = execute(raw)
    return {'status': 'ok', 'value': output}
