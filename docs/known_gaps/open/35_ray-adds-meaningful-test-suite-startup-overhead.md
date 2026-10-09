### [RISK] Ray adds meaningful test-suite startup overhead
Adding `ray` as a dependency increased the full test suite's wall-clock
time noticeably (roughly 50s to 80s) even though only a handful of tests
actually use it -- `ray.init()`'s worker-process startup cost is paid at
least once per test session. Not a correctness issue, but worth knowing
if test suite speed becomes a concern; consolidating Ray-dependent tests
to share one `ray.init()` call (e.g. via a session-scoped fixture) would
likely help if this grows further.

