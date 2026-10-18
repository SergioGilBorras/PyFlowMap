def publish(reader, writer, validate):
    with reader() as source:
        with writer() as target:
            data = source.read()
            if not validate(data):
                return False
            target.write(data)
            return True
