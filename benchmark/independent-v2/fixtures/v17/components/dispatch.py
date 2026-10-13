class Worker:
    def submit(self, item):
        if not item:
            return False
        return enqueue(item)
