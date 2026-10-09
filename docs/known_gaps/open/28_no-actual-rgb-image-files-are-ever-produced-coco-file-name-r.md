### [DEFERRED] No actual RGB image files are ever produced -- COCO `file_name` references a file that doesn't exist on disk
Found via a real dogfooding pass (generating a genuine dataset with
`bin/generate_dataset.py` and inspecting the output, not just reading
code): `annotations.json`'s `images[].file_name` field (e.g.
`"proc_scenario_0000.png"`) never corresponds to an actual file anywhere
in `output_dir` -- only `annotations.json` and per-scenario
`*_metadata.json` files are written. This is not a bug (there is no
rendering engine anywhere in this pipeline to produce an actual image
from -- a real UE5.4 install now exists and the plugin compiles/loads
(see the resolved UE5 entries elsewhere in this file), but nothing in
`generate_dataset`'s own call path invokes `UE5Backend`/UE5 at all, and
the UE5-side WebSocket JSON-RPC server needed to receive a real render
request doesn't exist yet either), but it was not previously stated
anywhere a user would see it before hitting it themselves. A caller
expecting a real image-plus-annotations COCO dataset (e.g. to train a
model, or to visually spot-check output) needs to know this up front,
not discover it by a missing-file surprise.
**Action**: documented explicitly in `docs/user_guide.rst`'s CLI section
and this entry; revisit once the UE5-side WebSocket bridge exists and
`generate_dataset` actually calls it to render a frame.

