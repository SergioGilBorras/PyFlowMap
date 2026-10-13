def validate_bounds(sample, reporter):
    assert sample is not None, reporter.describe("missing")
    assert sample.quality() > 0, reporter.describe("low quality")
    if not sample.active:
        raise LookupError("inactive")
    return sample.measure()
