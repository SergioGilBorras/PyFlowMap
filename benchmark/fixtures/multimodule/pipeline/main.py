"""Modular package: static imports and calls across files."""

from .parse import decode
from .validate import verify


def start(raw):
    data = decode(raw)  # BENCH:critical
    if verify(data):  # BENCH:critical
        return 'valid'
    return 'invalid'
