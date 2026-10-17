# Fusion macros — development status

Two macros are planned. `AstroGradient` is built ([`AstroGradient.setting`](AstroGradient.setting)); `AstroStarReduce` is not yet — what follows is the build plan, the reasoning behind the construction, and the current status of each.

Why macros and not DCTLs: both operations need **two images at the same time** (the original and a model derived from it), and that is exactly what a DCTL cannot do — it only ever sees one input image. In Fusion this is a node graph with two branches.

---

## AstroGradient — local gradient removal

### Purpose

Light pollution, airglow, moonlight and the falloff towards the horizon produce large-scale brightness **and** colour gradients. The method: build a smooth model of the background and subtract it from the image.

**Explicitly meant as a complement, not a replacement** for GraXpert or Siril's background extraction. The advantage here is not the quality of the model, but that it can be restricted to parts of the image with a mask and that it sits in the same node graph as the rest of the grade. Typical use: a residual gradient in one corner of the image that the global correction left behind.

### Node graph

```
                    ┌─ RankFilter ── Blur ────────┐
                    │  (median,      (Fast Gauss,  │
MediaIn ────────────┤   large)        very large)  │
        │           │                  = model     │
        │           └────────────────────────────┐ │
        │                                        │ │
        └──────────────────────────────────► ChannelBooleans
                                              (subtract)
                                                  │
                                            BrightnessContrast
                                            (offset back up)
                                                  │
                                              [output]
```

### Why this order

**Median before blur.** The Rank Filter at rank 0.5 throws stars out of the model before it gets blurred. Without that step the stars are modelled along with everything else, and you then subtract holes at exactly the positions where stars are.

**Fast Gaussian, not box.** Fusion's Fast Gaussian uses a constant-time method — a large radius costs practically nothing extra. That is the reason to build this macro in Fusion and not as a DCTL, where the cost grows linearly with the radius.

**Channel Booleans, not Merge.** Fusion's Merge node has **no** apply mode "Subtract" — the additive/subtractive slider there controls alpha premultiplication and has nothing to do with subtraction. The right tool is Channel Booleans with operation *Subtract*.

**Offset afterwards.** After the subtraction the background sits close to zero. In 32-bit float negative values survive, so the image is not broken — but for further work you want to lift the background back to roughly 8–12 %. That is the same reason `AstroStretch` has a Shadow Lift slider: a night sky clipped to zero produces banding in large-format print.

### Measured parameters

Tested against real image material: three RAWs of Björn's, Sony ILCE-7M2, 20mm Sigma Art @ f/1.6, 13 s, ISO 1000, 6048×4024 (`_DSC5410/11/12.ARW`, 2026-08-17). The node graph was rebuilt as a Python/OpenCV prototype, see [`examples/prototype_astro_macros.py`](../examples/prototype_astro_macros.py) — before/after in [`examples/gradient-before-after.jpg`](../examples/gradient-before-after.jpg).

| Control | Effect | Value for 24 MP full frame (6048×4024) |
|---|---|---|
| Model Size | Downsample factor before the blur | **24** (→ working size ~250×170 px) |
| Star Filter | Median window on the downscaled level | **5** |
| Softness | Gaussian sigma on the downscaled level | **6** (equivalent to a ~150 px radius on the full image — still \< 2 s of compute) |
| Strength | How much of the model gets subtracted (0–1) | 1.0 to start, then by eye |
| Pedestal | Lift applied after the subtraction | **35 % of the mean model value** — holds the sky at about 1.7–2 % luminance instead of at zero |
| Show Model | For judging whether the model really contains background only | — |

**Why downsampling instead of a direct large-radius blur:** that was an open question in the original build plan. The empirical answer: a downsample by a factor of 24 (box averaging via `INTER_AREA`) plus a small median and Gaussian kernel on the reduced image gives exactly the same result as a direct giant blur at full resolution — only orders of magnitude faster (< 2 s instead of many seconds per preview). In Fusion that corresponds to: **Resize down (Fast Gaussian inside the Resize is optional) → Rank Filter (median) → Blur (Fast Gaussian) → Resize back to original size**, rather than a rank/blur pass directly on the full image.

