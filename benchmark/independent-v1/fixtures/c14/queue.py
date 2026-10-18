def iterate_tracks(tracks, include_bonus):
    for track in tracks:
        if not track:
            continue
        yield track
    if include_bonus:
        yield from ('encore', 'outro')
    return 'finished'
