# Installation

## Voraussetzungen

- **DaVinci Resolve Studio 18 oder neuer.** DCTL-Unterstützung ist Studio-exklusiv — die kostenlose Version hat weder einen DCTL-Eintrag im LUT-Menü noch den DCTL-OFX-Node.
- Eine GPU, die Resolve unterstützt. Die DCTLs werden je nach Plattform nach CUDA, OpenCL oder Metal übersetzt.

---

## DCTLs installieren

### 1. Den LUT-Ordner finden

Der verlässlichste Weg führt über Resolve selbst:

> **Project Settings → Color Management → "Open LUT Folder"**

Das öffnet den richtigen Ordner im Dateimanager. Die Pfade lauten normalerweise:

| System | Pfad |
|---|---|
| Windows | `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT\` |
| macOS | `/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT/` |
| Linux | `/home/resolve/LUT/` |

### 2. Dateien ablegen

Lege dort einen Unterordner `Astro` an und kopiere die `.dctl`-Dateien hinein. Der Unterordner ist optional, hält die Liste im Inspector aber übersichtlich.

### 3. Listen aktualisieren

Im selben Dialog auf **"Update Lists"** klicken. Ein Resolve-Neustart ist nicht nötig — das gilt auch nach jeder Änderung an einer `.dctl`-Datei, was den Entwicklungszyklus sehr angenehm macht.

### 4. Anwenden

> ⚠️ **Der häufigste Stolperstein:** Rechtsklick auf einen Node → *LUT* → DCTL funktioniert bei diesen Dateien **nicht**. Dieser Weg ist für DCTLs ohne Bedienelemente gedacht und kann keine Reglerwerte übergeben.

Der richtige Weg:

1. Color Page, einen Node auswählen (oder neu anlegen)
2. **OpenFX-Panel** öffnen (Symbol oben rechts)
3. Unter *ResolveFX Color* den Effekt **"DCTL"** auf den Node ziehen
4. Im Inspector unter *DCTL List* die gewünschte Datei auswählen

Die Regler erscheinen dann direkt darunter im Inspector.

### Wenn nichts auftaucht

- Pfad prüfen — der Ordner muss der sein, den "Open LUT Folder" öffnet
- Dateiendung prüfen: `.dctl`, nicht `.dctl.txt` (Windows blendet bekannte Endungen aus)
- Resolve einmal neu starten
- In den Preferences unter *General → LUT Locations* nachsehen, ob ein abweichender Ordner konfiguriert ist

---

## Farbmanagement

Das ist kein optionales Detail. **Der Stretch rechnet mit szenenlinearen Daten.** Auf Log-Daten wie DaVinci Intermediate, S-Log oder N-Log ist die Mathematik schlicht falsch — das Ergebnis sieht dann flau und in den Mitten seltsam aus, ohne dass sofort klar wird, warum.

Zwei Wege:

### Weg A — bequem

> Project Settings → Color Management
> - Color Science: **DaVinci YRGB Color Managed**
> - Timeline Color Space: **DaVinci WG / Linear**

### Weg B — kontrolliert (empfohlen zum Lernen)

> Project Settings → Color Management → Color Science: **DaVinci YRGB**

Und die Farbraumwechsel explizit als Nodes in die Kette bauen:

```
Node 1   Color Space Transform   Kamera/Input  →  DaVinci WG / Linear
Node 2   DCTL: AstroStretch
Node 3   ... weiteres Grading ...
Node n   Color Space Transform   DaVinci WG / Linear  →  Adobe RGB
```

Mehr Nodes, aber du siehst an jeder Stelle, in welchem Zustand die Daten sind. Für ein Projekt, bei dem die Reihenfolge über das Ergebnis entscheidet, ist das die bessere Wahl.

### Alternativ: nur um den Stretch herum

Wenn du ansonsten in DaVinci Intermediate arbeiten willst, reicht es, den Stretch einzuklammern:

```
CST: DaVinci Intermediate → Linear
DCTL: AstroStretch
CST: Linear → DaVinci Intermediate
```

---

## Fusion-Makros installieren

*(Sobald die Makros verfügbar sind.)*

Makros sind `.setting`-Dateien und gehören in den Macros-Ordner:

| System | Pfad |
|---|---|
| Windows | `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Fusion\Macros\` |
| macOS | `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Macros/` |
| Linux | `/opt/resolve/Fusion/Macros/` |

Nach einem Resolve-Neustart erscheinen sie in der Fusion Page unter **Effects Library → Tools → Macros**.

---

## Auflösung — wichtig für Großformatdruck

Nodes auf der Color Page rechnen in **Timeline-Auflösung**, nicht in Quellauflösung. Wenn deine Timeline auf HD steht und dein Bild 45 Megapixel hat, modellierst du Gradienten auf einem heruntergerechneten Bild und skalierst das Ergebnis wieder hoch.

Zwei Lösungen:

- **Photo Page (Resolve 21)** — verarbeitet an der Quellauflösung, unabhängig von der Timeline. Der bequeme Weg.
- **Timeline-Auflösung manuell** auf die volle Sensorauflösung setzen (Project Settings → Master Settings → Timeline Resolution → Custom).

In **Fusion** gilt eine eigene Regel: ein **einzelner Clip** läuft in voller Quellauflösung, ein **Fusion Clip** dagegen in Timeline-Auflösung. Für hochauflösende Arbeit also nie einen Fusion Clip anlegen.
