# Was dieses Toolkit bewusst nicht macht — und warum

Es wäre verlockend, alles in Resolve erledigen zu wollen. Ein Programm, ein Node-Graph, keine Dateiexporte zwischendurch. Diese Seite erklärt, warum das eine schlechte Idee ist, und wo genau die Grenze verläuft.

Die kurze Fassung:

> **Alles, was mehrere Bilder braucht oder eine globale Optimierung, gehört nicht nach Resolve. Alles, was pixelweise oder lokal arbeitet, kann Resolve — und manches sogar besser als die Alternativen.**

---

## Die technischen Grenzen der Erweiterungswege

Resolve lässt sich auf drei Arten erweitern. Jede hat eine harte Decke.

### DCTL

DCTLs sind GPU-Shader in C-ähnlicher Syntax. Anders als oft angenommen sind sie **nicht** auf Per-Pixel-Operationen beschränkt: es gibt eine zweite Signatur mit `__TEXTURE__`-Parametern, mit der sich über `_tex2D()` jedes beliebige Pixel des Bildes lesen lässt. Faltung, Blur, Median und Morphologie sind damit machbar.

Was ein DCTL **nicht** kann:

| Grenze | Folge |
|---|---|
| Nur **ein** Eingangsbild | Die Subtraktion `Bild − Modell` muss außerhalb passieren |
| Nur **ein** Frame | Bildmittelung ist unmöglich. Punkt. |
| Kein Multi-Pass innerhalb einer Datei | Mehrere Durchgänge = mehrere Nodes; Zwischenergebnisse lassen sich nicht zurückholen |
| **Keine globalen Reduktionen** | Keine Summe, kein Min/Max, kein Histogramm über das ganze Bild |
| Kein persistenter Speicher | Nichts lässt sich zwischen Pixeln oder Frames merken |

Die vierte Zeile ist die folgenreichste — dazu unten mehr.

### Fuse

Fuses sind Lua-Plugins für Fusion, JIT-kompiliert, ohne Compiler installierbar, mit Hot-Reload. Sie können alles, was DCTL kann, **plus** mehrere Bildeingänge, Multi-Pass, Zugriff auf beliebige Frames, GPU-Kernel und persistente Buffer über Frames hinweg.

Das ist der sinnvollste Erweiterungsweg, wenn man über DCTL hinaus muss. Er reicht für fast alles außer echter globaler Optimierung.

### OFX

Eigene OpenFX-Plugins in C++ sind möglich; Resolve bringt das SDK mit, inklusive Beispielen für wahlfreien Frame-Zugriff. Volle Freiheit, aber C++-Toolchain, GPU-Kernel in drei Sprachvarianten und kein Hot-Reload. Realistisch mehrere Wochen für das erste brauchbare Plugin.

Fremd-OFX-Plugins laufen nur in Resolve Studio.

---

## Die vier Dinge, die dieses Toolkit nicht versucht

### 1. Stacking und Registrierung

**Warum es scheitert:** Nicht am Mitteln — es existiert sogar ein fertiges freies `FrameAvg.fuse`, das korrekt über N Frames mittelt. Es scheitert an der **Registrierung**: Sterne zwischen Frames identifizieren, matchen, rotieren, entzerren.

Bei untracked Weitwinkelaufnahmen dreht sich das Sternfeld zwischen den Frames. Ohne Ausrichtung ist Mittelung wertlos — man bekommt Strichspuren statt Punkte.

**Wo es hingehört:** Siril macht das mit 2-Pass-Globalregistrierung, Sigma-Clipping-Rejection und Normalisierung. Kostenlos, ausgereift, gut dokumentiert.

**Und der eigentliche Punkt:** Stacking bringt bei Astro mehr als jeder Bearbeitungsschritt. Rauschen sinkt mit 1/√N — 16 Frames bedeuten rund 75 % weniger Rauschen, also etwa zwei Blendenstufen. Das ist nichts, was man in einem Grading-Programm nachträglich herausholt.

### 2. Echtes DBE / Background Extraction mit Sample-Punkten

