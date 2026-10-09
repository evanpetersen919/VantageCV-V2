### [RESOLVED] `default_overview_camera` framed scenarios poorly, leaving most of the image empty
Found via the same dogfooding pass as the entry above: since no
rendering engine exists to eyeball an actual rendered frame against, a
top-down 2D plot of a real generated scenario was compared side-by-side
against `default_overview_camera`'s own projected 2D annotation boxes
for that same scenario. The projected content filled only ~55% of the
image's width and left large empty margins on most sides -- a real,
visually obvious framing problem that no existing test caught (every
existing test only checked that *some* boxes projected successfully,
never how much of the frame they used).

Root cause: the camera's offset (`extent * 0.3`) and height
(`extent * 0.6`) ratios positioned it too far back and too high above
the scenario, at too shallow a viewing angle, for its 90-degree
horizontal FOV to fill the frame with actual scene content. Resolved by
retuning both ratios (`0.3` → `0.05`, `0.6` → `0.35`), found by
iterating side-by-side against the same visual comparison until content
filled a healthy majority of the frame, verified to lose no meaningful
number of visible annotations (506 → 489 boxes visible, ~3%, from
perspective changes at the new vantage, not clipping). A regression test
(`test_default_overview_camera_fills_a_reasonable_fraction_of_the_frame`)
now asserts the union of projected 2D boxes spans a healthy majority of
the image in both axes, so this can't silently regress again.

