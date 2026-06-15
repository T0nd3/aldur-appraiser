# Aldur Appraiser

A **passive, read-only** overlay for Path of Exile 2 (league *Runes of Aldur*). It reads the
*Runeshape Combinations* panel of the Ezomyte Remnant via screen capture, prices each reward
option, and highlights the most valuable one — as a decision aid *before* you pick.

> **Use at your own risk.** This tool only reads the screen and draws its own overlay. It does
> **not** touch the game client (no clipboard, no input injection, no memory reading). That said,
> GGG's third-party policy is strict about automation — there is no official endorsement.

## Status

Pricing, OCR, panel detection, live capture (mss on Windows/X11, xdg-desktop-portal +
PipeWire on Wayland), the capture→detect→OCR→price loop, and a Qt corner-HUD overlay are
implemented. Cross-platform (Windows / Linux). Live in-game tuning is ongoing.

## Install

### Prebuilt binary (no Python needed) — Windows & macOS

Download from the [Releases](../../releases) page and run it:

- **Windows:** `aldur-appraiser.exe` — double-click (SmartScreen → "More info" →
  "Run anyway" the first time).
- **macOS (Apple Silicon):** `aldur-appraiser` — first launch is blocked by
  Gatekeeper (right-click → Open, or `xattr -d com.apple.quarantine ./aldur-appraiser`),
  and grant **Screen Recording** permission in System Settings → Privacy.

Capture on Windows/macOS uses `mss` (no extra setup). Run PoE2 in
borderless/windowed fullscreen. Linux users: use the setup script below (the
Wayland capture path needs the distro's GStreamer).

### From source (recommended on Linux)

The cross-platform setup script creates a venv, installs everything, and checks
your platform's capture prerequisites:

```bash
python scripts/setup.py
python scripts/setup.py --check     # only re-run the environment checks
```

<details>
<summary>Manual install</summary>

```bash
python -m venv .venv
. .venv/bin/activate                # Windows: .venv\Scripts\activate
pip install -e ".[vision,overlay]"  # pricing + RapidOCR + OpenCV + mss + Qt overlay (wheels)
pip install -e ".[tesseract]"       # optional OCR fallback (needs the tesseract binary)
```
</details>

### Screen capture per platform

- **Windows / macOS / Linux-X11:** uses `mss` (bundled wheel) — nothing extra.
  On macOS grant Screen Recording permission to your terminal.
- **Linux / Wayland:** `mss` can't read the screen, so capture goes through
  xdg-desktop-portal + PipeWire. This needs the distro's GStreamer + PyGObject
  (not pip-installable). The setup script detects and names the packages, e.g.
  Fedora/Bazzite: `gstreamer1-plugin-pipewire python3-gobject gstreamer1-plugins-good`
  (on atomic, layer them with `rpm-ostree install …` or use a distrobox).
  First run shows a one-time screen-share dialog; the choice is remembered.

## Usage

```bash
appraiser run                       # live overlay HUD (capture + detect + appraise)
appraiser run --inline              # per-row value chips next to each option (with the base-currency icon)
appraiser run --console             # plain console output instead of an overlay
appraiser table --top 15            # dump the live price table
appraiser price "Divine Orb" 3      # value a single reward option
appraiser price "divin orb" 3 --fuzzy
appraiser image panel.png           # appraise rewards from a screenshot
appraiser capture-test              # grab one frame to verify screen capture
```

## Notes

- **Run PoE2 in borderless/windowed fullscreen**, not exclusive fullscreen — exclusive mode
  yields a black capture frame on many Linux setups.
- Prices come from [poe2scout](https://poe2scout.com); cached ~20 min, never fetched per frame.
- Only **currency-vs-currency** choices are ranked reliably. Non-currency rewards (gear, gems,
  thin-market league items) are shown as unknown rather than guessed.
- Calibrate on an **English** client (OCR/snap dictionary).
