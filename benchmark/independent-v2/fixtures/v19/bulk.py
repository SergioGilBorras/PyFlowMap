def verify_all(tasks, logger):
    passed = []
    try:
        for task in tasks:
            passed.append(task.verify())
    except* ValueError as failures:
        logger.bad_data(failures)
    except* OSError as failures:
        logger.io_error(failures)
    finally:
        logger.finished()
    return passed
