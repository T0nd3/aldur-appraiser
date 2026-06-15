# Promotion drafts

Ready-to-post copy for sharing the tool. Replace `LINK` with the repo/release URL
and drop in a demo GIF where noted. Keep the read-only / "use at own risk"
framing — the community (and GGG) care about that.

---

## Reddit — r/PathOfExile2 (and r/PathOfExile)

**Title:**
Aldur Appraiser — a passive overlay that prices Runeshape Combination rewards (read-only, open source)

**Body:**

I kept hesitating at the Ezomyte Remnant's *Runeshape Combinations* panel, not sure which reward
was actually worth the most. So I built a small tool that prices them for you.

**What it does:** it watches for the panel, reads the reward options, and shows the value of each
one **right next to it** — in Exalted/Divine with the currency icon, best choice highlighted. The
always-paid bonus reward is shown separately (it doesn't affect the choice), and anything it can't
price is marked `?` rather than guessed.

*(demo GIF here)*

**How it works / safety:** it's **read-only** — just screen capture + OCR, drawing its own overlay
on top. No clipboard, no simulated input, no memory reading, no interaction with the game client.
It runs in the system tray. Prices come from poe2scout.

**Get it:** download a one-file build for **Windows** or **macOS** from the releases page (Linux:
a setup script). First launch shows the usual unsigned-app prompt (SmartScreen → *More info* →
*Run anyway*; macOS → right-click → *Open*). Run PoE2 in borderless/windowed fullscreen.

It's open source — feedback, issues and PRs welcome: **LINK**

⚠️ Use at your own risk: there's no official endorsement, and GGG's third-party policy is strict
about automation. I built it to be passive/read-only specifically to stay on the safe side, but I
can't make any guarantees — decide for yourself.

---

## Official forum — Third-Party Tools / Development

**Title:** Aldur Appraiser — passive read-only reward-valuation overlay for the Runeshape panel

Hi all — sharing a small open-source tool I made for the *Runeshape Combinations* panel.

It detects the panel via screen capture, OCRs the reward options, prices them against poe2scout,
and renders an inline overlay showing each option's value (Exalted/Divine, with the currency icon)
plus the best pick. The always-paid bonus reward is excluded from the ranking; unpriceable rewards
are shown as `?` rather than guessed; hover tooltips are filtered out.

Design notes for the curious:
- **Strictly read-only:** screen capture + OCR + an overlay window. No clipboard use, no input
  injection, no process/memory access — the same one-direction "read the screen" approach as some
  existing price-check tools, minus the clipboard step.
- Cross-platform: Windows/macOS use a screen-grab API directly; on Linux/Wayland it goes through
  the xdg-desktop-portal screencast (with a one-time permission prompt).
- System-tray app; built-in update check; English client.

Binaries (Windows/macOS) and source: **LINK**

Use at your own risk — this is unofficial, with no endorsement from GGG. I'd appreciate any
feedback, especially on detection across resolutions and edge-case panels.
