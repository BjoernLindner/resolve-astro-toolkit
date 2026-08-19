# What this toolkit deliberately does not do — and why

It would be tempting to want to handle everything inside Resolve. One program, one node graph, no file exports in between. This page explains why that is a bad idea, and where exactly the line runs.

The short version:

> **Anything that needs multiple images, or a global optimisation, does not belong in Resolve. Anything that works pixel-wise or locally can be done in Resolve — and some of it better than the alternatives.**

---

## The technical limits of each extension route

Resolve can be extended in three ways. Each has a hard ceiling.

### DCTL

DCTLs are GPU shaders in C-like syntax. Contrary to what is often assumed they are **not** restricted to per-pixel operations: there is a second signature with `__TEXTURE__` parameters that lets you read any pixel of the image via `_tex2D()`. Convolution, blur, median and morphology are all feasible with that.

What a DCTL **cannot** do:

| Limit | Consequence |
|---|---|
| Only **one** input image | The subtraction `image − model` has to happen outside |
| Only **one** frame | Frame averaging is impossible. Full stop. |
| No multi-pass within one file | Multiple passes = multiple nodes; intermediate results cannot be fetched back |
| **No global reductions** | No sum, no min/max, no histogram over the whole image |
| No persistent storage | Nothing can be remembered between pixels or between frames |

The fourth row is the most consequential — more on that below.

### Fuse

Fuses are Lua plugins for Fusion, JIT-compiled, installable without a compiler, with hot reload. They can do everything a DCTL can, **plus** multiple image inputs, multi-pass, access to arbitrary frames, GPU kernels and persistent buffers across frames.

That is the sensible extension route once you need to go beyond DCTL. It covers almost everything except true global optimisation.

### OFX

Custom OpenFX plugins in C++ are possible; Resolve ships the SDK, including examples for random frame access. Full freedom, but a C++ toolchain, GPU kernels in three language variants and no hot reload. Realistically several weeks for the first usable plugin.

Third-party OFX plugins only run in Resolve Studio.

---

## The four things this toolkit does not attempt

### 1. Stacking and registration

**Why it fails:** not at the averaging — there is even a finished, free `FrameAvg.fuse` that averages correctly over N frames. It fails at **registration**: identifying stars across frames, matching, rotating, warping them.

With untracked wide-angle shots the star field rotates between frames. Without alignment, averaging is worthless — you get trails instead of points.

**Where it belongs:** Siril does this with two-pass global registration, sigma-clipping rejection and normalisation. Free, mature, well documented.

**And the actual point:** stacking gains more than any processing step in astro. Noise falls with 1/√N — 16 frames mean roughly 75 % less noise, about two stops. That is not something you claw back afterwards in a grading application.

### 2. True DBE / background extraction with sample points

**Why it fails:** a proper DBE places sample points on clean sky, rejects outliers and fits a global polynomial or an RBF from them by least squares. That requires a **reduction across the entire image** — a DCTL cannot do it in principle, a Fuse only laboriously, an OFX plugin well.

**What is possible instead:** "model = heavily smoothed image, then subtract". With smooth gradients the difference is small. With strong, irregular light pollution it is considerable.

**Where it belongs:** GraXpert (AI-based, free) or Siril's RBF background extraction.

That is why the macro here is called `AstroGradient` and not `AstroDBE` — it is a local residual correction, not a replacement.

### 3. True star separation (starless)

**Why it fails:** StarNet and StarXTerminator are neural networks. A network distinguishes between "small bright point that is a star" and "small bright detail that is nebula structure". A minimum filter cannot — to it, both are the same thing.

In dense Milky Way star fields, morphological reduction therefore eats structure along with the stars.

**A theoretical route exists:** a Fuse can launch an external Python process with an ONNX model and read the result back — there is a working precedent for this. That would make StarNet integrable into Fusion. It is a multi-week project for a function that already exists as a standalone program, for free.

**Where it belongs:** the StarNet2 CLI, free, callable from within Siril.

### 4. ICC soft proofing

**Why it fails:** Resolve's colour management is colour-space and LUT based throughout, not ICC based. There is no way to load a paper or printer profile, no gamut warning, no rendering intents, no black point compensation. On macOS you can use display ICC profiles for the viewer — that is monitor calibration, not output profiling.

A workaround via a 3D LUT generated from the ICC profile exists, but it is only a preview without a gamut warning and without a selectable intent.

**Where it belongs:** Affinity Photo, Photoshop, Capture One or darktable — as the last step before printing.

With dark subjects this matters particularly: black point compensation decides whether the shadows stay differentiated or run together below the paper's Dmax.

---

## What Resolve does better in return

So that the list does not come across as one-sided — there are reasons to work here at all:

- **32-bit float throughout** on the GPU, with no loss of bit depth anywhere in the chain
- **A node graph** instead of a layer stack: branches, outside nodes for automatically inverted keys, layer mixers with composite modes
- **The HDR palette** with freely definable zones including falloff — you can put a zone exactly on the Milky Way luminance. There is no equivalent for that in astro software.
- **Lum vs Sat and Hue vs Sat** as curves — lowering saturation in the shadows is remarkably effective against colour noise in the sky
- **Magic Mask** for landscape foregrounds, AI-based, works on single images
- **Power Windows** with soft edge control, more precise than most masking tools in astro software
- **The Color Warper** for the fine separation between Milky Way colour and background sky

For compositing sky and foreground, and for the final grade, Resolve genuinely is superior to the classic astro tools. That is the area this toolkit is built for.
