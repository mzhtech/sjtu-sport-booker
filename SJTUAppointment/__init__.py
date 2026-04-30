"""Package exports for sjtu-sport-booker."""

from importlib import import_module

__all__ = ["sjtu-sport-booker"]


def __getattr__(name):
    if name == "sjtu-sport-booker":
        return import_module(".sjtu-sport-booker", __name__).sjtu-sport-booker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
