from worker import fetch, persist


def orchestrate():
    result = fetch()
    persist(result)
