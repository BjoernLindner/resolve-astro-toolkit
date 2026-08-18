# Resolve Astro Toolkit

Astro image processing tools for **DaVinci Resolve Studio** — DCTLs and Fusion macros for the operations Resolve does not ship with: non-linear stretching, green cast removal, gradient subtraction and star reduction.

Built for Milky Way nightscapes destined for large-format print.

> **Status: early.** The DCTLs work. The Fusion macros are in development — see [macros/README.md](macros/README.md).

---

## Why this exists

Resolve has an excellent colour engine: 32-bit float throughout, a node graph, HDR zone controls, per-hue and per-luminance saturation, and GPU speed. What it has never had is the handful of operations astrophotography depends on. There is no arcsinh stretch, no SCNR, no background extraction, no star separation.

There is also, as far as we can tell, **no astro toolset for Resolve or Fusion at all** — not on GitHub, not in Reactor, not commercially. The astro community uses PixInsight, Siril and Photoshop; Resolve shows up there only as a timelapse editor.

This repository is an attempt to close the part of that gap that is worth closing.

## What this is not

It is deliberately **not** a replacement for [Siril](https://siril.org), and using it as one will give worse results than doing nothing.

The dividing line is clean:

> **Anything needing multiple images or global optimisation belongs in Siril. Anything pixel-wise or local can live in Resolve — and some of it works better there.**

So: no stacking, no registration, no true DBE with sample points and a least-squares fit, no neural-network star removal. Those are weeks of work for a worse result than free tools already give you. See [docs/limitations.md](docs/limitations.md) for the reasoning in full.

Where this toolkit earns its place is **after** Siril: local refinement, masked correction, and finishing — with all of Resolve's grading tools available on the same node graph.

---

## Contents

| Tool | Type | Status | What it does |
|---|---|---|---|
| [`AstroStretch`](dctl/AstroStretch.dctl) | DCTL | ✅ working — **the core tool** | Arcsinh and MTF (midtone transfer) stretching with colour preservation, highlight protection and a clip warning. Without it, linear astro data cannot be developed in Resolve at all |
| [`AstroSCNR`](dctl/AstroSCNR.dctl) | DCTL | ✅ working | Subtractive chromatic noise reduction — removes the green cast every stretched astro image develops. Unlike Siril's, it can be masked to the sky |
| `AstroGradient` | Fusion macro | 🚧 in development | Local gradient subtraction via a median/blur background model. A maskable residual correction alongside GraXpert or Siril, not a replacement for either |
| `AstroStarReduce` | Fusion macro | ⚠️ experimental | Morphological star reduction (rank-filter opening). On dense Milky Way fields it cannot tell stars from fine nebula structure — at a window of 5 px it removes 90 % of the star pixels and 77 % of the real structure with them ([measurements](macros/README.md#the-limit-honestly)) |

### What you also need

This toolkit is one link in a chain, not a self-contained solution:

- **Before Resolve, required:** [Siril](https://siril.org) or [Seti Astro Suite](https://www.setiastro.com/) for calibration, registration, stacking, background extraction and colour calibration. Resolve cannot stack — and stacking gains more than any single processing step, since noise falls with 1/√N.
- **After Resolve, required for print:** Affinity Photo, Photoshop or darktable for ICC soft proofing. Resolve's colour management is LUT-based and cannot load a paper or printer profile.

The full chain is in [docs/workflow.md](docs/workflow.md); why those two steps will never move into Resolve is in [docs/limitations.md](docs/limitations.md).

## Requirements

- **DaVinci Resolve Studio 18 or newer.** DCTL support is Studio-only; the free edition has no DCTL entry in the LUT menu and no DCTL OFX node.
- A working space that is **linear**. The stretch maths assumes scene-linear data — applied to log data it is simply wrong. See [INSTALL.md](INSTALL.md#colour-management).

## Installation

See [INSTALL.md](INSTALL.md). Short version: drop the `.dctl` files into Resolve's LUT folder, hit *Update Lists*, and apply them through the **DCTL effect in the OpenFX panel** — not via right-click → LUT, which cannot pass slider values.

## Where this fits in a real workflow

```
Siril / SASpro                    ← calibration, registration, stacking,
  ↓                                 background extraction, colour calibration
16-bit TIFF (linear)
  ↓
DaVinci Resolve Studio            ← this toolkit + Resolve's own grading
  ↓
16-bit TIFF (Adobe RGB)
  ↓
ICC soft proofing                 ← Affinity Photo / Photoshop / darktable
  ↓                                 Resolve cannot soft-proof to printer profiles
Print
```

The long version, including where in the node tree each tool belongs and why the order matters, is in [docs/workflow.md](docs/workflow.md).

## Contributing

Way of working, commit format and the licensing constraint are in [CONTRIBUTING.md](CONTRIBUTING.md). Open points are tracked as [issues](https://github.com/BjoernLindner/resolve-astro-toolkit/issues).

## Licence

MIT — see [LICENSE](LICENSE).

All code here is written from scratch. Where convolution kernels were needed, they were implemented rather than adapted from existing GPL-licensed DCTL collections, specifically so this stays permissively licensed.

## Acknowledgements

No code is taken from these, but they were valuable as reference and are worth knowing about:

- [thatcherfreeman/utility-dctls](https://github.com/thatcherfreeman/utility-dctls) — mathematically-minded DCTLs plus `FrameAvg.fuse` and a DCTL interpreter fuse
- [baldavenger/DCTLs](https://github.com/baldavenger/DCTLs) (GPL-3.0) — extensive convolution collection
- [nmbr73/Shaderfuse](https://github.com/nmbr73/Shaderfuse) — the best living documentation of Fusion's GPU compute API
- [Siril](https://siril.org), [Seti Astro Suite](https://www.setiastro.com/), [GraXpert](https://graxpert.com/) — the free astro stack this toolkit is designed to sit downstream of
