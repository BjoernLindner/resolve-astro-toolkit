#!/usr/bin/env python3
"""
Numpy port of AstroStretch.dctl and AstroSCNR.dctl
==================================================

The counterpart to prototype_astro_macros.py, for the two DCTLs rather
than the two Fusion macros. Same purpose: measure against real image
material instead of assuming.

The macros were prototyped before they were built. The DCTLs were not -
they were written straight into Resolve, which is how AstroSCNR came to
ship in v0.1.0 with its effect never assessed on an image (#28). This
file closes that gap, and the measurements it produced are written up in
issues #28, #29 and #30.

WHAT THIS IS FOR

Two things a Resolve session cannot give you:

  1. Exact numbers. A parade scope tells you the green trace sits above
     the others. It does not tell you that the 95th percentile of the
     green excess is 0.0169, which is the number that decides whether a
     hardcoded constant in the DCTL is the right order of magnitude.

  2. Reproducibility. Anyone can re-run this and get the same figures.
     A screenshot of a scope is not evidence anyone else can check.

WHAT THIS IS NOT

Not a substitute for testing in Resolve. Two differences matter:

  - The decode here goes to the camera's native primaries (dcraw -o 0),
    while Resolve routes through a CST into DaVinci Wide Gamut. Absolute
    levels differ; on the test material the sky lands at about 10.7 %
    here against the 13-25 % recorded from the Resolve session.
  - Anything about how the image looks - star fringing, how much green
    the foreground loses, whether real airglow survives - needs eyes on
    a display.

KEEPING IT HONEST

The formulas below are transcribed by hand from the .dctl sources. There
is no mechanism that keeps them in sync. Change a DCTL, change this file,
or the numbers it produces describe a version that no longer exists.

USAGE

    uv run --with numpy --with rawpy python examples/prototype_astro_dctl.py IMAGE.ARW [...]

Decoding happens in-process via rawpy, with the settings matching the
dcraw invocation documented in prototype_astro_macros.py:

    dcraw -v -T -6 -w -o 0 -4 -q 3 -W
"""

import argparse
import sys

import numpy as np
import rawpy

REC709 = (0.2126, 0.7152, 0.0722)


# --------------------------------------------------------------- decode


def decode_linear(path):
    """Decodes a raw file to linear float RGB in the camera's own
    primaries. The postprocess arguments correspond one to one to the
    dcraw flags in prototype_astro_macros.py: gamma=(1,1) and
    no_auto_bright are -4 and -W, output_color=raw is -o 0."""
    with rawpy.imread(path) as raw:
        rgb16 = raw.postprocess(
            gamma=(1, 1),
            no_auto_bright=True,
            output_bps=16,
            use_camera_wb=True,
            output_color=rawpy.ColorSpace.raw,
            demosaic_algorithm=rawpy.DemosaicAlgorithm.AHD,
        )
    return rgb16.astype(np.float32) / 65535.0


def luminance(img):
    return (
        REC709[0] * img[..., 0] + REC709[1] * img[..., 1] + REC709[2] * img[..., 2]
    ).astype(np.float32)


