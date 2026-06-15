# Aldur Appraiser

A **passive, read-only** overlay for Path of Exile 2 (league *Runes of Aldur*). It reads the
*Runeshape Combinations* panel of the Ezomyte Remnant via screen capture, prices each reward
option, and highlights the most valuable one — as a decision aid *before* you pick.

> **Use at your own risk.** This tool only reads the screen and draws its own overlay. It does
> **not** touch the game client (no clipboard, no input injection, no memory reading). That said,
> GGG's third-party policy is strict about automation — there is no official endorsement.

## Status

Phase 1 (pricing core) is implemented and runs game-independently on Windows and Linux.

## Install

The pricing core has no system dependencies (pure-Python wheels):

```bash
python -m venv .venv
. .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
```

The vision/overlay half (later phases) is an optional extra:

```bash
pip install -e ".[vision]"          # RapidOCR (primary, no system dep), OpenCV, mss
pip install -e ".[tesseract]"       # optional OCR fallback — requires the tesseract binary:
                                     #   Bazzite (atomic): via distrobox or an rpm-ostree layer
                                     #   Windows: UB-Mannheim installer + PATH
```

## Usage

```bash
appraiser table --top 15            # dump the live price table
appraiser price "Divine Orb" 3      # value a reward option
appraiser price "divin orb" 3 --fuzzy
```

## Notes

- **Run PoE2 in borderless/windowed fullscreen**, not exclusive fullscreen — exclusive mode
  yields a black capture frame on many Linux setups.
- Prices come from [poe2scout](https://poe2scout.com); cached ~20 min, never fetched per frame.
- Only **currency-vs-currency** choices are ranked reliably. Non-currency rewards (gear, gems,
  thin-market league items) are shown as unknown rather than guessed.
- Calibrate on an **English** client (OCR/snap dictionary).
