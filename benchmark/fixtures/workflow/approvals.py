"""HR workflow domain: multiple decision branches and statuses."""


def save_request(request):
    return True


def queue_review(request):
    return True


def approve(request):
    return True


def process_leave(request):
    if request.days <= 0:
        return 'invalid'
    save_request(request)  # BENCH:critical
    if request.days > 10:
        queue_review(request)  # BENCH:critical
        return 'pending'
    approve(request)  # BENCH:critical
    return 'approved'
