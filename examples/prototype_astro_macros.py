#!/usr/bin/env python3
"""
Prototype script for AstroGradient and AstroStarReduce
======================================================

Simulates the planned Fusion node graphs (see macros/README.md) in
Python/OpenCV, in order to find sensible parameter ranges against real
image material BEFORE the node graphs are built by hand in Fusion.

Tested against: Sony ILCE-7M2, 20mm F1.4 Sigma Art @ f/1.6, 13s, ISO 1000,
6048x4024 (three frames of the same Milky Way scene, 2026-08-17).

The results of that run are written up in macros/README.md under
"Measured parameters". This script is not production software, it is the
workbench the Fusion macros were calibrated on.

Requirements: numpy, opencv-python. RAW decoding happens separately with
dcraw, see the comment below.

    dcraw -v -T -6 -w -o 0 -4 -q 3 -W your_image.ARW
    # -o 0 -4  = linear, no gamma curve (camera space, not sRGB)
    # -W       = no auto-bright (it would distort the linear values)
    # -q 3     = AHD demosaicing
    # -T -6    = TIFF, 16-bit
"""

import numpy as np
import cv2
import time


def load_linear_tiff(path):
    """Loads a 16-bit TIFF produced by dcraw. IMPORTANT: PIL often reads
    16-bit TIFFs incorrectly as 8-bit RGB - hence cv2 with
    IMREAD_UNCHANGED here, which keeps the full 16-bit range."""
    bgr = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if bgr is None:
        raise FileNotFoundError(path)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 65535.0
    return rgb


def find_horizon(lum, percentile=5, drop_factor=4.0):
    """Rough horizon detection: looks for the row where the 5th
    percentile of brightness collapses (tree silhouettes go black while
    the sky stays bright). A debugging aid only - in Fusion/Resolve you
    do this by hand with a Power Window."""
    row_p = np.percentile(lum, percentile, axis=1)
    baseline = np.median(row_p[: len(row_p) // 3])
    for y in range(len(row_p) // 3, len(row_p)):
        if row_p[y] < baseline / drop_factor:
            return y
    return len(row_p)


def build_gradient_model(sky_rgb, downsample=24, median_k=5, blur_sigma=6):
    """Core of AstroGradient: downsample (acts like a box blur and kills
    most stars through averaging alone) -> median (clears the remaining
    star residue) -> Gaussian (smooths) -> scale back up.

    This is the answer to the open question from macros/README.md:
    "Is resize-small -> blur -> resize-large faster/smoother than a
    direct large-radius blur?" - Yes, clearly: a direct Gaussian with
    sigma ~150px on 24 MP takes orders of magnitude longer than this
    path, which ran in under 2 seconds at downsample=24."""
    h, w = sky_rgb.shape[:2]
    sw, sh = max(1, w // downsample), max(1, h // downsample)
    small = cv2.resize(sky_rgb, (sw, sh), interpolation=cv2.INTER_AREA)
    if median_k > 1:
        u16 = np.clip(small * 65535, 0, 65535).astype(np.uint16)
        u16 = cv2.medianBlur(u16, median_k)
        small = u16.astype(np.float32) / 65535.0
    if blur_sigma > 0:
        small = cv2.GaussianBlur(small, (0, 0), blur_sigma)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)


def subtract_gradient(rgb, horizon_y, downsample=24, median_k=5,
                       blur_sigma=6, pedestal_fraction=0.35):
    """Applies the gradient model to the sky region only (rows
    0:horizon_y) and leaves the foreground untouched - exactly the
    behaviour achieved in Resolve through a Power Window or a mask on
    the Fusion macro input."""
    corrected = rgb.copy()
    sky = rgb[:horizon_y]
    model = build_gradient_model(sky, downsample, median_k, blur_sigma)
    pedestal = model.mean() * pedestal_fraction
    corrected[:horizon_y] = np.clip(sky - model + pedestal, 0, None)
    return corrected, model


def star_opening(rgb, k, strength=1.0):
    """Core of AstroStarReduce: a morphological opening (minimum filter,
    then maximum filter of the same window size) shrinks bright points
    while leaving large-scale structure largely in place. cv2.erode
    = rank 0 (minimum), cv2.dilate = rank 1 (maximum) in Fusion terms."""
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    u16 = np.clip(rgb * 65535, 0, 65535).astype(np.uint16)
    eroded = cv2.erode(u16, kernel)
    opened = cv2.dilate(eroded, kernel).astype(np.float32) / 65535.0
    if strength >= 1.0:
        return opened
    return rgb * (1.0 - strength) + opened * strength


def arcsinh_preview(rgb, s=400.0):
    """For display only - identical formula to AstroStretch.dctl in
    arcsinh mode, so that preview images stay comparable."""
    st = np.clip(np.arcsinh(s * rgb) / np.arcsinh(s), 0, 1)
    return (st * 255).astype(np.uint8)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: prototype_astro_macros.py <linear_16bit.tiff>")
        sys.exit(1)

    rgb = load_linear_tiff(sys.argv[1])
    lum = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    horizon_y = find_horizon(lum)
    print(f"Image size: {rgb.shape[1]}x{rgb.shape[0]}  horizon at y={horizon_y}")

    t0 = time.time()
    corrected, model = subtract_gradient(rgb, horizon_y)
    print(f"AstroGradient model built in {time.time()-t0:.2f}s")

    cv2.imwrite(
        "preview_gradient_corrected.png",
        cv2.cvtColor(arcsinh_preview(corrected), cv2.COLOR_RGB2BGR),
    )

    reduced = star_opening(corrected, k=3, strength=0.4)
    cv2.imwrite(
        "preview_star_reduced.png",
        cv2.cvtColor(arcsinh_preview(reduced), cv2.COLOR_RGB2BGR),
    )
    print("Preview images written.")
