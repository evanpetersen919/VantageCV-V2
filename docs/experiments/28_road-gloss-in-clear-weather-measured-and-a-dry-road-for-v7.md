## Road gloss in clear weather: measured, and a dry road for v7

The question left open by the generator audit: do roads look wet in clear weather? City Sample's
road material (`M_Asphalt_Master_Inst_ParkingLots`) has a glossy default. Six clear summer-day
scenes (seeds 45000-45005, same camera each time) were rendered under four road settings with
`bin/calibrate_night.py --base day`, and scored with a new statistic, `mirror_corr` in
`src/evaluation/image_stats.py`: the correlation, after removing each row's mean, between the road
band below the middle of the frame and the scene above it flipped (a wet road echoes what stands
over it). It is a rough proxy (it assumes the horizon is near the middle, which holds for the
renders, not for real frames), so means over many images are compared, not single frames.

| Road setting | mirror_corr |
|---|---|
| default (v6 and v7 up to the first batch) | 0.13 |
| roughness 0.9 | 0.07 |
| roughness 0.9, no puddles, specular 0.2 | 0.08 |
| roughness 1.0, specular 0.05 | 0.08 |
| real clear-day BDD100K frames (120 images) | 0.09 |

![The same three clear-day scenes under the four road settings: the default (left) has a wet-looking sheen near the crosswalk and on the left of the third scene; the three rougher settings do not](../images/road_settings_clear_day.jpg)

The default road has a localized sheen, not a mirror; the rougher settings remove it and land on the
real value. The v7 profile now uses the second setting (`_DRY_SURFACES`) for every scene that is
not raining, day and night; rain keeps its wet surfaces. The first v7 batch (`train_v7a`) was
rendered before this change, so it has the default road. Nothing has been trained on this change.

