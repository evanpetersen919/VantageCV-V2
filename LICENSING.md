# Licensing record

What each asset class in VantageCV comes from, what its licence says (quoted where the text was read),
what is settled, and what is not. This is a record of evidence, **not legal advice**. Updated 2026-10-08.
Dated working notes and results are in [`EXPERIMENT_LOG.md`](EXPERIMENT_LOG.md).

## Summary

| Asset class | Source and licence | Status for training a detector on renders | Used in |
|---|---|---|---|
| This repository's code | MIT ([`LICENSE`](LICENSE)) | Settled | everything |
| Unreal Engine 5.4 | Unreal Engine EULA | Engine use settled; see crowd row for the one clause that concerns training | rendering |
| City Sample vehicles, buildings, road kit, props | Epic Content License Agreement and Fab Standard License (EULA text read except Section 16(l)); Fab page tag "Allows usage with AI: No" | **Open.** Text read as limited to generative AI; Epic has not confirmed | all batches |
| City Sample crowd characters (adapted from MetaHumans) | Unreal Engine EULA, MetaHuman clause | **Unresolved.** Not limited to generative AI. **Not used in new work since 2026-10-08** | batches up to `train_v12e` |
| Megascans / Quixel items in the project (curbs, street furniture) | Not recorded | **Unverified** | all batches |
| Vehicle Variety Pack Vol. 2 box truck (Fab) | Fab Standard License; "Allows usage with AI: No" | Same reading as City Sample vehicles; unconfirmed | only the `v11` truck experiment |
| Rocketbox avatars (pedestrians in new work) | MIT since 2020-11-16 (earlier: Microsoft Research License) | Permissive text with a relicensing history; MIT does not name ML training; counsel question | `train_v13r` |
| BDD100K, Cityscapes, RealDriveSim (evaluation and comparison data) | Not recorded in this repository | **Not checked** | scoring, comparison arms |
| ultralytics (YOLO training code) | Not recorded in this repository | **Not checked** | training |

**Published so far:** MIT code, rendered images and videos, results and this log. **Not published:** datasets and trained
weights, held until the open rows above are resolved by counsel or by Epic.

## Epic content (City Sample, Unreal Engine)

Clause texts below were copied from Epic's pages by the repository owner on 2026-10-05; the pages themselves could not be fetched
by the tooling used here (HTTP 403), so re-check them on the live pages before relying on them.

**Content License Agreement** (<https://www.unrealengine.com/eula/content>)

- Section 3b, Linear Media: "You may freely Distribute Licensed Content incorporated into rendered linear media products. This means,
  for example, you may freely Distribute rendered video files (e.g., broadcast or streamed video files, cartoons, or movies) or images
  created using Licensed Content." Reading: publishing renders, images and videos is allowed.
- Section 17, Artificial Intelligence: "Any Licensed Content that has been tagged ... 'NoAI' ... will be known as 'NoAI Content.' ...
  'Generative AI Programs' means artificial intelligence, machine learning, deep learning, neural networks, or similar technologies
  designed to automate the generation of or aid in the creation of new content ... You shall not collect, aggregate, mine, scrape, or
  otherwise use NoAI Content (i) in datasets utilized by Generative AI Programs; (ii) in the development of Generative AI Programs; or
  (iii) as inputs to Generative AI Programs." Reading, **unconfirmed by Epic**: the restriction is on generative programs; an object
  detector generates nothing. A published dataset could be used by others for generative AI, so any dataset release would carry a
  "no generative AI use" notice.

**Fab page for City Sample:** "License terms: Standard License ... Allows usage with AI: No", treated as the NoAI tag. The question
sent to Epic (below) asked what it means for training a detector.

**Unreal Engine EULA, General Restrictions:** the Generative AI restriction is limited to generative programs. The MetaHuman
clause is not: "use, or permit others to use, MetaHuman digital characters and animation curves (or any rendered output thereof if
crafted to replicate the functionality of MetaHuman) to build or enhance any database or training or testing any artificial
intelligence, machine learning, deep learning, neural networks, or similar technologies."

**City Sample crowd provenance:** Epic's City Sample documentation (quoted by a research pass; verify on the live page): "The City
Sample is populated with thousands of unique digital human characters adapted from a subset of MetaHumans and accessories." In the
project files the crowd characters reference MetaHuman skeleton, skin, eye and hair assets. Verdict recorded 2026-10-05: derived
from MetaHuman with high confidence on provenance, low confidence on the clause's legal reach.

**Correspondence.** Asked Epic on 2026-10-05 (Unreal Engine licensing contact form): do the crowd characters count as MetaHuman for
this clause; does it prohibit training a non-generative detector on such renders, evaluated only on real photographs; may renders,
a labelled dataset and trained weights be published. Reply received 2026-10-08, in full: "Unfortunately, we're not able to provide
custom legal or EULA interpretations for specific developer distribution models. For questions regarding how the Unreal Engine EULA
applies to your specific product and distribution plans, we'd recommend consulting with your own legal counsel." No yes and no no.

