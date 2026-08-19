# Installation

## Requirements

- **DaVinci Resolve Studio 18 or newer.** DCTL support is Studio-only — the free edition has neither a DCTL entry in the LUT menu nor the DCTL OFX node.
- A GPU that Resolve supports. The DCTLs are translated to CUDA, OpenCL or Metal depending on the platform.

---

## Installing the DCTLs

### 1. Find the LUT folder

The most reliable route goes through Resolve itself:

> **Project Settings → Color Management → "Open LUT Folder"**

That opens the correct folder in your file manager. The paths are normally:

| System | Path |
|---|---|
| Windows | `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT\` |
| macOS | `/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT/` |
| Linux | `/home/resolve/LUT/` |

### 2. Drop the files in

Create a subfolder `Astro` there and copy the `.dctl` files into it. The subfolder is optional, but it keeps the list in the Inspector readable.

### 3. Update the lists

Click **"Update Lists"** in the same dialog. A Resolve restart is not needed — that also holds after every edit to a `.dctl` file, which makes the development cycle very pleasant.

### 4. Apply

> ⚠️ **The most common stumbling block:** right-click a node → *LUT* → DCTL does **not** work with these files. That path is meant for DCTLs without controls and cannot pass slider values.

The correct route:

1. Color page, select a node (or create one)
2. Open the **OpenFX panel** (icon at the top right)
3. Under *ResolveFX Color*, drag the **"DCTL"** effect onto the node
4. In the Inspector, pick the file you want under *DCTL List*

The sliders then appear directly below it in the Inspector.

### If nothing shows up

- Check the path — the folder has to be the one "Open LUT Folder" opens
- Check the file extension: `.dctl`, not `.dctl.txt` (Windows hides known extensions)
- Restart Resolve once
- Look under *Preferences → General → LUT Locations* to see whether a different folder is configured

---

## Colour management

This is not an optional detail. **The stretch operates on scene-linear data.** On log data such as DaVinci Intermediate, S-Log or N-Log the maths is simply wrong — the result then looks flat and odd in the midtones, without it being immediately obvious why.

Which route fits depends on what you are feeding in:

| Source | Route |
|---|---|
| A camera RAW file (ARW, CR3, NEF, RAF, RW2, DNG) | **A** — decode it to linear and be done |
| A 16-bit TIFF out of Siril or SASpro | **B** or **C** — the file is already linear, the project just has to leave it that way |

### Route A — decode the RAW to linear

The shortest path when the source is a RAW file, and the one that leaves the fewest ways to go wrong. No transform node at all.

> Project Settings → **Camera Raw**
> - RAW profile: your camera's, e.g. **Sony Stills - ARW**
> - Decode using: **Project** (so the settings below actually apply)
>
> then under *Project Settings* in the same panel:
>
> | Setting | Value | Why |
> |---|---|---|
> | Gamma | **Linear** | The one that decides whether the stretch is right or wrong |
> | Color space | your delivery primaries if offered — Adobe RGB for print, otherwise leave it | The gamut conversion is correct here, on linear data |
> | Auto tone normalization | **off** | It rescales each image's tonal range on its own. That is the stretch's job, and with it on, two frames of the same scene are not comparable |
> | Sharpness | **0.00** | Sharpening at decode amplifies noise and bloats stars. It belongs at the very end of the chain, if at all — see [docs/workflow.md](docs/workflow.md) |

**The viewer will go almost black.** That is correct, not a fault. Linear night-sky data sits at a few tenths of a percent; the whole point of `AstroStretch` is to lift it. If the image still looks like a normal photograph after this, the decode is not linear.

### Route B — colour-managed project

> Project Settings → Color Management
> - Color Science: **DaVinci YRGB Color Managed**
> - Timeline Color Space: **DaVinci WG / Linear**

### Route C — explicit transform nodes

> Project Settings → Color Management → Color Science: **DaVinci YRGB**

and build the colour space change explicitly into the chain:

```
Node 1   Color Space Transform   input  ->  delivery primaries, Linear gamma
                                            Tone Mapping: None
Node 2   DCTL: AstroStretch
Node 3   ... further grading ...
```

More nodes, but you can see at every point what state the data is in. For a project where the order decides the result, that is the better choice. Note there is no closing transform — see below.

### Alternatively: just around the stretch

If you want to work in DaVinci Intermediate otherwise, bracketing the stretch is enough:

```
CST: DaVinci Intermediate → Linear
DCTL: AstroStretch
CST: Linear → DaVinci Intermediate
```

### The closing transform: there usually isn't one

Two details that the standard Resolve grading pattern gets wrong for this toolkit:

- **Tone mapping must be set to None** on the CST going in. It defaults to `DaVinci` with an adaptation value, and it compresses tones non-linearly — which destroys the linearity the stretch assumes.
- **Do not close the chain with `CST Linear → Adobe RGB`.** `AstroStretch` *is* the transfer function; after it the data is display-referred, not linear light. A closing CST would apply a second curve on top, lifting the image twice.

Put the gamut conversion on the way in instead — set the opening CST's output to your delivery primaries (Adobe RGB for print, sRGB for screen) with **Linear** gamma — and leave the end of the chain alone. A gamut conversion is a matrix operation and is only correct on linear light, which is what you have there and not what you have at the end.

The reasoning in full, including what to do if you would rather keep DaVinci Wide Gamut as the working space, is in [docs/workflow.md](docs/workflow.md#where-the-colour-space-transforms-belong).

### How to check, rather than trust the settings

Colour space settings are easy to get wrong in a way that looks fine. Resolve's naming does not help: `Rec.709 (Scene)` reads as though it were scene-referred, but it is not linear, and picking it gives the stretch nothing it needs. Under plain DaVinci YRGB the timeline colour space setting is largely inert anyway, so setting it alone fixes nothing.

Check the image instead of the dropdowns. Open the waveform, bypass everything downstream of the input, and look at the night sky:

- **Correct (linear):** the trace is crushed against the bottom of the scale. Almost nothing above the first few percent.
- **Wrong (already gamma-encoded):** the trace sits in the middle of the scale, and the image looks like a viewable photograph before you have stretched anything.

The second case is the most common failure with this toolkit, and it is worth thirty seconds to rule out before blaming a slider.

---

## Installing the Fusion macros

*(Once the macros are available.)*

Macros are `.setting` files and belong in the Macros folder:

| System | Path |
|---|---|
| Windows | `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Fusion\Macros\` |
| macOS | `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Macros/` |
| Linux | `/opt/resolve/Fusion/Macros/` |

After a Resolve restart they appear on the Fusion page under **Effects Library → Tools → Macros**.

---

## Resolution — important for large-format print

Nodes on the Color page operate at **timeline resolution**, not at source resolution. If your timeline is set to HD and your image has 45 megapixels, you are modelling gradients on a downscaled image and scaling the result back up.

Two solutions:

- **Photo page (Resolve 21)** — processes at source resolution, independent of the timeline. The convenient route.
- **Set the timeline resolution manually** to the full sensor resolution (Project Settings → Master Settings → Timeline Resolution → Custom).

In **Fusion** a separate rule applies: a **single clip** runs at full source resolution, whereas a **Fusion clip** runs at timeline resolution. So never create a Fusion clip for high-resolution work.
