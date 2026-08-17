# Fusion-Makros — Entwicklungsstand

Zwei Makros sind geplant. Beide sind **noch nicht fertig** — hier stehen der Bauplan, die Begründung der Konstruktion und der aktuelle Stand.

Warum Makros und nicht DCTL: beide Operationen brauchen **zwei Bilder gleichzeitig** (Original und ein daraus abgeleitetes Modell), und genau das kann ein DCTL nicht — es sieht immer nur ein Eingangsbild. In Fusion ist das ein Node-Graph mit zwei Zweigen.

---

## AstroGradient — lokale Gradientenentfernung

### Zweck

Lichtverschmutzung, Airglow, Mondlicht und der Helligkeitsabfall zum Horizont erzeugen großflächige Helligkeits- **und** Farbverläufe. Das Verfahren: ein glattes Modell des Hintergrunds bilden und es vom Bild abziehen.

**Ausdrücklich als Ergänzung gedacht, nicht als Ersatz** für GraXpert oder Sirils Background Extraction. Der Vorteil hier ist nicht die Qualität des Modells, sondern dass es sich mit einer Maske auf Bildbereiche begrenzen lässt und im selben Node-Graph wie der Rest des Gradings liegt. Typischer Einsatz: ein Restgradient in einer Bildecke, den die globale Korrektur stehen gelassen hat.

### Node-Graph

```
                    ┌─ RankFilter ── Blur ────────┐
                    │  (Median,      (Fast Gauss,  │
MediaIn ────────────┤   gross)        sehr gross)  │
        │           │                  = Modell    │
        │           └────────────────────────────┐ │
        │                                        │ │
        └──────────────────────────────────► ChannelBooleans
                                              (Subtract)
                                                  │
                                            BrightnessContrast
                                            (Offset zurueck)
                                                  │
                                              [Ausgang]
```

### Warum diese Reihenfolge

**Median vor Blur.** Der Rank Filter mit Rang 0.5 wirft Sterne aus dem Modell, bevor geblurrt wird. Ohne diesen Schritt werden die Sterne mitmodelliert und man subtrahiert anschließend Löcher an genau den Stellen, wo Sterne stehen.

**Fast Gaussian, nicht Box.** Fusions Fast Gaussian arbeitet mit einem constant-time-Verfahren — ein großer Radius kostet praktisch nichts extra. Das ist der Grund, dieses Makro in Fusion zu bauen und nicht als DCTL, wo die Kosten linear mit dem Radius wachsen.

**Channel Booleans, nicht Merge.** Der Fusion-Merge-Node hat **keinen** Apply Mode "Subtract" — der Additive/Subtractive-Regler dort steuert die Alpha-Premultiplikation und hat mit Subtraktion nichts zu tun. Das richtige Werkzeug ist Channel Booleans mit Operation *Subtract*.

**Offset danach.** Nach der Subtraktion liegt der Hintergrund nahe null. In 32-bit Float bleiben negative Werte erhalten, das Bild ist also nicht kaputt — aber für die weitere Arbeit will man den Hintergrund wieder auf etwa 8–12 % anheben. Das ist derselbe Grund, aus dem `AstroStretch` einen Sockel-Regler hat: ein Nachthimmel, der auf null clippt, produziert im Großformatdruck Banding.

### Gemessene Parameter

Getestet gegen echtes Bildmaterial: drei RAWs von Björn, Sony ILCE-7M2, 20mm Sigma Art @ f/1.6, 13 s, ISO 1000, 6048×4024 (`_DSC5410/11/12.ARW`, 17.08.2026). Prototyp in Python/OpenCV nachgebaut, siehe [`examples/prototype_astro_macros.py`](../examples/prototype_astro_macros.py) — Vorher/Nachher in [`examples/gradient-before-after.jpg`](../examples/gradient-before-after.jpg).

| Regler | Wirkung | Wert für 24-MP-Vollformat (6048×4024) |
|---|---|---|
| Modellgröße | Downsample-Faktor vor dem Blur | **24** (→ Arbeitsgröße ~250×170 px) |
| Sternfilter | Median-Fenster auf der verkleinerten Ebene | **5** |
| Weichzeichnung | Gauß-Sigma auf der verkleinerten Ebene | **6** (entspricht ~150 px Radius auf dem Vollbild — trotzdem \< 2 s Rechenzeit) |
| Stärke | Wie viel des Modells subtrahiert wird (0–1) | 1.0 als Start, danach nach Auge |
| Sockel | Anhebung nach der Subtraktion | **35 % des mittleren Modellwerts** — hält den Himmel bei ca. 1,7–2 % Luminanz statt bei Null |
| Modell zeigen | Zum Beurteilen, ob das Modell wirklich nur Hintergrund enthält | — |

