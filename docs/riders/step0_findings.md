# Riders and two-wheelers: step 0 findings

Date: 2026-10-09. Scope: what the Rocketbox avatars give us for riders, which real models the bikes will be modelled on,
and what is not known yet. Nothing here is built; step 1 (measure BDD100K rider statistics and pre-register the
evaluation) and step 2 (a bicycle spike) come next.

How to read the evidence tags: **measured** = produced by a script in this repository on this machine;
**published** = a number from a manufacturer or standards page that an agent opened or read in search results, with its
URL; **secondhand** = from an aggregator or retailer listing or a search summary that was not checked against the
manufacturer; **derived** = our own arithmetic from the above. Anything else is listed as *not published*.

## 1. Rocketbox avatars (measured)

Reproduce with `blender -b -P scripts/rocketbox_measure.py -- external_data/rocketbox OUT.json`; the committed result
is [`rocketbox_dims.json`](rocketbox_dims.json) (40 adult avatars, Blender 5.2.2). The local clone is sparse and holds
only the Adults folder; the upstream repository also has `Children` (four avatars) and `Professions` folders, which a
later fetch would add (listed in the repository tree, not yet inspected).

- **Skeleton:** a 3ds Max Biped, 80 bones, one mesh, in all 40 avatars. Bone names include `Bip01 Pelvis`, `Spine`,
  `Spine1`, `Spine2`, `Neck`, `Head`, `L/R Clavicle`, `L/R UpperArm`, `L/R Forearm`, `L/R Hand`, finger bones
  (`Finger0`..`Finger4` and their children), `L/R Thigh`, `L/R Calf`, `L/R Foot`, `L/R Toe0`, plus facial bones.
- **Import:** the FBX armature carries a 0.01 scale and the avatar faces **-Y** (all 40). The existing bake script
  (`scripts/rocketbox_bake_poses.py`) already turns each baked mesh to face +Y.
- **Proportions are nearly identical across avatars**, so one IK solve plus a small per-avatar adjustment should fit all:

| Measure (m) | min | median | max |
|---|---|---|---|
| mesh height | 1.723 | 1.799 | 1.869 |
| pelvis height (standing) | 0.895 | 0.895 | 0.923 |
| thigh | 0.399 | 0.399 | 0.426 |
| calf | 0.397 | 0.397 | 0.400 |
| upper arm | 0.253 | 0.286 | 0.286 |
| forearm | 0.240 | 0.271 | 0.271 |
| hand (wrist to middle finger base) | 0.094 | 0.096 | 0.096 |
| shoulder width (upper-arm joints) | 0.344 | 0.421 | 0.421 |
| hip width | 0.177 | 0.177 | 0.177 |
| pelvis to neck | 0.535 | 0.626 | 0.626 |
| foot joint height | 0.100 | 0.102 | 0.102 |
| toe offset forward of foot joint | 0.131 | 0.134 | 0.134 |

  The variation is in the arms, torso and shoulders (about 15% between the shortest and longest), not the legs.
- **The catalogue** (`configs/rocketbox_catalog.json`) holds 38 of the 40; `Female_Party_01` and `Female_Party_02` are not in it.
- **Animations:** 326 clips in `Assets/Animations/all_animations_max_motextr_static` (and an `_xy` variant). Searching the
  file names for bike, ride, cycl, motor, drive, scooter, saddle, helmet, vehicle gives **no match**: there are no riding
  or driving clips. The sitting clips (`sit_chair_*`, `sit_table_*`, 36 and 34 files) are the closest. Probing
  `m_sit_chair_idle_neutral_01` (measured): pelvis 0.59 m high, knee angle about 112 degrees, thighs slightly declined
  (about -14 degrees), elbow about 142 degrees, hand 0.66 m high. That is a seated base to start from, not a riding
  pose: **riding poses have to be authored** (hands to grips, feet to pedals or pegs, pelvis to the seat).

## 2. Models to build, and what is known about them

One named real model per class, so every dimension has a source. The geometry values below were gathered by research
agents; where a manufacturer page was unreachable the value is secondhand and must be checked against the manufacturer
chart before it is modelled.

### Motorcycles and scooters

