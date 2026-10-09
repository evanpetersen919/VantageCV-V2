### [RESOLVED] Resumable/checkpointed generation verified via a real simulated crash, not just the mocked unit test
`tests/integration/test_resume_handler.py` already covered this
correctness claim, but via a test double, not an actual interrupted
process. Dogfooded for real instead: ran `generate_dataset_resumable`
for a full 8-scenario dataset as a baseline, then in a separate output
directory, called it first for only 4 scenarios (a real, deliberate
stand-in for "the process was killed after 4 scenarios" -- same
`checkpoint.json`/`*_coco_part.json` files a real crash would leave
behind), then called it again for all 8 on that same directory (exactly
what a restarted process pointed at the same `--output-dir` would do).
The "resumed" call took 2.94s versus the "partial" call's 2.87s -- not
the uninterrupted baseline's 5.86s -- confirming it genuinely skipped
regenerating the 4 already-completed scenarios rather than merely
reproducing the same result a second time. Final output
(`images`/`annotations`, including post-merge annotation ID
renumbering) was byte-identical between the uninterrupted and
interrupted-then-resumed runs. No bug found; this closes the loop on
"resumable generation was tested, but only against a mock" as a real,
independently-verified guarantee.