**Warum es scheitert:** Ein richtiges DBE setzt Stützpunkte auf reinem Himmel, verwirft Ausreißer und fittet daraus ein globales Polynom oder eine RBF per Least-Squares. Das braucht eine **Reduktion über das gesamte Bild** — DCTL kann das prinzipiell nicht, ein Fuse nur mühsam, ein OFX-Plugin gut.

**Was hier stattdessen geht:** "Modell = stark geglättetes Bild, dann subtrahieren". Bei glatten Verläufen ist der Unterschied klein. Bei starker, unregelmäßiger Lichtverschmutzung deutlich.

**Wo es hingehört:** GraXpert (KI-basiert, kostenlos) oder Sirils RBF-Background-Extraction.

Deshalb heißt das Makro hier `AstroGradient` und nicht `AstroDBE` — es ist eine lokale Restkorrektur, kein Ersatz.

### 3. Echte Sternentrennung (starless)

**Warum es scheitert:** StarNet und StarXTerminator sind neuronale Netze. Ein Netz unterscheidet zwischen "kleiner heller Punkt, der ein Stern ist" und "kleines helles Detail, das Nebelstruktur ist". Ein Minimum-Filter kann das nicht — für ihn ist beides dasselbe.

Bei dichten Milchstraßen-Sternfeldern frisst morphologische Reduktion daher Struktur mit.

**Ein theoretischer Weg existiert:** Ein Fuse kann einen externen Python-Prozess mit einem ONNX-Modell starten und das Ergebnis zurücklesen — es gibt ein funktionierendes Vorbild dafür. Damit wäre StarNet in Fusion integrierbar. Das ist ein mehrwöchiges Projekt für eine Funktion, die als eigenständiges Programm bereits kostenlos existiert.

**Wo es hingehört:** StarNet2 CLI, kostenlos, aus Siril heraus aufrufbar.

### 4. ICC-Softproofing

**Warum es scheitert:** Resolves Farbmanagement ist durchgehend farbraum- und LUT-basiert, nicht ICC-basiert. Es gibt keine Möglichkeit, ein Papier-/Druckerprofil zu laden, keine Gamut-Warnung, keine Rendering Intents, keine Black Point Compensation. Auf macOS lassen sich Display-ICC-Profile für den Viewer nutzen — das ist Monitorkalibrierung, kein Output-Profiling.

Ein Workaround über ein aus dem ICC erzeugtes 3D-LUT existiert, ist aber nur eine Vorschau ohne Gamut-Warnung und ohne wählbaren Intent.

**Wo es hingehört:** Affinity Photo, Photoshop, Capture One oder darktable — als letzter Schritt vor dem Druck.

Bei dunklen Motiven ist das besonders wichtig: Black Point Compensation entscheidet, ob die Schatten differenziert bleiben oder unterhalb des Papier-Dmax gemeinsam zulaufen.

---

## Was Resolve dafür besser kann

Damit die Liste nicht einseitig wirkt — es gibt Gründe, überhaupt hier zu arbeiten:

- **32-bit Float durchgehend** auf der GPU, ohne Bittiefenverlust in der Kette
- **Node-Graph** statt Ebenenstapel: Verzweigungen, Outside-Nodes für automatisch invertierte Keys, Layer Mixer mit Composite Modes
- **HDR-Palette** mit frei definierbaren Zonen samt Falloff — man kann eine Zone exakt auf die Milchstraßen-Luminanz legen. Dafür gibt es in Astro-Software kein Gegenstück.
- **Lum vs Sat und Hue vs Sat** als Kurven — Sättigung in den Schatten senken ist gegen Farbrauschen im Himmel bemerkenswert wirksam
- **Magic Mask** für Landschaftsvordergründe, KI-basiert, funktioniert auf Einzelbildern
- **Power Windows** mit weicher Kantenkontrolle, präziser als die meisten Maskenwerkzeuge in Astro-Software
- **Color Warper** für die feine Trennung zwischen Milchstraßenfarbe und Hintergrundhimmel

Für Compositing von Himmel und Vordergrund und für das finale Grading ist Resolve den klassischen Astro-Werkzeugen tatsächlich überlegen. Das ist der Bereich, für den dieses Toolkit gedacht ist.