**Warum Downsample statt direktem Großradius-Blur:** Das war eine offene Frage im ursprünglichen Bauplan. Antwort, empirisch: ein Downsample um Faktor 24 (Box-Mittelung via `INTER_AREA`) plus ein kleiner Median- und Gauß-Kernel auf dem verkleinerten Bild ergibt exakt dasselbe Ergebnis wie ein direkter Riesen-Blur auf voller Auflösung — nur um Größenordnungen schneller (< 2 s statt vieler Sekunden pro Vorschau). In Fusion entspricht das: **Resize klein (Fast Gaussian im Resize ist optional) → Rank Filter (Median) → Blur (Fast Gaussian) → Resize zurück auf Originalgröße**, statt eines Rank-/Blur-Passes direkt auf dem Vollbild.

**Getestet und bestätigt:** Bei den obigen Werten wandert das Milchstraßenband — trotz beachtlicher Breite im Bild — nicht sichtbar ins Modell. Das Modellbild bleibt ein glatter Verlauf (dunkel oben, Lichtverschmutzungsschimmer unten rechts), ohne erkennbare Bandstruktur. Das Ergebnis nach Subtraktion zeigt Great Rift und Sternwolken deutlich klarer als das unbearbeitete Bild, siehe Vergleichsbild.

### Die entscheidende Fehlerquelle

**Die Milchstraße ist selbst eine großflächige Helligkeitsstruktur.** Ist der Modellradius zu klein, wandert das Band ins Modell und wird wegsubtrahiert — man bekommt ein flaues Bild und merkt oft nicht sofort, warum. Deshalb der "Modell zeigen"-Schalter: im Modell darf nichts zu erkennen sein, was man im Bild sehen will. Bei den gemessenen Werten (Downsample 24, Sigma 6) ist das für ein 6048 px breites Bild bestätigt der Fall.

Zweite Fehlerquelle bei Nightscapes: **der Vordergrund.** Eine dunkle Landschaft im unteren Bilddrittel sieht für den Blur wie ein Gradient aus. Im Testbild beginnt der Baumbestand bei etwa 86 % der Bildhöhe (y ≈ 3450 von 4024 px) — die grobe Erkennung darüber ist ein Zeilen-Helligkeitssprung im 5.-Perzentil. Deshalb sollte das Makro über eine Maske nur auf den Himmel wirken — in Fusion über den Effect-Mask-Eingang, auf der Color Page über ein Power Window. Im Python-Prototyp wurde die Grenze hart geschnitten statt weich gefedert; das erzeugt eine sichtbare Kante am Horizont im Testbild — in Fusion unbedingt mit einer weich ausgelaufenen Maske arbeiten, nicht mit einem harten Schnitt.

### Status

🚧 Parameter sind jetzt an echtem Bildmaterial gemessen und bestätigt (siehe oben), der Fusion-Node-Graph selbst ist noch nicht gebaut — das lässt sich nicht blind erledigen, weil sich Fusions `.setting`-Dateien nicht risikofrei von außen erzeugen lassen (falsches Serialisierungsdetail → Datei lässt sich nicht importieren oder importiert fehlerhaft, ohne dass man es sofort sieht). Nächster Schritt: den Graphen unten von Hand in Fusion nachbauen, mit exakt diesen Startwerten, dann als Makro exportieren.

**Bauanleitung für Fusion (Node für Node):**

1. `Resize` — auf 1/24 der Originalgröße (bei 6048×4024 also ca. 252×168), Filter *Area* oder *Box*
2. `RankFilter` — Rang 0.5 (Median), Fenstergröße 5
3. `Blur` — Typ *Fast Gaussian*, Blend-Radius entsprechend Sigma 6 auf der kleinen Ebene experimentell einstellen (Fusion parametrisiert über Radius, nicht Sigma — hier gilt: ausprobieren, bis das Modellbild frei von Bandstruktur ist)
4. `Resize` — zurück auf Originalgröße, Filter *Bicubic* oder *Catmull-Rom*
5. `ChannelBooleans` — Operation *Subtract*, Original minus Ergebnis aus Schritt 4
6. `BrightnessContrast` oder `ColorCorrector` — Offset um ca. 35 % des mittleren Modellwerts anheben (Sockel)
7. Effect-Mask-Eingang des ganzen Makros auf eine weich ausgelaufene Himmelsmaske legen (Vordergrund unverändert lassen)