| Model | Wheelbase | Seat height | Length | Tyres (front / rear) | Evidence |
|---|---|---|---|---|---|
| Yamaha MT-07 (naked) | 1,394 mm | 805 mm | 2,065 mm (EU sources: 2,085) | 120/70ZR17, 180/55ZR17 | published (yamahamotorsports.com/models/mt-07/specs); mm are conversions of published inches |
| Honda Rebel 500 (cruiser) | 1,491 mm | 691 mm | 2,207 mm | 130/90-16, 150/80-16 | published (hondanews.com 2024 specifications); mm converted |
| Honda PCX125 (scooter, UK 2025) | 1,315 mm | 763 mm | 1,935 mm | 110/70-14, 130/70-13 | published (honda.co.uk PCX125 specifications) |
| Honda Super Cub C125 (small commuter) | 1,242 mm | 780 mm | 1,910 mm | 70/90-17, 80/90-17 | published (hondanews.com 2024 C125); mm converted |

Also published for these: width, height, ground clearance, rake, trail, tank size, mass (see the cited pages). Tyre
outer diameters (about 510 to 646 mm) are **derived** from tyre size, not published. Sources disagree in places (MT-07
length, PCX trail 80 vs 86 mm). A sport or touring model was skipped: no clean data was found.

### Bicycles, scooters, cargo bike

| Model | Key geometry | Evidence |
|---|---|---|
| Trek FX 2 Disc (city/hybrid, size L, 2021) | wheelbase 1,070 mm; BB drop 65 mm; BB height 281 mm (a dealer page says 296 mm); chainstay 450 mm; head angle 71.5; seat angle 73.5; crank 170 mm; handlebar 660 mm (L); 700c | secondhand (BikeInsights, 99spokes via search summaries; Trek's own chart unreachable) |
| Trek Marlin 5 Gen 3 (mountain, size M, 29 in) | wheelbase 1,163 mm; BB height 326 mm; chainstay 438 mm; head angle 66.5; seat angle 73.4; crank 170 mm; handlebar 750 mm; tyre about 61 mm wide | secondhand (BikeInsights via search) |
| Micro Cruiser (kick scooter) | wheel 200 mm; bar height 740 to 890 mm; deck 508 x 110 mm | secondhand (one dealer listing) |
| Segway Ninebot Max G30P (e-scooter) | 1,167 x 423 x 1,203 mm unfolded; deck 508 x 170 mm; bar height 1,021 mm, width 478 mm; clearance 76 mm; tyre 10 in, about 64 mm wide | secondhand (eridehero.com, a wiki; the G30LP differs) |
| Tern GSD Gen 2 (cargo e-bike) | length 1,810 mm; 20 in wheels; saddle-to-pedal 690 to 1,120 mm | secondhand (retailer listings), thin |

Fit rules, from the bike-fit sources the agent could read: LeMond saddle height = 0.883 x inseam from the bottom
bracket centre (roadbikerider.com, fetched); knee bend at the bottom of the stroke 35 to 45 degrees for recreational
riding and 30 to 35 for road (phoenixphysicaltherapy.com, fetched), 25 to 35 in another source (definitions differ);
trunk angle from horizontal 40 to 80 degrees recreational, 30 to 40 road. For motorcycles, an SAE paper (2007-01-0438,
abstract only) reports rider torso angle about 65 degrees from horizontal on sport bikes and about 85 on cruisers.

## 3. Not published, so it must be measured from photos or side-view drawings

- **Motorcycles and scooters:** handlebar width and height, footpeg or footboard position relative to the seat,
  seat-to-grip distance, seat length and width, tank width, mirror and windscreen heights, scooter floorboard length
  and height. (Owner's manuals with dimensioned drawings were not searched.)
- **Bicycles:** frame tube diameters, pedal width, top-tube length, official mass by size, a manufacturer rider-height
  chart. **Kick scooter:** wheelbase, length, deck height, stem height, tyre width, mass. **Ninebot:** wheelbase, deck
  height above ground. **Tern GSD:** wheelbase, angles, BB height, handlebar width, crank length, confirmed mass.
- **For all classes:** lean angle, rider speed, lane position, clothing and helmet statistics, and box geometry of
  riders in real driving images have no sourced values. They are to be measured from BDD100K in step 1.

## 4. What this means for the build

1. The skeleton is known, uniform and scriptable: IK targets on `Bip01 L/R Hand`, `Foot`, `Toe0` and the pelvis are
   enough, with the arms (the part that varies) getting the per-avatar adjustment.
2. Riding poses are authored, not retargeted; the chair-sitting clip is only a seated base.
3. Wheel size, wheelbase and seat height are firm for the four motorcycle models; rider contact points (grips, pegs)
   come from tracing side-view drawings or photos of those models, and the bicycle numbers need checking against the
   manufacturer charts first.
4. Children avatars exist upstream but are not in the local clone; adults first.
5. Every non-Rocketbox mesh will be modelled by us from these dimensions; no third-party meshes are needed for the
   first spike, so there is nothing to clear for licensing beyond Rocketbox itself.
