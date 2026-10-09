### [RISK] `pkg_resources` (needed by Ray, via the pinned `setuptools<81`) is slated for removal by setuptools upstream
The fix above pins `setuptools<81` specifically to keep `pkg_resources`
importable, because `ray` 2.9.3's `ray/_private/pydantic_compat.py` does
`from pkg_resources import packaging` unconditionally whenever a remote
task is first submitted. `pkg_resources` itself now warns on import:
"slated for removal as early as 2025-11-30." When that happens, this
pin will stop being satisfiable (or satisfiable only with an
increasingly ancient setuptools), and every `ray.remote(...).remote()`
call in this codebase will break again the same way.
**Action**: watch for a `ray` release that no longer imports
`pkg_resources` (newer Ray versions past 2.9.3 likely already fixed
this internally) and upgrade `ray` + drop the `setuptools<81` pin
together, rather than pinning setuptools indefinitely.