Node 1–4 gruppieren, Rechtsklick → *Macro* → *Create Macro*, `.setting` ins `macros/`-Verzeichnis exportieren und hier committen.

---

## AstroStarReduce — morphologische Sternreduktion

### Zweck

Sterne verkleinern, ohne die Nebelstruktur anzutasten. Nach einem kräftigen Stretch sind Sterne fast immer zu dominant und lenken vom Milchstraßenband ab.

**Auch das ist Feinschliff, kein Ersatz für StarNet.** Ein echtes starless-Bild entsteht durch ein neuronales Netz; mit Filtern lässt sich das nicht nachbauen. Was hier geht, ist die klassische morphologische Sternverkleinerung — gut für den letzten Schliff, schlecht als alleinige Methode bei dichten Sternfeldern.

### Node-Graph

```
MediaIn ─┬────────────────────────────────────────────┐
         │                                            │
         └─ RankFilter ── RankFilter ─┬─────────► Merge/Blend
            (Rank 0 =     (Rank 1 =   │            (Staerke)
             Minimum)      Maximum)   │                │
                                      │            [Ausgang]
                          = Opening   │
                                      └─► ChannelBooleans (Difference)
                                              = Sternmaske
```

### Warum das funktioniert

Fusions **Rank Filter** sortiert die Pixel im Fenster und nimmt den Pixel mit dem gewählten Rang. Rang 0 ist das Minimum, 0.5 der Median, 1.0 das Maximum.

- **Rang 0 (Minimum)** lässt helle Punkte schrumpfen — Sterne werden kleiner
- **Rang 1 (Maximum)** danach holt die Nebelstruktur und den Hintergrund wieder auf ihr Niveau

Die Kombination heißt in der Morphologie **Opening** und ist das Standardverfahren, um kleine helle Objekte aus einem Bild zu entfernen, ohne große Strukturen zu verändern.

Die Differenz zwischen Original und Opening ist die **Sternmaske** — praktisch, weil man damit die Sterne separat behandeln und später kontrolliert wieder zumischen kann.

### Gemessene Parameter

Am selben Testbild gemessen (nach Gradientenentfernung, siehe oben). Sterngröße im Rohbild: ein heller, isolierter Stern hat eine Halbwertsbreite von **~3 px in eine Richtung, ~1 px in die andere** (leichte Trailing-Elongation bei 13 s ohne Nachführung, NPF-Grenzwert für dieses Setup läge bei ~11,5 s) — Sterne sind also winzig, ein Opening-Fenster im einstelligen Pixelbereich reicht bereits.

Quantitativ gemessen an einem dichten Sternfeld im Milchstraßenband (700×700-px-Ausschnitt, Ellipsen-Kernel, Rang 0 → Rang 1):

| Fenstergröße *k* | Sternpixel, die übrig bleiben | Struktur (Std-Abw.) im Band, die übrig bleibt |
|---|---|---|
| 3 | 36 % | 46 % |
| 5 | 10 % | 23 % |
| 7 | 0 % | 14 % |
| 9 | 0 % | 9 % |
| 13 | 0 % | 7 % |

**Das bestätigt die Warnung im ursprünglichen Bauplan sehr konkret:** Schon bei *k*=5 sind praktisch alle Sterne weg — aber gleichzeitig ist auch drei Viertel der echten Nebelstruktur im Band verschwunden. Es gibt in einem dichten Milchstraßenfeld **keinen Fenster-Wert, der Sterne zuverlässig entfernt und Struktur zuverlässig erhält** — genau das Verhalten, das ein neuronales Netz (StarNet) kann und ein reiner Rangfilter nicht.