**Tested and confirmed:** at the values above, the Milky Way band — despite its considerable width in the frame — does not visibly migrate into the model. The model image stays a smooth gradient (dark at the top, a light-pollution glow at the bottom right) with no recognisable band structure. The result after subtraction shows the Great Rift and the star clouds far more clearly than the unprocessed image, see the comparison image.

### The decisive failure mode

**The Milky Way is itself a large-scale brightness structure.** If the model radius is too small, the band migrates into the model and gets subtracted away — you end up with a flat image and often do not immediately notice why. Hence the "Show Model" switch: nothing that you want to see in the image may be recognisable in the model. At the measured values (downsample 24, sigma 6) this is confirmed to hold for an image 6048 px wide.

The second failure mode with nightscapes: **the foreground.** A dark landscape in the lower third of the frame looks like a gradient to the blur. In the test image the treeline starts at about 86 % of the image height (y ≈ 3450 of 4024 px) — the rough detection behind that figure is a jump in per-row brightness at the 5th percentile. The macro should therefore act on the sky only, via a mask — in Fusion through the effect mask input, on the Color page through a Power Window. In the Python prototype the boundary was cut hard rather than feathered; that produces a visible edge at the horizon in the test image — in Fusion, work with a softly falling-off mask, never with a hard cut.

### Status

✅ Built and verified in Resolve Studio 21.1.1 on `_DSC5411.ARW`: [`AstroGradient.setting`](AstroGradient.setting).

**How the file came about.** The node graph was built in a live Fusion comp through the scripting API, and its tool definitions were written out by Fusion's own serialiser (`comp:CopySettings()` + `bmd.writefile()`). Only the `MacroOperator` wrapper — the exposed controls, the mask router and the `Model Size` user control — was added by hand. The finished file was then pasted back into a comp and rendered: its output is **bit-identical** to the hand-built graph, so the hand-authoring risk this section used to warn about is closed by test, not by care.

**Installing.** Copy `AstroGradient.setting` to

```
~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Macros/
```

It then appears in Fusion under *Add Tool → Macros*.

**Where it sits in Resolve.** A Fusion macro cannot live in a Color page node. It runs on the **Fusion page** of the clip, and the Fusion page is processed *before* the Color page — so the macro still sees the linear Camera Raw decode and still runs before `AstroStretch`, exactly as [`docs/workflow.md`](../docs/workflow.md) requires for node 03. Node 03 on the Color page becomes redundant and can be disabled.

```
MediaIn ──► AstroGradient ──► MediaOut
                 ▲
SkyMask ─────────┘  (effect mask: sky = white, foreground = black)
```

**Inside the macro:**

```
AGIn ─┬─ ModelDown ── StarFilter ── Smooth ── ModelUp ─┬─ Strength ─┐
      │  (Scale,      (RankFilter,  (Blur,    (Resize  │  (gain)     │
      │   Box)         rank 0.5)     Gaussian) Cubic)  │             ▼
      └────────────────────────────────────────────────┼──────► Subtract ── Pedestal ──► ShowModel ──► out
                                                       │        (masked)    (masked)       ▲
                                                       └───────────────────────────────────┘
AGMask ──► effect mask of Subtract and Pedestal
```

**Controls and their Fusion values.** The prototype's OpenCV units do not carry over 1:1. Both were pinned by rendering each Fusion stage to EXR and fitting it against the OpenCV operation applied to the *same* `MediaIn` frame:

