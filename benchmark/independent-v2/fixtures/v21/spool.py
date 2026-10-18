def drain(queue, device):
    sent = 0
    for job in queue:
        try:
            if not job.ready:
                continue
            if job.cancelled:
                break
            device.print(job)
        except OSError:
            device.reset()
        else:
            sent += 1
        finally:
            device.poll()
    else:
        return sent
    return -sent
