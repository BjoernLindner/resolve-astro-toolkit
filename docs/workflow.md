# Wo im Workflow diese Werkzeuge hingehören

Dieses Toolkit ist ein Baustein, kein Weg. Damit die Werkzeuge das tun, was sie sollen, müssen sie an der richtigen Stelle stehen — und die Reihenfolge ist bei Astro nicht Geschmackssache, sondern folgt aus der Mathematik.

---

## Die Gesamtkette

```
1  AUFNAHME
   Mehrere Himmelsframes, moeglichst separate Vordergrundframes

2  VORVERARBEITUNG            Siril / Seti Astro Suite Pro
   Kalibrierung (Darks/Flats/Bias)
   Registrierung + Stacking   ← Resolve kann das nicht
   Background Extraction      ← global, gehoert hierhin
   Farbkalibrierung (SPCC)
   Sternentrennung (StarNet2)
   → 16-bit oder 32-bit TIFF, linear

3  GRADING                    DaVinci Resolve Studio  ← dieses Toolkit
   CST → linear
   AstroStretch
   AstroGradient (lokale Restkorrektur)
   AstroSCNR
   AstroStarReduce
   + Resolves eigene Werkzeuge
   CST → Adobe RGB
   → 16-bit TIFF

4  DRUCKVORSTUFE              Affinity Photo / Photoshop / darktable
   ICC-Softproof              ← Resolve kann das nicht
   Output-Sharpening
   Dithering gegen Banding
```

Zwei Schritte kann Resolve nicht und wird es nicht können: **Stacking mit Registrierung** und **ICC-Softproofing auf Druckerprofile**. Beides ist keine Bequemlichkeitsfrage, sondern eine Architekturfrage — siehe [grenzen.md](grenzen.md).

---

## Die Node-Kette in Resolve

Ein Vorschlag, der sich aus der Reihenfolgelogik ergibt:

| Node | Werkzeug | Warum hier |
|---|---|---|
| 01 | **CST** Input → DaVinci WG / Linear | Alles Folgende setzt lineare Daten voraus |
| 02 | Spatial NR *(Studio)* | Chroma-Rauschen früh weg, solange es noch gaußförmig ist |
| 03 | **AstroGradient** | Restgradienten entfernen, **bevor** gestretcht wird |
| 04 | **AstroStretch** (Arcsinh) | Der erste, kräftige Stretch |
| 05 | **AstroStretch** (MTF, sanft) | Feinabstimmung — zwei sanfte Stretches schlagen einen aggressiven |
| 06 | **AstroSCNR** | Grünstich, der jetzt erst sichtbar geworden ist |
| 07 | HDR-Palette / Log Wheels | Eigene Zone auf die Milchstraßen-Luminanz legen |
| 08 | Lum vs Sat | Sättigung in den Schatten senken → Farbrauschen im Himmel |
| 09 | Hue vs Sat | Blau/Cyan anheben, Orange der Lichtverschmutzung senken |
| 10 | **AstroStarReduce** | Sterne zurücknehmen, nachdem der Kontrast steht |
| 11 | Power Window / Magic Mask | Himmel und Vordergrund trennen, Vordergrund separat behandeln |
| 12 | Blur/Sharpen | Schärfen zuletzt |
| 13 | **CST** Linear → Adobe RGB | Ausgabefarbraum |

---

## Warum diese Reihenfolge

### Gradienten vor dem Stretch

Ein Gradient ist im linearen Zustand eine einfache, glatte, additive Funktion. Nach dem Stretch ist er nichtlinear verzerrt und lässt sich mit einem glatten Modell nicht mehr sauber beschreiben.

Dazu kommt ein zweiter Effekt: Der Stretch verstärkt den Gradienten mit. Man wird dann gezwungen, den Schwarzpunkt so weit anzuheben, dass die helle Bildecke nicht überstrahlt — und verliert dabei die dunkle Ecke.

### Rauschreduktion früh, aber Luminanz-NR spät

Zwei Schulen, beide mit Argument. Chroma-Rauschen behandelt man früh und linear, weil es dort noch gaußförmig ist und weil Farbrauschen praktisch keine Information trägt. Luminanz-Rauschreduktion dagegen erst nach dem Stretch — vorher sieht man schlicht nicht, was man tut.

Und immer maskiert: helle, signalstarke Regionen schützen, nur die dunklen SNR-armen Bereiche glätten. Unmaskierte Luminanz-NR ist die Hauptursache für den Plastik-Look.

### SCNR nach dem Stretch

Auf linearen Daten ist der Grünüberschuss noch klein und SCNR bringt wenig. Er entsteht sichtbar erst durch den Stretch, weil die Bayer-Matrix doppelt so viele Grünpixel hat und die Verstärkung das mitzieht.

### Sternreduktion nach dem Kontrast

Andersherum bläht jede Kontraststeigerung die eben verkleinerten Sterne wieder auf, und man bekommt zusätzlich dunkle Ringe um helle Sterne.

### Schärfen ganz zuletzt

Jede Skalierung zerstört die Wirkung vorheriger Schärfung. Output-Sharpening muss auf die finale Pixelgröße und das Papier abgestimmt sein — und gehört deshalb eigentlich nicht mehr nach Resolve, sondern in die Druckvorstufe.

### Schwarzpunkt nie clippend

Der Nachthimmel ist nie völlig schwarz. Ein auf null geclippter Hintergrund verliert nicht nur Struktur, er produziert im Großformatdruck sichtbares Banding, weil die Quantisierungsstufen in einer glatten dunklen Fläche über 84 cm Bildbreite auseinandergezogen werden.

Zielwert: Hintergrund bei etwa **8–15 %**. `AstroStretch` hat dafür einen Sockel-Regler und eine Clip-Warnung, die rot anzeigt, wo der Schwarzpunkt gerade Information vernichtet.

---

## Ein Wort zum Vordergrund

Bei Nightscapes ist der Vordergrund fast immer der Flaschenhals — er liegt typisch 4–8 EV unter dem Himmel. Kein Werkzeug in diesem Toolkit repariert das.

Was hilft, ist eine **getrennte Behandlung**: den Vordergrund als eigenen Zweig im Node-Graph entwickeln, mit anderer Farbtemperatur, aufgehellten Schatten und deutlich stärkerer Rauschreduktion — und über eine Maske einblenden.

Für die Maske: bei weichen Horizonten ein Gradient-Power-Window, bei Silhouetten (Bäume, Felskanten) besser die Magic Mask oder ein kanalbasierter Qualifier. Eine weich gefederte Kante ist bei Nadelbäumen fatal und erzeugt einen sichtbaren Halo.

Und alle Gradientenwerkzeuge müssen vom Vordergrund ferngehalten werden. Eine dunkle Landschaft sieht für ein Blur-Modell wie ein Gradient aus.
