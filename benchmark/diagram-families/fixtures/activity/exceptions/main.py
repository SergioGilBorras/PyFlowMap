def main(source):
    try:
        result = source.read()
    except OSError:
        return None
    finally:
        source.close()
    return result
