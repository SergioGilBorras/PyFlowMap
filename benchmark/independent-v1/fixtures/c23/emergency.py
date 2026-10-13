def shutdown(controller, manager):
    try:
        with manager() as ticket:
            if ticket.expired:
                raise TimeoutError('expired')
            controller.close()
            return 'closed'
    except TimeoutError:
        return 'retry'
