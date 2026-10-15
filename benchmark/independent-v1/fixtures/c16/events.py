def handle_event(event, log):
    match event:
        case ('click', target):
            match target:
                case {'type': 'button', 'enabled': True, 'id': identifier}:
                    log.append(identifier)
                    return 'clicked'
                case {'type': 'button'}:
                    return 'disabled'
                case _:
                    return 'ignored'
        case ('move', x, y) if x > 0:
            return ('moved', x, y)
        case _:
            return 'other'