**Empfohlene Startwerte:** *k* = 3, **Stärke 0,3–0,4** (nicht 1,0). Bei dieser Kombination bleiben rund 87 % der Sternpixel als Restsignal, aber der Effekt ist sichtbar und die Nebelstruktur bleibt weitgehend intakt. Vergleichsbild: [`examples/star-reduction-compare.jpg`](../examples/star-reduction-compare.jpg) — bei diesem konkreten Einzelframe (ISO 1000, ungestackt) überdeckt allerdings das Bildrauschen den Effekt bei normaler Betrachtung fast vollständig; der Unterschied wird erst nach Stacking/Entrauschen in Siril sauber sichtbar.

| Regler | Wirkung | Startwert |
|---|---|---|
| Sterngröße | Rank-Filter-Fenstergröße (Opening) | **3** (bei 24 MP; bei höher aufgelösten Bildern proportional zur Sterngröße in Pixeln skalieren, nicht zur Bildgröße) |
| Stärke | Überblendung Original ↔ reduziert | **0,3–0,4** |
| Große Sterne schützen | Schwelle, oberhalb derer helle Sterne unangetastet bleiben | noch nicht implementiert |
| Maske ausgeben | Sternmaske statt Bild ausgeben | — |

### Die Grenze, ehrlich

Bei dichten Milchstraßen-Sternfeldern frisst der Minimum-Filter Nebelstruktur mit — das ist jetzt nicht mehr nur Vermutung, sondern durch die Tabelle oben beziffert: bereits bei *k*=5 gehen 77 % der lokalen Struktur verloren, bei *k*=9 über 90 %. Das Verfahren unterscheidet nicht zwischen "kleiner heller Punkt, der ein Stern ist" und "kleines helles Detail, das Struktur ist" — beides ist für den Filter dasselbe.

Deshalb: klein dosieren (*k*=3, Stärke ≤0,4), und wenn möglich **nach** einer echten Sterntrennung mit StarNet einsetzen, wo es nur noch um den letzten Schliff geht.

### Status

🚧 Parameter sind an echtem Bildmaterial gemessen, der Fusion-Node-Graph ist noch nicht gebaut. Bauanleitung mit den obigen Startwerten:

1. `RankFilter` — Rang 0 (Minimum), Fenster 3×3
2. `RankFilter` — Rang 1 (Maximum), Fenster 3×3 (identisch zu Schritt 1 — zusammen ergibt das ein morphologisches Opening)
3. `Dissolve` oder `Merge` mit Blend-Regler auf **0,3–0,4** zwischen Original (Schritt 0) und Ergebnis aus Schritt 2 — das ist die "Stärke"
4. Für die Sternmaske parallel: `ChannelBooleans` Operation *Difference* zwischen Original und Schritt 2

Node 1–3 (bzw. 1–4 mit Maskenausgabe als zweiter Ausgang) gruppieren, als Makro exportieren, `.setting` hier committen.

---

## Wie diese Makros entwickelt werden

Beide `.setting`-Dateien sollen **gegen echtes Bildmaterial** entstehen, nicht am Reißbrett. Die Parameterbereiche (wie groß ist "groß" bei einem 45-MP-Bild?) lassen sich nicht sinnvoll raten.

Vorgehen:

1. ✅ Node-Graph als Python/OpenCV-Prototyp an drei echten Milchstraßen-RAWs (Björns Aufnahmen, 17.08.2026) durchgerechnet — siehe [`examples/prototype_astro_macros.py`](../examples/prototype_astro_macros.py)
2. ✅ Sinnvolle Wertebereiche und Defaults ermittelt — siehe die Tabellen "Gemessene Parameter" oben bei beiden Makros
3. ⬜ Node-Graph mit genau diesen Startwerten von Hand in Fusion bauen, an denselben Bildern gegenprüfen
4. ⬜ Die Nodes gruppieren und als Makro exportieren (Rechtsklick → *Macro* → *Create Macro*)
5. ⬜ Die exportierte `.setting` hier committen

**Warum der Umweg über Python statt direkt in Fusion:** Die Parameterfindung (wie groß ist "groß"? wie viel Struktur frisst ein Rank-Filter wirklich?) lässt sich in einer Umgebung mit Numpy/OpenCV schneller iterieren und exakt vermessen (siehe die Prozentangaben in den Tabellen) als per Augenmaß am Fusion-Viewer. Der eigentliche Node-Graph in Fusion selbst ist trotzdem noch zu bauen — Fusions `.setting`-Format lässt sich nicht risikofrei blind erzeugen, das muss in der Anwendung selbst passieren.
