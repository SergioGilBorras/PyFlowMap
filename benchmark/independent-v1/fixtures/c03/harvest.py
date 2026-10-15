def allocate(baskets, capacity):
    accepted = []
    for basket in baskets:
        if not basket:
            continue
        if len(accepted) >= capacity:
            break
        accepted.append(basket)
    else:
        accepted.append('complete')
    return accepted