def find_horizon(lum, percentile=5, drop_factor=4.0):
    """Same rough horizon detection as prototype_astro_macros.py, so the
    sky region measured here is the one the macro figures were taken on."""
    row_p = np.percentile(lum, percentile, axis=1)
    baseline = np.median(row_p[: len(row_p) // 3])
    for y in range(len(row_p) // 3, len(row_p)):
        if row_p[y] < baseline / drop_factor:
            return y
    return len(row_p)


# --------------------------------------------------- AstroStretch.dctl


def astro_asinh(v):
    """dctl/AstroStretch.dctl: log(v + sqrt(v*v + 1)). The DCTL runtime
    has no inverse hyperbolic function, so the DCTL spells it out - and
    so does this, rather than calling np.arcsinh, so the two stay
    comparable including their rounding."""
    return np.log(v + np.sqrt(v * v + 1.0))


def asinh_factor(x, s):
    d = astro_asinh(np.float32(s))
    if d < 1e-8:
        return np.ones_like(x)
    return np.where(
        x < 1e-7, s / d, astro_asinh(s * x) / (np.maximum(x, 1e-7) * d)
    ).astype(np.float32)


def mtf_factor(x, m):
    mm = float(np.clip(m, 0.0005, 0.9995))
    if abs(mm - 0.5) < 1e-6:
        return np.ones_like(x)
    num = (mm - 1.0) * x
    den = (2.0 * mm - 1.0) * x - mm
    out = (num / np.where(np.abs(den) < 1e-8, 1.0, den)) / np.maximum(x, 1e-7)
    out = np.where(np.abs(den) < 1e-8, 1.0, out)
    # The DCTL tests x before it tests the denominator and returns early,
    # so this branch has to win over the one above.
    out = np.where(x < 1e-7, (mm - 1.0) / (-mm), out)
    return out.astype(np.float32)


def stretch_factor(x, mode, stretch, midtone):
    return asinh_factor(x, stretch) if mode == 0 else mtf_factor(x, midtone)


def astro_stretch(
    img,
    mode=0,
    stretch=25.0,
    midtone=0.25,
    blackpoint=0.0,
    shadowlift=0.0,
    preserve=1.0,
    hiprotect=0.0,
    clampout=True,
):
    """Port of dctl/AstroStretch.dctl. Defaults match the DEFINE_UI_PARAMS
    defaults in the DCTL. The Clip Warning is not ported - it is a display
    aid, and painting pixels red would only corrupt the statistics."""
    bp = float(np.clip(blackpoint, 0.0, 0.995))
    inv = np.float32(1.0 / (1.0 - bp))
    z = np.maximum((img - bp) * inv, 0.0).astype(np.float32)

    lum = luminance(z)
    kl = stretch_factor(lum, mode, stretch, midtone)
    w = float(np.clip(preserve, 0.0, 1.0))

    out = np.empty_like(z)
    for c in range(3):
        kc = stretch_factor(z[..., c], mode, stretch, midtone)
        out[..., c] = z[..., c] * (kl * w + kc * (1.0 - w))

    hp = float(np.clip(hiprotect, 0.0, 1.0))
    if hp > 0.0:
        thr = 1.0 - 0.9 * hp
        t = np.clip((lum - thr) / max(1.0 - thr, 1e-4), 0.0, 1.0)
        s = (t * t * (3.0 - 2.0 * t)) * hp
        for c in range(3):
            out[..., c] = out[..., c] * (1.0 - s) + z[..., c] * s

    sl = float(np.clip(shadowlift, 0.0, 0.5))
    if sl > 0.0:
        out = out * (1.0 - sl) + sl

    return np.clip(out, 0.0, 1.0) if clampout else out


# ------------------------------------------------------ AstroSCNR.dctl

AVG_NEUTRAL, MAX_NEUTRAL, ADD_MASK = 0, 1, 2

# The two constants under examination in #29. Named here so the analysis
# can vary them; the DCTL has them hardcoded at these values.
ADD_MASK_GAIN = 4.0
SHOW_MASK_GAIN = 8.0


def astro_scnr(
    img,
    method=AVG_NEUTRAL,
    amount=1.0,
    preserve_lum=False,
    add_mask_gain=ADD_MASK_GAIN,
):
    """Port of dctl/AstroSCNR.dctl. Returns (image, removed), where
    removed is the per-pixel green reduction the Show Mask display is
    built from."""
    r, g, b = img[..., 0].copy(), img[..., 1].copy(), img[..., 2].copy()
    a = float(np.clip(amount, 0.0, 1.0))

    limit = np.maximum(r, b) if method == MAX_NEUTRAL else 0.5 * (r + b)
    g_new = np.minimum(g, limit)

    if method == ADD_MASK:
        soft = np.clip((g - limit) * add_mask_gain, 0.0, 1.0)
        w = a * soft
    else:
        w = np.full_like(g, a, dtype=np.float32)

    g_out = g * (1.0 - w) + g_new * w
    removed = g - g_out

    # Redistribution onto red and blue. Note there is no clamp after
    # this in the DCTL either - see #30.
    if preserve_lum:
        share = np.where(removed > 0.0, removed * 0.5, 0.0)
        r = r + share
        b = b + share

    return np.stack([r, g_out, b], axis=-1), removed


def show_mask(removed, gain=SHOW_MASK_GAIN):
    return np.clip(removed * gain, 0.0, 1.0)


# ------------------------------------------------------------ analysis


def analyse(path, stretch=25.0, blackpoint=0.0):
    print(f"\n{'=' * 70}\n{path}\n{'=' * 70}")

    img = decode_linear(path)
    h, w = img.shape[:2]
    print(f"decoded {w}x{h}, linear, camera primaries")

    horizon = find_horizon(luminance(img))
    print(f"horizon row {horizon} of {h} ({horizon / h:.1%} of frame height)")

    sky = img[:horizon].copy()
    del img
    print(
        f"sky linear      mean {sky.mean():.4f}  "
        f"R {sky[..., 0].mean():.4f}  G {sky[..., 1].mean():.4f}  B {sky[..., 2].mean():.4f}"
    )

    st = astro_stretch(sky, stretch=stretch, blackpoint=blackpoint)
    del sky
    lum = luminance(st)
    print(
        f"after stretch   luminance mean {lum.mean():.1%}  median {np.median(lum):.1%}  "
        f"p05 {np.percentile(lum, 5):.1%}  p95 {np.percentile(lum, 95):.1%}"
    )

    # --- pass-through
    zero, _ = astro_scnr(st, amount=0.0)
    print(f"\nAmount 0.00 is bit-exact pass-through: {np.array_equal(zero, st)}")
    del zero

    # --- the green excess, which every constant below is measured against
    limit = 0.5 * (st[..., 0] + st[..., 2])
    excess = st[..., 1] - limit
    pos = excess[excess > 0]
    print(f"\ngreen excess  G - (R+B)/2  ({pos.size / excess.size:.1%} of sky pixels)")
    for q in (50, 75, 90, 95, 99, 99.9):
        print(f"  p{q:<5} {np.percentile(pos, q):.4f}")
    print(f"  max    {pos.max():.4f}    mean {pos.mean():.4f}")
    p95 = np.percentile(pos, 95)

    # --- #29, first half: is Additive Mask a no-op
    out_avg, rem_avg = astro_scnr(st, method=AVG_NEUTRAL, amount=1.0)
    out_add, rem_add = astro_scnr(st, method=ADD_MASK, amount=1.0)
    ratio = rem_add.mean() / max(rem_avg.mean(), 1e-12)
    soft = np.clip(excess * ADD_MASK_GAIN, 0.0, 1.0)[excess > 0]
    print(f"\nAdditive Mask, gain {ADD_MASK_GAIN}")
    print(f"  mean weight on green-excess pixels  {soft.mean():.4f}")
    print(f"  share reaching full weight          {(soft >= 0.99).mean():.4%}")
    print(f"  mean green removed, Average Neutral {rem_avg.mean():.6f}")
    print(f"  mean green removed, Additive Mask   {rem_add.mean():.6f}")
    print(f"  Additive Mask does {ratio:.1%} of Average Neutral")
    print(f"  gain that would put p95 at full weight: {1.0 / p95:.1f}")
    del out_add

    # --- #29, second half: is Show Mask legible
    m = show_mask(rem_avg)
    print(f"\nShow Mask, gain {SHOW_MASK_GAIN}")
    for q in (50, 90, 99, 99.9):
        print(f"  p{q:<5} {np.percentile(m, q):.4f}")
    print(f"  share above 0.1  {(m > 0.1).mean():.4%}")
    print(f"  gain that would put p95 of removal at full brightness: {1.0 / p95:.1f}")

    # --- #30: what Preserve Luminance actually returns
    out_pl, _ = astro_scnr(st, method=AVG_NEUTRAL, amount=1.0, preserve_lum=True)
    loss_off = (lum - luminance(out_avg)).mean()
    loss_on = (lum - luminance(out_pl)).mean()
    theory = REC709[0] * 0.5 + REC709[2] * 0.5
    over = (out_pl[..., 0] > 1.0) | (out_pl[..., 2] > 1.0)
    print("\nPreserve Luminance")
    print(f"  mean luminance loss, off  {loss_off:.6f}")
    print(f"  mean luminance loss, on   {loss_on:.6f}")
    print(
        f"  compensated               {1.0 - loss_on / max(loss_off, 1e-12):.1%}"
        f"   (predicted {theory / REC709[1]:.1%})"
    )
    print(f"  pixels above 1.0 in R or B  {over.sum()} ({over.mean():.4%})")
    print(
        f"  full compensation would need {REC709[1] / (REC709[0] + REC709[2]):.2f}"
        f" x removed, against the 0.5 in the DCTL"
    )

    # --- method ordering: (R+B)/2 <= max(R,B), so Average must be stronger
    _, rem_max = astro_scnr(st, method=MAX_NEUTRAL, amount=1.0)
    print("\nMethod strength")
    print(f"  mean removed, Average Neutral {rem_avg.mean():.6f}")
    print(f"  mean removed, Maximum Neutral {rem_max.mean():.6f}")
    print(f"  Average stronger than Maximum: {rem_avg.mean() > rem_max.mean()}")


def main():
    ap = argparse.ArgumentParser(
        description="Run the AstroStretch and AstroSCNR ports over raw frames "
        "and print the measurements behind issues #28, #29 and #30."
    )
    ap.add_argument("images", nargs="+", help="raw files, e.g. testfiles/*.ARW")
    ap.add_argument(
        "--stretch",
        type=float,
        default=25.0,
        help="Arcsinh Stretch, matching the DCTL default (25.0)",
    )
    ap.add_argument(
        "--blackpoint",
        type=float,
        default=0.0,
        help="Black Point, matching the DCTL default (0.0). The usable "
        "range measured in Resolve was 0.002-0.005",
    )
    args = ap.parse_args()

    for path in args.images:
        analyse(path, stretch=args.stretch, blackpoint=args.blackpoint)


if __name__ == "__main__":
    sys.exit(main())
