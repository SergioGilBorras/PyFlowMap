def step(sensor, authorization, actuator):
    if sensor.ready() and authorization.check() and actuator.arm():
        return actuator.move()
    if sensor.failed() or actuator.reset():
        return 'degraded'
    return 'standby' if authorization.check() else 'locked'
