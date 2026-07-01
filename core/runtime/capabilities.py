"""Runtime capability definitions."""

from __future__ import annotations

from enum import Enum, auto


class Capability(Enum):
    GRAPH_TRAVERSAL = auto()
    VECTOR_SEARCH = auto()
    METADATA_STORAGE = auto()
    PERSISTENT_STORAGE = auto()
    MULTI_PROJECT = auto()
    INCREMENTAL_INDEX = auto()
    REST_API = auto()
    WEBSOCKET = auto()
    CONCURRENT_USERS = auto()
    SHARED_INDEXES = auto()
    CONTEXT_GATEWAY = auto()
    REMOTE_INDEXING = auto()
    FLUTTER_CLIENT = auto()


SERVER_CAPABILITIES = {
    Capability.GRAPH_TRAVERSAL,
    Capability.VECTOR_SEARCH,
    Capability.METADATA_STORAGE,
    Capability.PERSISTENT_STORAGE,
    Capability.MULTI_PROJECT,
    Capability.INCREMENTAL_INDEX,
    Capability.REST_API,
    Capability.WEBSOCKET,
    Capability.CONCURRENT_USERS,
    Capability.SHARED_INDEXES,
    Capability.REMOTE_INDEXING,
    Capability.FLUTTER_CLIENT,
}


LOCAL_CAPABILITIES = {
    Capability.GRAPH_TRAVERSAL,
    Capability.VECTOR_SEARCH,
    Capability.METADATA_STORAGE,
    Capability.PERSISTENT_STORAGE,
    Capability.INCREMENTAL_INDEX,
}