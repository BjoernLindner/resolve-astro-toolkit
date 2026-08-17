#!/usr/bin/env python3
"""
Prototyp-Skript fuer AstroGradient und AstroStarReduce
========================================================

Simuliert die geplanten Fusion-Node-Graphen (siehe macros/README.md) in
Python/OpenCV, um an echtem Bildmaterial sinnvolle Parameterbereiche zu
ermitteln, BEVOR die Node-Graphen von Hand in Fusion gebaut werden.

Getestet gegen: Sony ILCE-7M2, 20mm F1.4 Sigma Art @ f/1.6, 13s, ISO 1000,
6048x4024 (drei Frames derselben Milchstrassen-Szene, 17.08.2026).

Die Ergebnisse dieses Laufs stehen in macros/README.md unter
"Gemessene Parameter". Dieses Skript ist keine Produktionssoftware,
sondern die Werkbank, mit der die Fusion-Makros kalibriert wurden.

Voraussetzungen: numpy, opencv-python. RAW-Dekodierung separat mit
dcraw, siehe Kommentar unten.

    dcraw -v -T -6 -w -o 0 -4 -q 3 -W dein_bild.ARW
    # -o 0 -4  = linear, keine Gammakurve (Kameraraum, kein sRGB)
    # -W       = kein Auto-Bright (sonst verfaelscht das die linearen Werte)
    # -q 3     = AHD-Demosaicing
    # -T -6    = TIFF, 16-bit
"""

import numpy as np
import cv2
import time


def load_linear_tiff(path):
    """Laedt ein von dcraw erzeugtes 16-bit-TIFF. WICHTIG: PIL liest
    16-bit-TIFFs oft fälschlich als 8-bit RGB ein - deshalb hier cv2
    mit IMREAD_UNCHANGED, das den vollen 16-bit-Bereich erhaelt."""
    bgr = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if bgr is None:
        raise FileNotFoundError(path)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 65535.0
    return rgb


def find_horizon(lum, percentile=5, drop_factor=4.0):
    """Grobe Horizonterkennung: sucht die Zeile, ab der das 5.-Perzentil
    der Helligkeit einbricht (Baumsilhouetten werden schwarz, der Himmel
    bleibt hell). Nur ein Debug-Hilfsmittel - in Fusion/Resolve macht
    man das per Power Window von Hand."""
    row_p = np.percentile(lum, percentile, axis=1)
    baseline = np.median(row_p[: len(row_p) // 3])
    for y in range(len(row_p) // 3, len(row_p)):
        if row_p[y] < baseline / drop_factor:
            return y
    return len(row_p)


def build_gradient_model(sky_rgb, downsample=24, median_k=5, blur_sigma=6):
    """AstroGradient-Kern: Downsample (wirkt wie Box-Blur + killt die
    meisten Sterne schon durch Mittelung) -> Median (raeumt Sternreste
    weg) -> Gauss (glaettet) -> zurueckskalieren.

    Das ist die Antwort auf die offene Frage aus macros/README.md:
    "Ist Resize-klein -> Blur -> Resize-gross schneller/glatter als ein
    direkter Grossradius-Blur?" - Ja, deutlich: ein direkter Gauss mit
    Sigma ~150px auf 24 MP dauert um Groessenordnungen laenger als
    dieser Weg, der bei downsample=24 in unter 2 Sekunden lief."""
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
                       blur_sigma=6, sockel_fraction=0.35):
    """Wendet das Gradientenmodell nur auf den Himmelsbereich an (Zeilen
    0:horizon_y) und laesst den Vordergrund unangetastet - genau das
    Verhalten, das in Resolve ueber ein Power Window / eine Maske am
    Fusion-Makro-Eingang erreicht wird."""
    corrected = rgb.copy()
    sky = rgb[:horizon_y]
    model = build_gradient_model(sky, downsample, median_k, blur_sigma)
    sockel = model.mean() * sockel_fraction
    corrected[:horizon_y] = np.clip(sky - model + sockel, 0, None)
    return corrected, model


def star_opening(rgb, k, strength=1.0):
    """AstroStarReduce-Kern: morphologisches Opening (Minimum-Filter,
    dann Maximum-Filter derselben Fenstergroesse) verkleinert helle
    Punkte, laesst grossflaechige Struktur weitgehend stehen. cv2.erode
    = Rank 0 (Minimum), cv2.dilate = Rank 1 (Maximum) in Fusion-Sprache."""
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    u16 = np.clip(rgb * 65535, 0, 65535).astype(np.uint16)
    eroded = cv2.erode(u16, kernel)
    opened = cv2.dilate(eroded, kernel).astype(np.float32) / 65535.0
    if strength >= 1.0:
        return opened
    return rgb * (1.0 - strength) + opened * strength


def arcsinh_preview(rgb, s=400.0):
    """Nur fuer die Anzeige - identische Formel wie AstroStretch.dctl
    im Arcsinh-Modus, damit Vorschaubilder vergleichbar sind."""
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
    print(f"Bildgroesse: {rgb.shape[1]}x{rgb.shape[0]}  Horizont bei y={horizon_y}")

    t0 = time.time()
    corrected, model = subtract_gradient(rgb, horizon_y)
    print(f"AstroGradient-Modell gebaut in {time.time()-t0:.2f}s")

    cv2.imwrite(
        "preview_gradient_corrected.png",
        cv2.cvtColor(arcsinh_preview(corrected), cv2.COLOR_RGB2BGR),
    )

    reduced = star_opening(corrected, k=3, strength=0.4)
    cv2.imwrite(
        "preview_star_reduced.png",
        cv2.cvtColor(arcsinh_preview(reduced), cv2.COLOR_RGB2BGR),
    )
    print("Vorschaubilder geschrieben.")
