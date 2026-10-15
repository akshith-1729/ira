"""In-process cache for venue lookups. External paid APIs are not called."""

from __future__ import annotations

from typing import Callable, TypeVar

T = TypeVar("T")

# Clarivate JCR, Scopus, and Web of Science venue metrics need a paid key.
# Do not add clients for those here.
PAID_VENUE_APIS = ("clarivate-jcr", "scopus", "web-of-science")


class LookupCache:
    def __init__(self) -> None:
        self._data: dict[str, object] = {}

    def get_or_set(self, key: str, loader: Callable[[], T]) -> T:
        if key not in self._data:
            self._data[key] = loader()
        return self._data[key]  # type: ignore[return-value]

    def clear(self) -> None:
        self._data.clear()

    def __contains__(self, key: str) -> bool:
        return key in self._data


VENUE_LOOKUP_CACHE = LookupCache()