**Decision (2026-10-08):** no MetaHuman-derived pedestrians in new datasets, experiments or releases; Rocketbox only. The
`pedestrian_source: city_sample` option remains only to reproduce earlier batches and logs a warning when used.

## Fab End User License Agreement (Standard License)

The Fab page for City Sample (and for third-party Fab content such as the Vehicle Variety Pack) names the Standard License. Text
pasted by the repository owner on 2026-10-08 from Epic's page (summary header: "Last updated: October 1st, 2024"). The pasted text
stops at Section 16(g); Section 16(l), which Section 6 points to for the definitions of "NoAI Content" and "Generative AI
Programs", was **not** in the paste and has not been read.

- Section 3(a), Standard License: "a non-exclusive and non-transferable license to privately use, reproduce, display, perform, and
  modify the Content in accordance with the terms of this Agreement ... you can privately use the Content however you want under a
  Standard License." Private research use is inside the grant, subject to the restrictions below.
- Section 4(b), Distributing Linear Media Projects: "Subject to any applicable restrictions in Section 6 (Content Use Restrictions),
  you may freely Distribute a Project that is a rendered linear media product. This means, for example, you may freely Distribute:
  i. rendered video files (e.g., broadcast or streamed video files, cartoons, movies, or images) and ii. images created using
  Content." Reading: publishing rendered images and videos is allowed; whether a labelled image dataset counts as "images created
  using Content" is a reading, not stated.
- Section 6(b)(vii), General Restrictions: "you may not: ... use NoAI Content (i) in datasets utilized by Generative AI Programs; (ii)
  in the development of Generative AI Programs; or (iii) as training inputs to Generative AI Programs. See Section 16(l) for the
  definitions of NoAI Content and Generative AI Programs." Same structure as Content License Agreement Section 17 (above): the
  restriction is worded around Generative AI Programs. The definition that decides whether a detector is one is in 16(l), unread.
- Section 7(a), Amendments: "Any Content you acquired (whether free or paid) prior to the modified terms will remain governed by the
  license terms applicable at the time when you acquired the Content." The terms that apply are those at the time of acquisition;
  acquisition dates of City Sample and of the Vehicle Variety Pack should be recorded (not yet).
- Section 14(b), Indemnification: the user indemnifies the Content Licensor against third-party claims "related to your Project or
  your exercise of a license granted to you". A liability point for counsel.
- Section 6(a), Non-Compatible Licenses: Standard License content may not be combined with code or content under a licence (for
  example GPL, LGPL, CC BY-SA) that would require the Content to be governed by other terms. Nothing in this repository combines
  Content with such code (renders and labels are separate files); noted for counsel together with the ultralytics licence (unchecked).

## Pedestrians in new work: Microsoft Rocketbox

- Repository `microsoft/Microsoft-Rocketbox` (115 rigged avatars; 38 adult avatars used). Current `LICENSE.md`: the standard MIT
  License, "Copyright (c) 2020 Microsoft", no added terms, no mention of machine learning.
- History (from the repository's git log): created 2020-03-13 with the **Microsoft Research License Terms**, granting use "for
  non-commercial, non-revenue generating, research purposes" and forbidding distribution of the Dataset. On 2020-11-16 (commits
  `1eeb280`, `accbe42`) the paper's first author replaced it with the MIT License. The repository was archived 2026-10-02.
- Paper (Gonzalez-Franco et al., Frontiers in Virtual Reality, 2020-11-03, DOI 10.3389/frvir.2020.561558, 13 days before the
  relicensing): the library is "publicly available for research and academic use".
- Prior use by others: Kerim et al., WACV 2024 (arXiv 2208.12763), Section 4, uses "The Microsoft Rocketbox Avatar Library" for
  character avatars in a synthetic-data simulator and releases the simulator and datasets. It states no licence terms.
- Open for counsel: MIT does not name ML training; whether the later MIT grant covers every mesh and texture given the earlier
  research-only release and the paper's wording.

## Other City Sample-adjacent content

- **Megascans / Quixel** (road curbs `Modular_Curb_5_M`, street furniture): the project holds these under `Content/Megascans`; no
  licence text has been read or recorded. Unverified.
- **Vehicle Variety Pack Vol. 2** (Fab, free; one box truck): Standard License, "Allows usage with AI: No", "Generated with AI:
  No". Used only in the `v11` experiment; later batches use City Sample vehicles. Same reading and status as City Sample's vehicles.

## Not yet checked

Terms of BDD100K, Cityscapes and RealDriveSim (the last states CC BY 4.0 on its project page, to be re-checked), and of ultralytics.
Cityscapes and BDD100K are used for evaluation only; their terms still apply to what is published about them.

## What would change this record

- Section 16(l) of the Fab EULA (the definitions of NoAI Content and Generative AI Programs), and the acquisition dates of the Fab content.
- A written answer from Epic or counsel on the NoAI tag and the MetaHuman clause.
- Counsel's reading of the Rocketbox history.
- Verbatim licence text for Megascans, BDD100K, Cityscapes, RealDriveSim and ultralytics.
- A scene built entirely from permissively licensed vehicles, buildings and props (not scoped).
