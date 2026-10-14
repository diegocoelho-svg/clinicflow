from collections.abc import Iterator

import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def clear_throttle_cache() -> Iterator[None]:
    cache.clear()
    yield
    cache.clear()
