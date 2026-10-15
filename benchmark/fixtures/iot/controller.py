"""Embedded/IoT domain: match-case state dispatch and early returns."""


def power_on():
    return 'on'


def cool_down():
    return 'cooling'


def power_off():
    return 'off'


def transition(state, temp):
    match state:
        case 'OFF':
            return power_on()  # BENCH:critical
        case 'ON' if temp > 90:
            return cool_down()  # BENCH:critical
        case 'ON':
            return 'steady'
        case _:
            return power_off()  # BENCH:critical
