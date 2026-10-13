def emit(code):
    return code

def interpret(packet):
    match packet:
        case {'kind': 'point', 'xy': [x, y]} if x >= 0 and y >= 0:
            return emit(('north_east', x, y))
        case {'kind': 'point', 'xy': [x, y]}:
            return emit(('other_quadrant', x, y))
        case {'kind': 'stop'}:
            return emit('halt')
        case _:
            return emit('unreadable')
