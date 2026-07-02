from collections.abc import Callable
from importlib import import_module
from importlib.metadata import entry_points
from types import ModuleType

from obrist.dsl import BenchmarkCollection

CollectionFactory = Callable[[], BenchmarkCollection]
"""Callable that returns a fully constructed benchmark collection."""

_COLLECTIONS: dict[str, CollectionFactory] = {}


def register(name: str, factory: CollectionFactory) -> None:
    """Register an in-process benchmark collection factory."""

    _COLLECTIONS[name] = factory


def load_collection(name: str) -> BenchmarkCollection:
    """Load a benchmark collection by registry name, entry point, or import fallback."""

    if name in _COLLECTIONS:
        return _load_from_factory(name, _COLLECTIONS[name])

    for entry_point in entry_points(group="obrist.collections"):
        if entry_point.name == name:
            factory = entry_point.load()
            if not callable(factory):
                raise TypeError(f"Entry point {name!r} did not resolve to a collection factory")
            return _load_from_factory(name, factory)

    module = _import_collection_module(name)
    get_collection = module.get_collection
    if not callable(get_collection):
        raise TypeError(f"{name}.collections.get_collection is not callable")
    return _load_from_factory(name, get_collection)


def _load_from_factory(name: str, factory: CollectionFactory) -> BenchmarkCollection:
    collection = factory()
    if not isinstance(collection, BenchmarkCollection):
        raise TypeError(f"Collection factory {name!r} did not return BenchmarkCollection")
    return collection


def _import_collection_module(name: str) -> ModuleType:
    """Import a collection module from a direct package or the datasets namespace."""

    direct_module_name = f"{name}.collections"
    try:
        return import_module(direct_module_name)
    except ModuleNotFoundError as error:
        if error.name != name:
            raise

    return import_module(f"datasets.{name}.collections")
