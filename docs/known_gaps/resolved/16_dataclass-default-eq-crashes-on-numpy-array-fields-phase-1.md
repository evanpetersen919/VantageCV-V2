### [RESOLVED] Dataclass default `__eq__` crashes on numpy-array fields — Phase 1
Confirmed by direct test: a `@dataclass` with a `numpy.ndarray` field raises
`ValueError: The truth value of an array with more than one element is
ambiguous` on `==` comparison, because the generated `__eq__` chains
per-field `==` with `and`. The master prompt's `RoadNode`/`RoadEdge`
dataclasses have `position`/`centerline` ndarray fields and a custom
`__hash__`, but don't disable the default `__eq__` — meaning any code path
that compares two instances (e.g. `in` on a list, or an assertion) would
crash. Fixed by declaring both `@dataclass(eq=False)`; identity is via
`node_id`/`edge_id` through the manual `__hash__` only, and no code path
needs value-equality on these objects.

