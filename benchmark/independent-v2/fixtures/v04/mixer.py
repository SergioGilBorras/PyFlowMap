def render_sample(source, meter):
    try:
        frame = source.read()
        if frame is None:
            return "silence"
        try:
            return meter.normalize(frame)
        finally:
            meter.record(frame)
    finally:
        source.release()
