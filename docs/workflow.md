# Where these tools belong in the workflow

This toolkit is a building block, not a path. For the tools to do what they are supposed to do, they have to sit in the right place — and with astro the order is not a matter of taste, it follows from the maths.

---

## The full chain

```
1  CAPTURE
   Several sky frames, ideally separate foreground frames

2  PREPROCESSING              Siril / Seti Astro Suite Pro
   Calibration (darks/flats/bias)
   Registration + stacking    ← Resolve cannot do this
   Background extraction      ← global, belongs here
   Colour calibration (SPCC)
   Star separation (StarNet2)
   → 16-bit or 32-bit TIFF, linear

3  GRADING                    DaVinci Resolve Studio  ← this toolkit
   CST → linear
   AstroStretch
   AstroGradient (local residual correction)
   AstroSCNR
   AstroStarReduce
   + Resolve's own tools
   CST → Adobe RGB
   → 16-bit TIFF

4  PRINT PREPARATION          Affinity Photo / Photoshop / darktable
   ICC soft proofing          ← Resolve cannot do this
   Output sharpening
   Dithering against banding
```

Two steps Resolve cannot do and will not be able to do: **stacking with registration** and **ICC soft proofing against printer profiles**. Neither is a question of convenience, both are architectural — see [limitations.md](limitations.md).

---

## The node chain in Resolve

A proposal that follows from the ordering logic:

| Node | Tool | Why here |
|---|---|---|
| 01 | **CST** Camera Raw output → output primaries, **Linear** gamma, tone mapping *None* | Everything that follows assumes linear data — and this is where the gamut conversion belongs, see below |
| 02 | Spatial NR *(Studio)* | Chroma noise out early, while it is still Gaussian |
| 03 | **AstroGradient** | Remove residual gradients **before** stretching |
| 04 | **AstroStretch** (arcsinh) | The first, strong stretch |
| 05 | **AstroStretch** (MTF, gentle) | Fine tuning — two gentle stretches beat one aggressive one |
| 06 | **AstroSCNR** | The green cast, which has only now become visible |
| 07 | HDR palette / log wheels | Put a dedicated zone on the Milky Way luminance |
| 08 | Lum vs Sat | Lower saturation in the shadows → colour noise in the sky |
| 09 | Hue vs Sat | Raise blue/cyan, lower the orange of light pollution |
| 10 | **AstroStarReduce** | Pull the stars back once the contrast is settled |
| 11 | Power Window / Magic Mask | Separate sky and foreground, treat the foreground separately |
| 12 | Blur/Sharpen | Sharpening last |
| 13 | *(no closing CST)* | `AstroStretch` already applied the transfer function — see below |

---

## Where the colour space transforms belong

The usual Resolve pattern is a sandwich: convert into a large working space at the top of the node tree, grade in the middle, convert to the output space at the bottom. That pattern is right, and it applies on the Photo page as much as on the Color page. But the standard filling — DaVinci Wide Gamut with **DaVinci Intermediate** gamma — is wrong for this toolkit, and the standard closing transform is wrong twice over.

### The working gamma must be Linear, not Intermediate

DaVinci Intermediate is a log curve. `AstroStretch` assumes scene-linear data; on log data the arcsinh maths is simply wrong. So the opening CST converts to **Linear**, not Intermediate, and its tone mapping must be set to **None** — tone mapping compresses tones non-linearly and destroys exactly the linearity the stretch depends on.

If your source is a RAW file you can skip this node entirely by decoding to linear in Camera Raw. One transform fewer is one mistake fewer.

### The stretch *is* the transfer function

This is the part that catches people out. Arcsinh and MTF are precisely the curves that map scene-linear astro data into a viewable range — that is what "stretching" means in astrophotography. **After `AstroStretch`, the data is display-referred.** It is not linear light any more.