| Control | Fusion input | Default | How it maps to the prototype |
|---|---|---|---|
| Model Size | `ModelDown` user control, `XSize = 1/ModelSize` | **24** | Same divisor. Fusion's `Scale` rounds up (6024×4024 → 252×168, OpenCV floors to 251×167) — irrelevant after the blur |
| Star Filter | `StarFilter.Size` | **2** | Size is a radius: **2 ≙ `medianBlur` ksize 5** (closest fit of sizes 1–3) |
| Softness | `Smooth.XBlurSize`, filter *Gaussian* | **38** | Fusion's Gaussian Blur Size ≈ **6.3 × σ** (fitted over sizes 12–60, interior error < 0.05 %). σ 6 → 38. Edges are clamped, not mirrored as in OpenCV |
| Strength | `Strength.Gain` on the model branch | **1.0** | `result = input − Strength × model + Pedestal` |
| Pedestal | `Pedestal.Brightness` | **0.01** | Scalar offset in linear units, same on all channels. `0.35 × mean(model)` = 0.0102 on this frame; set it by the outcome, see below |
| Show Model | `ShowModel.Mix` | **0** | 0 = corrected image, 1 = model, 0.5 = both blended |
| Effect Mask | `AGMask` → `Subtract` and `Pedestal` | — | Unconnected = whole frame. Outside the mask the input passes through untouched (verified bit-exact) |

**Pedestal in practice.** Resolve's RAW decode is scaled differently from the dcraw decode the prototype ran on, so the prototype's "1.7–2 %" sky figure does not transfer. What matters is the sky after the full grade: on this frame, with the node chain from `docs/workflow.md` unchanged, Pedestal **0.015** puts the stretched sky background at **11 %** (p10–p90: 9–13 %), inside the 8–15 % target. 0.01 gave 7.5 %, 0.02 gave 14 %.

**Verification on `_DSC5411.ARW`** (6024×4024, Resolve RAW decode, linear float):

| Check | Result |
|---|---|
| Model vs prototype pipeline on the same input, image interior | 0.8 % relative RMS (6.7 % including the outer 200 px, where the edge modes differ) |
| `Subtract` output vs `input − model` | bit-exact |
| Macro output vs hand-built graph, at default, Show Model 1 and Strength 0.5 | bit-exact |
| Sky flatness, 8×8 block medians above the treeline | max/min **7.9 → 1.22**, coefficient of variation 0.42 → 0.03 |

**Known limit — the horizon.** Directly above the treeline a bright rim of light pollution remains. Two causes, both measured: the glow rises too steeply there for a model this smooth (at the image centre the input climbs from 0.09 to 0.16 over the last 4 % of image height, the model only reaches 0.07), and the dark foreground pulls the model down in exactly that zone, because the blur averages trees into it. The effect mask keeps the trees from being darkened but cannot repair a model that already contains them. The fix is a mask-aware model — blur `image × mask` and `mask` separately and divide — which belongs with the sky mask work in #3.

---

## AstroStarReduce — morphological star reduction

### Purpose

Shrink stars without touching the nebula structure. After a strong stretch the stars are almost always too dominant and distract from the Milky Way band.

**This too is finishing, not a replacement for StarNet.** A genuinely starless image comes out of a neural network; filters cannot reproduce that. What is possible here is the classic morphological star shrink — good for the last bit of polish, bad as the only method on dense star fields.

### Node graph

```
MediaIn ─┬────────────────────────────────────────────┐
         │                                            │
         └─ RankFilter ── RankFilter ─┬─────────► Merge/Blend
            (rank 0 =     (rank 1 =   │           (strength)
             minimum)      maximum)   │                │
                                      │            [output]
                          = opening   │
                                      └─► ChannelBooleans (difference)
                                              = star mask
```

### Why this works

Fusion's **Rank Filter** sorts the pixels in the window and takes the pixel at the chosen rank. Rank 0 is the minimum, 0.5 the median, 1.0 the maximum.

- **Rank 0 (minimum)** makes bright points shrink — stars get smaller
- **Rank 1 (maximum)** afterwards brings the nebula structure and the background back to their original level

The combination is called an **opening** in morphology and is the standard method for removing small bright objects from an image without altering large structures.

The difference between the original and the opening is the **star mask** — useful, because it lets you treat the stars separately and blend them back in later in a controlled way.

### Measured parameters

Measured on the same test image (after gradient removal, see above). Star size in the raw image: a bright, isolated star has a full width at half maximum of **~3 px in one direction, ~1 px in the other** (slight trailing elongation at 13 s untracked; the NPF limit for this setup would be ~11.5 s) — so the stars are tiny, and an opening window in the single-digit pixel range is already enough.

