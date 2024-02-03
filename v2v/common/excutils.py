import contextlib
import logging
import sys
import traceback


@contextlib.contextmanager
def save_and_reraise_exception():
    """Save current exception, run some code and then re-raise."""
    type_, value, tb = sys.exc_info()
    try:
        yield
    except Exception:
        logging.error('Original exception being dropped: %s' %
                      (traceback.format_exception(type_, value, tb)))
        raise