So a closing `CST Linear → Adobe RGB` applies a *second* transfer function on top of the first. The image lifts twice, the shadows wash out, and the black point and shadow lift sliders stop meaning what their labels say. It looks plausible — brighter than the raw file, which is what you expected — and the damage only shows up in print, as a sky that will not sit at the 8–15 % this page asks for.

### Therefore: convert the gamut on the way in, not on the way out

A gamut conversion is a matrix operation, and it is only colorimetrically correct on linear light. Since the data is linear *before* the stretch and display-referred *after* it, the conversion belongs at node 01:

```
Node 01   CST   Camera Raw output  ->  Adobe RGB primaries, Linear gamma
                                       Tone Mapping: None
Node 02+  AstroStretch, AstroSCNR, grading  (Adobe RGB primaries, linear -> stretched)
Node 13   nothing
```

Set node 01's output primaries to whatever you are delivering — Adobe RGB for print, sRGB for screen. Everything downstream then works in the delivery gamut, and no closing transform is needed.

A side benefit: `AstroStretch` weights its luminance with the Rec.709 coefficients (0.2126 / 0.7152 / 0.0722). Those are a poorer fit in DaVinci Wide Gamut than in Adobe RGB or sRGB, which share the Rec.709 white point. Working in the delivery gamut makes the colour-preserving stretch slightly more accurate, not less.

**The trade-off, stated honestly:** you give up the very large DaVinci Wide Gamut as a working space. If you would rather keep it, the closing CST must convert gamut *only* — the same gamma on both sides — and never `Linear → Adobe RGB`. That path introduces a small colorimetric error, because the CST will linearise using a standard curve that is not the arcsinh the data actually carries. The error is largest on saturated colours, which for this material means star colours — the very thing `AstroStretch` has a Preserve Color slider to protect.

---

## Why this order

### Gradients before the stretch

In the linear state a gradient is a simple, smooth, additive function. After the stretch it is distorted non-linearly and can no longer be described cleanly by a smooth model.

There is a second effect on top of that: the stretch amplifies the gradient along with everything else. You are then forced to raise the black point far enough that the bright corner of the image does not glare — and you lose the dark corner in the process.

### Noise reduction early, but luminance NR late

Two schools, both with an argument. You treat chroma noise early and linear, because it is still Gaussian there and because colour noise carries practically no information. Luminance noise reduction, by contrast, only after the stretch — before it, you simply cannot see what you are doing.

And always masked: protect bright, high-signal regions, smooth only the dark, low-SNR areas. Unmasked luminance NR is the main cause of the plastic look.

### SCNR after the stretch

On linear data the green excess is still small and SCNR achieves little. It only becomes visible through the stretch, because the Bayer matrix has twice as many green pixels and the amplification carries that along.

### Star reduction after the contrast

The other way round, every increase in contrast bloats the stars you just shrank back up again, and you get dark rings around bright stars on top.

### Sharpening dead last

Any scaling destroys the effect of earlier sharpening. Output sharpening has to be matched to the final pixel size and to the paper — and therefore does not really belong in Resolve at all, but in print preparation.

### Never let the black point clip

The night sky is never completely black. A background clipped to zero does not just lose structure, it produces visible banding in large-format print, because the quantisation steps in a smooth dark area get stretched across 84 cm of image width.

Target value: background at roughly **8–15 %**. `AstroStretch` has a shadow lift slider for that and a clip warning that shows in red where the black point is currently destroying information.

---

## A word on the foreground

With nightscapes the foreground is almost always the bottleneck — it typically sits 4–8 EV below the sky. No tool in this toolkit repairs that.

What helps is **separate treatment**: develop the foreground as its own branch in the node graph, with a different colour temperature, lifted shadows and considerably stronger noise reduction — and blend it in through a mask.

For the mask: a gradient Power Window for soft horizons, and for silhouettes (trees, rock edges) rather the Magic Mask or a channel-based qualifier. A softly feathered edge is fatal with conifers and produces a visible halo.

And all gradient tools have to be kept away from the foreground. A dark landscape looks like a gradient to a blur model.