Measured quantitatively on a dense star field in the Milky Way band (700×700 px crop, elliptical kernel, rank 0 → rank 1):

| Window size *k* | Star pixels remaining | Structure (std. dev.) remaining in the band |
|---|---|---|
| 3 | 36 % | 46 % |
| 5 | 10 % | 23 % |
| 7 | 0 % | 14 % |
| 9 | 0 % | 9 % |
| 13 | 0 % | 7 % |

**This confirms the warning from the original build plan very concretely:** already at *k*=5 practically all stars are gone — but at the same time three quarters of the real nebula structure in the band has gone with them. In a dense Milky Way field there is **no window value that reliably removes stars and reliably preserves structure** — precisely the behaviour a neural network (StarNet) can deliver and a pure rank filter cannot.

**Recommended starting values:** *k* = 3, **strength 0.3–0.4** (not 1.0). At that combination about 87 % of the star pixels remain as residual signal, but the effect is visible and the nebula structure stays largely intact. Comparison image: [`examples/star-reduction-compare.jpg`](../examples/star-reduction-compare.jpg) — on this particular single frame (ISO 1000, unstacked), however, the image noise covers the effect almost completely at normal viewing distance; the difference only becomes cleanly visible after stacking and denoising in Siril.

| Control | Effect | Starting value |
|---|---|---|
| Star Size | Rank filter window size (opening) | **3** (at 24 MP; for higher-resolution images scale proportionally to star size in pixels, not to image size) |
| Strength | Blend between original and reduced | **0.3–0.4** |
| Protect Large Stars | Threshold above which bright stars are left alone | not implemented yet |
| Output Mask | Output the star mask instead of the image | — |

### The limit, honestly

On dense Milky Way star fields the minimum filter eats nebula structure along with the stars — that is no longer just a suspicion but quantified by the table above: already at *k*=5 some 77 % of the local structure is lost, at *k*=9 more than 90 %. The method does not distinguish between "small bright point that is a star" and "small bright detail that is structure" — to the filter, both are the same thing.

So: keep the dose small (*k*=3, strength ≤0.4), and where possible apply it **after** a real star separation with StarNet, where it is only about the final polish.

### Status

🚧 The parameters are measured against real image material, the Fusion node graph has not been built yet. Build instructions with the starting values above:

1. `RankFilter` — rank 0 (minimum), window 3×3
2. `RankFilter` — rank 1 (maximum), window 3×3 (identical to step 1 — together they form a morphological opening)
3. `Dissolve` or `Merge` with the blend slider at **0.3–0.4** between the original (step 0) and the result of step 2 — that is the "strength"
4. For the star mask in parallel: `ChannelBooleans` operation *Difference* between the original and step 2

Group nodes 1–3 (or 1–4 with the mask as a second output), export as a macro, commit the `.setting` here.

---

## How these macros are developed

Both `.setting` files are meant to come into being **against real image material**, not at the drawing board. The parameter ranges (how large is "large" on a 45 MP image?) cannot sensibly be guessed.

Procedure:

1. ✅ Node graph computed through as a Python/OpenCV prototype on three real Milky Way RAWs (Björn's captures, 2026-08-17) — see [`examples/prototype_astro_macros.py`](../examples/prototype_astro_macros.py)
2. ✅ Sensible value ranges and defaults determined — see the "Measured parameters" tables above for both macros
3. Build the node graph in Fusion with exactly these starting values, verify against the same images — ✅ `AstroGradient`, ⬜ `AstroStarReduce`
4. Wrap the nodes as a macro and verify the file by re-importing it — ✅ `AstroGradient`, ⬜ `AstroStarReduce`
5. Commit the `.setting` here — ✅ `AstroGradient`, ⬜ `AstroStarReduce`

**Why the detour through Python instead of going straight to Fusion:** finding the parameters (how large is "large"? how much structure does a rank filter really eat?) can be iterated faster and measured exactly (see the percentages in the tables) in an environment with numpy/OpenCV than by eye in the Fusion viewer. The actual node graph in Fusion still has to be built — Fusion's `.setting` format cannot be generated blind without risk, that has to happen in the application itself.
