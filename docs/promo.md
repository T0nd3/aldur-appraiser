# Promotion drafts

Ready-to-post copy. Replace `LINK` with the repo/release URL and attach the demo
clip where noted. Keep the read-only / disclaimer framing intact.

---

## Reddit — r/PathOfExile2 (and r/PathOfExile)

**Title:**
Aldur Appraiser — a read-only overlay that values Runeshape Combination rewards (open source)

**Body:**

Aldur Appraiser is an open-source overlay for Path of Exile 2 that values the reward options on
the Ezomyte Remnant's *Runeshape Combinations* panel.

It detects the panel, reads the offered rewards via OCR, prices them against poe2scout, and shows
each option's value inline — in Exalted or Divine with the matching currency icon — with the most
valuable choice highlighted. The always-paid bonus reward is reported separately so it does not
affect the comparison, and any reward that cannot be priced is shown as `?` rather than estimated.

*(attach the demo clip here)*

**Design and safety.** The tool is strictly read-only: it captures the screen and draws its own
overlay. It does not use the clipboard, simulate input, read process memory, or interact with the
game client in any way. It runs in the system tray and sources prices from poe2scout.

**Availability.** Single-file builds for Windows and macOS are on the releases page; Linux uses a
setup script. The binaries are unsigned, so the first launch shows the standard OS prompt (Windows
SmartScreen → *More info* → *Run anyway*; macOS → right-click → *Open*). Run the game in
borderless/windowed fullscreen.

Source and downloads: **LINK**

**Disclaimer.** This is an unofficial, third-party tool with no endorsement from GGG, whose policy
on third-party software is restrictive. It was deliberately built to be passive and read-only to
minimise risk, but no guarantees can be made — use it at your own discretion.

---

## Official forum — Third-Party Tools / Development

**Title:** Aldur Appraiser — read-only reward-valuation overlay for the Runeshape Combinations panel

Aldur Appraiser is an open-source overlay for the Ezomyte Remnant's *Runeshape Combinations* panel.

It detects the panel through screen capture, reads the reward options via OCR, prices them against
poe2scout, and renders an inline overlay showing each option's value (Exalted/Divine with the
currency icon) and the best pick. The always-paid bonus reward is excluded from the ranking,
rewards that cannot be priced are marked `?` rather than estimated, and transient hover tooltips
are filtered out.

Implementation notes:

- **Strictly read-only.** Screen capture, OCR, and an overlay window only — no clipboard use, no
  input injection, no process or memory access.
- **Cross-platform.** Windows and macOS use a direct screen-grab API; on Linux/Wayland capture
  goes through the xdg-desktop-portal screencast (one-time permission prompt).
- System-tray application with a built-in update check. English client.

Binaries (Windows/macOS) and source: **LINK**

This is unofficial software with no endorsement from GGG; use it at your own discretion. Feedback
is welcome, particularly on panel detection across resolutions and uncommon reward layouts.
