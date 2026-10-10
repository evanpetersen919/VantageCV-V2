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
| Megascans / Quixel items in the project (curbs, bollards, hydrants, barriers, street furniture) | Governed by the same two agreements as City Sample: Fab Standard License (Fab EULA) and, for legacy Epic-era items, the Epic Content License Agreement; no Megascans-specific AI clause found | Same status as City Sample (NoAI wording is generative-only; Epic unconfirmed) | all batches |
| Vehicle Variety Pack Vol. 2 box truck (Fab) | Fab Standard License; "Allows usage with AI: No" | Same reading as City Sample vehicles; unconfirmed | only the `v11` truck experiment |
| Rocketbox avatars (pedestrians in new work) | MIT since 2020-11-16 (earlier: Microsoft Research License) | Permissive text with a relicensing history; MIT does not name ML training; counsel question | `train_v13r` |
| BDD100K (25% of every arm's training images; all evaluation) | UC Regents licence: free for educational, research and not-for-profit use; commercial use only for BDD/BAIR Commons members (text read from a mirror) | Research use fine; **commercial use of anything trained on it needs a separate licence** | training, evaluation |
| Cityscapes (evaluation only) | Non-commercial; abstract derivatives such as trained models may be distributed (official page read) | Fine for evaluation; no Cityscapes data in anything published | evaluation |
| RealDriveSim (comparison arms only) | CC BY 4.0 (official project page read) | Fine with attribution; not part of any release | comparison arms |
| ultralytics (YOLO training code) | AGPL-3.0 (LICENSE file read); Ultralytics states trained models are AGPL-3.0 too unless an Enterprise License is bought | **A blocker for releasing weights under a non-AGPL licence**; the repository code that imports it is also affected | training |

**Published so far:** MIT code, rendered images and videos, results and this log. **Not published:** datasets and trained
weights. **Goal (owner, 2026-10-08): publish the dataset on Kaggle; trained weights are not going to be published.** What that
requires is in the section "Publishing the dataset on Kaggle" below; the weights-only rows (ultralytics, BDD100K's commercial
restriction) stop mattering for a dataset-only release.

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

## Publishing the dataset on Kaggle

Scope: rendered images and their labels (COCO, YOLO, KITTI, masks) of a Rocketbox batch, with a README. No weights, no BDD100K,
Cityscapes or RealDriveSim data, no Epic asset files, no ultralytics code (link to the GitHub repository instead).

**Which batches.** Only batches rendered with `pedestrian_source: rocketbox` (`train_v13r` and later). Never the batches with the
City Sample crowd (`train_v7p`, `train_v12e` and earlier): their renders contain MetaHuman-derived characters, and the EULA clause
covers "any rendered output thereof". Checked 2026-10-08 on all 256 scenarios of `urban_dense_v13r.yaml`: 6,343,451 asset entries,
by folder `/Game/Building` 5,295,020, `/Game/Vehicle` 1,151,193, `/Game/Megascans` 346,712, `/Game/Road` 282,419, `/Game/Prop` 249,340,
`/Game/VantageCV` (this project's own, including the Rocketbox meshes) 81,863; **none under `/Crowd` or with MetaHuman in the path**.
The test level holds no resident crowd (frames rendered with no scenario pedestrians show none).

**What the texts say about a dataset of renders** (readings, not legal advice):
- Distributing renders: Content License Agreement Section 3b and Fab EULA Section 4(b) allow freely distributing "images created
  using Content", subject to the Content Use Restrictions (Section 6). Rocketbox's MIT grant includes the right to "publish,
  distribute" (a copy of the notice must accompany copies of the avatars themselves; renders are not copies, but the notice is
  cheap to include).
- The clause that touches a dataset: CLA Section 17 and Fab EULA Section 6(b)(vii) bar using NoAI Content "in datasets utilized by
  Generative AI Programs". City Sample is NoAI-tagged. A detector is not a generative program, but a public dataset can be
  downloaded by anyone, including people training generative models. Whether that puts the publisher in breach is not stated;
  the cautious course is terms that forbid generative-AI use of the dataset. **Counsel question.**
- Licence choice on Kaggle: the Creative Commons and ODbL options cannot add a ban on generative-AI use (their terms forbid extra
  restrictions), and a share-alike licence (CC BY-SA, GPL-like) collides with Fab Section 6(a), which names CC BY-SA as
  incompatible with Standard License content. The natural fit is Kaggle's "Other (specified in description)" with explicit terms:
  attribution; research and development of non-generative models allowed; no use to train, develop or feed generative AI programs;
  no redistribution of Epic assets (none are included); third-party notices below. CC0 is not suitable. Wording to be confirmed
  by counsel.
- Notices to carry in the dataset README: City Sample and Unreal Engine are Epic Games, Inc.'s; Microsoft Rocketbox avatars,
  MIT, Copyright (c) 2020 Microsoft, with the licence text; a statement that no real-world data is included.

**Still open for a dataset release**
1. The NoAI/dataset point above (Epic's reading of Section 17 / 16(l), unread and unconfirmed).
2. Megascans items (curbs, street furniture; 5.5% of the scenario asset entries) fall under the same agreements as City Sample
   (see above), so they share point 1 and need nothing further of their own.
3. Rocketbox: MIT's silence on ML and the research-only release history (counsel); for an image dataset the avatars are rendered
   pixels, not distributed files, which lowers but does not remove the question.
4. The Kaggle licence wording itself, and Kaggle's own terms for uploads containing third-party content.

**No longer in play with a dataset-only release:** ultralytics/AGPL for weights, and BDD100K's commercial-use restriction for
trained models (only metrics computed with them would appear, and no BDD100K data is shipped). The AGPL and BDD100K notes above
become relevant again if weights are ever published.

## Vegetation textures and models (CC0)

Added 2026-10-10 for the leafy street trees, the curb grass and the scanned trees. Everything here is under Creative Commons CC0 1.0
(public domain dedication), which allows copying, modifying and redistributing, even commercially, with no permission or attribution.
CC0 is also compatible with the dataset terms discussed above (it adds nothing to the restrictions on the Epic content).

| Source | Asset | Used for | Licence statement checked |
|---|---|---|---|
| ambientCG (https://ambientcg.com) | `LeafSet024` (beech), `LeafSet014` (hornbeam), `LeafSet027` (maple) | leaf-cluster cards of the generated trees (`unreal_plugin/tools/build_foliage_textures.py`) | https://docs.ambientcg.com/license/ : "All ambientCG assets are provided under the Creative Commons CC0 1.0 Universal License" (2026-10-10) |
| ambientCG | `Grass005`, `Bark012` | curb grass patches and tree bark (`fetch_photo_textures.py`, 1K maps committed under `unreal_plugin/content/photo`) | same page |
| Poly Haven (https://polyhaven.com) | `jacaranda_tree`, `tree_small_02`, `searsia_lucida`, `othonna_cerarioides`, `fern_02` (scans by Rob Tuytel and Rico Cilliers) | the photographic street trees, shrubs, hedges and ferns (`prepare_photoreal_trees.py`; the FBX and textures are downloaded, not committed) | https://polyhaven.com/license : "CC0 means absolute freedom" (2026-10-10) |

The Unreal assets built from these (materials, instances, Nanite mesh) live in the project under `/Game/VantageCV/Foliage` and
`/Game/VantageCV/Trees`; no Epic content is used for any of them. The generated leaf, bark and grass patterns made earlier with
Pillow and numpy have no third-party origin and were replaced by the photographs above.

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
- Scan of the local clone (the avatars and animations used; `Assets/Avatars/Adults` and `Assets/Animations`): the only licence or
  notice files are the repository's `LICENSE.md` (MIT) and `README.md`; no per-asset or third-party notices were found there.
- Open for counsel: MIT does not name ML training; whether the later MIT grant covers every mesh and texture given the earlier
  research-only release and the paper's wording.

## Other City Sample-adjacent content

- **Fab library record (read 2026-10-08 from the launcher's local cache, `VaultCache/FabLibrary/listings_v1.db`):** the library holds
  three listings: *City Sample* (Epic Games, `is_ai_forbidden` = 1), *Vehicle Variety Pack Volume 2* (Switchboard Studios,
  `is_ai_forbidden` = 1) and *Stylized House Interior* (`is_ai_forbidden` = 0; no content from it is in the project). An earlier
  note that the Vehicle Variety Pack read 0 is superseded: the cache now reads 1, matching its page. Launcher download folders
  (file creation dates, a proxy for acquisition, not the licence acceptance date): `CitySample_5.7` 2025-12-27,
  `VehicleVc016a8147616V2` 2025-12-30, `CitySample_5.4` 2026-09-16. The exact acceptance dates are in the Epic account's purchase
  history (not read).
- **Megascans / Quixel** (the project's `Content/Megascans`: bollards, barriers, hydrants, mailboxes, plant pots, garbage cans,
  `Modular_Curb_5_M`, parking meter, signs; the scenes use curbs, hydrants, a parking meter and a road sign, from
  `road_edge_kit.py` and `street_furniture.py`). Checked 2026-10-08:
  - `quixel.com/terms` permanently redirects (HTTP 308) to Epic's Content License Agreement (`unrealengine.com/eula/content`).
  - Quixel's licence page says: "Assets bought on Fab are available under the Fab Standard License" (linked to the Fab EULA), and
    offers custom project or studio licences; it says nothing on AI.
  - Epic staff on the forum (2024-10-23, thread "Megascans License?"): Megascans obtained from Fab are under "the new license"
    (Fab Standard); items acquired earlier under Unreal Unlimited "remain subject to the Content EULA and will be considered
    UE-only content". Community members asked for confirmation on other points and got no staff answer.
  - The Fab library cache has no separate Megascans listing, so these items came inside the City Sample package (whose listing is
    flagged AI-forbidden).
  Result: Megascans here fall under the same two agreements already recorded (Fab EULA Sections 3, 4, 6; Content License
  Agreement Sections 3, 17), with the same distribution allowance for rendered images and the same NoAI wording. No
  Megascans-specific restriction on AI or datasets was found anywhere; none of these pages was available verbatim (Epic's pages return
  403), so the owner's paste of Fab Section 16 and the account's licence record remain the missing pieces. This is not a separate
  open question any more.
- **Vehicle Variety Pack Vol. 2** (Fab, free; one box truck): Standard License, "Allows usage with AI: No", "Generated with AI:
  No". Used only in the `v11` experiment; later batches use City Sample vehicles. Same reading and status as City Sample's vehicles.

## Epic clauses: second sources and what could not be read

Epic's own pages (`unrealengine.com/eula/...`, `fab.com/eula`) refuse automated fetches (HTTP 403) and web archives are blocked
for the tooling used, so the quotes above rest on the owner's paste. Corroboration found on 2026-10-08:

- MetaHuman clause: a third-party mirror (ConductAtlas, version CA-V-001373, first captured 2026-05-05) quotes "use, or permit others
  to use, MetaHuman digital characters and animation curves ... to build or enhance any database or training ...", matching the
  owner's paste; CGChannel (2025-06-04) reports that under Epic's new licensing MetaHumans may be used "in workflows that
  incorporate artificial intelligence technology" but "not to train or enhance the AI models themselves". The restriction on
  training is therefore not limited to generative AI, and dates from June 2025 or earlier.
- Content License Agreement Section 17: Epic's change log (search snippet only) describes it as new, prohibiting NoAI content in
  datasets for, in the development of, or as inputs to Generative AI Programs, matching the owner's paste.
- Fab EULA Section 6(b)(vii) points to Section 16(l) for the definitions of NoAI Content and Generative AI Programs. A forum post
  (Epic Developer Community, "AI image use") quotes a different Fab paragraph (when content counts as created with Generative AI
  Programs), not the NoAI definition. **16(l) itself has not been read.** If it matches Content License Agreement Section 17's
  definition ("designed to automate the generation of or aid in the creation of new content"), a detector is outside it; that is
  an inference until the text is read.

## Evaluation and training data

- **BDD100K** (25% of every arm's real training images, plus all evaluation). The code repository's `LICENSE` is BSD 3-Clause
  (Copyright 2018 Fisher Yu); the data carry a different licence. A mirror of the dataset (Hugging Face `dgural/bdd100k`)
  reproduces it: "Copyright (c) 2018. The Regents of the University of California (Regents). All Rights Reserved."; permission to
  "use, copy, modify, and distribute this software and its documentation for educational, research, and not-for-profit purposes"
  without fee; a separate grant for "commercial purposes (such rights not subject to transfer)" to "BDD and BAIR Commons members and
  their affiliates"; commercial enquiries to UC Berkeley's Office of Technology Licensing. The official site (`doc.bdd100k.com`)
  could not be reached, so this is read from a mirror and should be confirmed on the official page. Meaning for this project:
  research use is inside the grant; weights trained on BDD100K images, if released for commercial use by others, raise a question
  for counsel.
- **Cityscapes** (evaluation only, never trained on). Official page, read 2026-10-08: freely available "for non-commercial
  purposes"; no use of the dataset or a derivative work for commercial purposes; "That you do not distribute this dataset or
  modified versions"; "It is permissible to distribute derivative works in as far as they are abstract representations of this
  dataset" (trained models are the page's own example); attribution required; Terms of Use Section 3.2 limits access to registered
  users affiliated with scientific bodies and Section 4.2 limits making contents available to third parties. Nothing published here
  contains Cityscapes data; scores and per-class numbers are results.
- **RealDriveSim** (512 images in two comparison arms; not part of any release). Official project page, read 2026-10-08: "Licensed
  under CC BY 4.0". Sharing anything derived from it needs attribution (Jadon et al., 2025, arXiv 2506.16319); the repository keeps
  its files in the git-ignored `external_data/`.
- **ultralytics** (YOLO training and scoring). The repository `LICENSE` is the GNU Affero General Public License v3 (19 November
  2007); its page on the AGPL says nothing about trained models. Ultralytics' own statements, as reported by search summaries on
  2026-10-08 (its license FAQ and request-a-license page, a maintainer's comment in a GitHub issue, and Roboflow, a licensor of
  Ultralytics and a commercial party): trained and fine-tuned models, "even if you train your own model from scratch" and use it
  only internally, fall under AGPL-3.0 unless an Enterprise License is obtained, and downstream code that includes the training code
  or a model should be open-sourced. Whether a court would agree is disputed (a commenter in the same issue argues custom-trained
  models are not covered). The primary pages were not read (the AGPL page on ultralytics.com has no such text; the FAQ and
  Enterprise terms were not retrieved). Meaning for this project: weights trained with ultralytics should be treated as AGPL-3.0 if
  they are ever published (or the models retrained with a differently licensed trainer), and this repository's MIT licence does not
  extend over ultralytics code it imports. Counsel question; also the reason weights stay unpublished. Blender (used only to bake
  Rocketbox poses) is GPL software; that its outputs are not covered by the GPL was not checked here.

## Open items that need a person, not a search

- Paste Fab EULA Section 16 in full (especially 16(l)) and Content License Agreement Sections 3 and 17 as they read now.
- Acceptance dates and the licence version shown in the Epic account for City Sample and the Vehicle Variety Pack.
- Confirm the BDD100K licence on the official site (`doc.bdd100k.com` did not resolve; `bdd-data.berkeley.edu` failed its certificate
  check); read Ultralytics' license FAQ and Enterprise terms directly.
- Counsel: the NoAI tag and datasets, the MetaHuman clause (no longer used), Rocketbox's history and MIT's silence on ML (and,
  only if weights are ever released, BDD100K's commercial restriction and AGPL for the weights). Epic would not interpret any of it (reply of
  2026-10-08).

## What would change this record

- Section 16(l) of the Fab EULA (the definitions of NoAI Content and Generative AI Programs), and the acquisition dates of the Fab content.
- A written answer from Epic or counsel on the NoAI tag and the MetaHuman clause.
- Counsel's reading of the Rocketbox history.
- Verbatim licence text for Megascans, BDD100K, Cityscapes, RealDriveSim and ultralytics.
- A scene built entirely from permissively licensed vehicles, buildings and props (not scoped).
