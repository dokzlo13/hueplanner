import shelve
import functools
from collections import OrderedDict
import os
import structlog

logger = structlog.getLogger(__name__)

class LRUCacheDecorator:
    def __init__(self, cache_size=5, cache_file="./.cache/cache.db"):
        self.cache_size = cache_size
        self.cache_dir, self.cache_file_name = os.path.split(cache_file)
        self.cache_file = cache_file
        self.access_order = OrderedDict()  # Keep track of item access order

        # Ensure cache directory exists
        if self.cache_dir and not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

    def __call__(self, func):
        @functools.wraps(func)
        def wrapped_func(*args, **kwargs):
            # Create a key from the function arguments
            key = str(func.__name__) + str(args) + str(kwargs)

            # Use shelve for disk-based cache
            with shelve.open(self.cache_file, writeback=True) as cache:
                # Check if result is cached and return it
                if key in cache:
                    logger.debug("Cache hit", key=key)
                    result = cache[key]
                    self.access_order[key] = None  # Update access order
                    return result

                # Call the function and cache the result
                result = func(*args, **kwargs)
                cache[key] = result
                self.access_order[key] = None  # Update access order

                # If cache exceeds size, remove the least recently used item
                if len(self.access_order) > self.cache_size:
                    oldest = next(iter(self.access_order))
                    del cache[oldest]
                    del self.access_order[oldest]

                return result

        return wrapped_func
