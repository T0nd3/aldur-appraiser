# Temple Planner — Implementation Plan

A second PoE2 league-mechanic helper inside aldur-appraiser: the **Vaal Temple**.
Goal: build the temple efficiently — maximise high-tier valuable rooms while
minimising rooms lost to destabilisation.

## Locked decisions
- **Location:** a `temple` module *inside* the aldur-appraiser repo (shares
  packaging / overlay / capture infra; kept separate from the pricing core).
- **Form:** interactive **editor first**, then a solver on top.
- **Solver = per-run placement advisor**, NOT a global optimiser — each run you
  draw 6 *random* cards, so the whole temple can't be pre-planned.

## Mechanic (Vaal Temple), as confirmed
- **9×9 diamond grid.** Built over ~10 runs (**60 energy, 6 per run**).
- Each run you **draw 6 random cards** (rooms + `Path`) and place them. Selecting
  a card shows green highlights for where it interacts with placed rooms.
- Rooms upgrade to **max Tier 3** by **adjacency** to specific room types (counts
  per room). **Exception: the Generator/Dynamo** powers rooms within a Manhattan
  radius (3/4/5 by tier) and **must be connected to a Road/Path**.
- `Path` cards connect non-adjacent rooms.
- **Conversions:** Spymaster converts an adjacent Garrison → Legion Barracks;
  Synthflesh Lab converts an adjacent Garrison → Transcendent Barracks.
- **Architect rooms** (Currency/Uniques/Tablets/… Vaults) unlock by defeating the
  Architect and **destabilise on completion**.
- **Destabilisation:** each entry 2–3 random tiles destabilise (removed
  permanently on exit). **Accessible "Restricted" rooms always destabilise.**
  Defeating Architect/Atziri → greater destabilisation.
- The game's **"Restricted Rooms"** are the **Architect reward Vaults** (placed
  via Xipocado's Console after the Architect). They — and the Treasure Vault —
  are **volatile**: a Vault is placed for its bonus but only **opening** it
  triggers destabilisation (it also hits the snake's loose ends). The efficient
  community layouts use almost no Vaults, so the practical rule is **avoid Vaults**
  — modelled by the volatile discount + presets that never weight Vaults up.
  (`is_volatile()`; editor marks them magenta / "One-use".)
- **Snake building (key):** destabilisation only deletes rooms whose removal
  orphans nothing — the **loose ends** (`removable_room_cells`). A single chain
  ("snake") from the entrance has exactly ONE end (its tail), so only that one
  can be lost; branches and loops add more ends. So the goal is the OPPOSITE of
  loops: build a snake, bury valuable rooms in the interior (articulation points
  are SAFE), and leave a cheap room as the tail. The editor marks the loose ends
  orange ("deletable"); the advisor discounts them.
- Only **accessible** (connected) rooms count toward the score / bonuses.
- Volatile rooms are also discounted.
- **Objective:** maximise high-tier valuable rooms (the upgrade graph), keep them
  off the loose ends (snake interior), prefer persistent over volatile, and avoid
  fighting the Architect/Atziri (greater destabilisation).

## Data model — BUILT (`src/aldur_appraiser/temple/rooms.py`)
- `Room` dataclass: `id, name, category, bonus, generator, fixed_tier,
  architect_room, upgraded_by (UpgradeRule: source + per-tier counts),
  cannot_connect (symmetric), converts, aka (in-game card names), notes`.
- **24 rooms** encoded from the mobalytics Vaal Temple table + in-game graph.
- `validate()` checks referential integrity + `cannot_connect` symmetry.
- Tests: `tests/test_temple_rooms.py` (5, passing).

## Open VERIFY items (don't block the engine)
1. **Card/display-name mappings (RESOLVED via Hold-Alt):** Barracks=Garrison,
   Depot=Armoury, Dynamo=Generator, Thaumaturge's Laboratory=Thaumaturge,
   **Prosthetic Research=Synthflesh Lab** (a card name, NOT a separate room).
2. **Upgrade rules — RESOLVED (ported from Tetriszocker ROOM_DATA):** group
   `count` (sum across a list of source types), `require_all` (one of EACH type),
   and `source_min_tier`. So e.g. Commander = 2/3 adjacent {Garrison, Transcendent}
   together; Garrison/Armoury/Generator T3 need both of their pair; Flesh Surgeon
   T3 needs a T2+ Synthflesh. Engine resolves tiers to a fixed point.
   Hold-Alt verified rooms (12): Generator, Thaumaturge, Synthflesh, Smithy,
   Transcendent Barracks, Sacrificial Chamber, Golem Works, Commander, Flesh
   Surgeon, Alchemy Lab, Garrison, Corruption Chamber. Unseen (inverse-confirmed):
   Armoury, Legion Barracks, Spymaster.
   IMPORTANT correction: mobalytics had the Spymaster and Golem Works "effect of
   Temple Mods from …" lists SWAPPED; corrected per in-game graph + Hold-Alt.
3. **Generator power — RESOLVED:** powers directly adjacent rooms and conducts
   along connected paths (within range 3/4/5 by tier) to rooms beside them; must
   be connected to a road. Sacrifice/assassinate rooms (Sacrificial Chamber,
   Spymaster) carry `manual_tier` and get their tier from a per-cell override.
   Note: high-tier ritual rooms hold a one-use device that destabilises the room.
4. **Exact per-tier % numbers** (value display only; not needed for structure).
5. **"Restricted Rooms" — RESOLVED:** the in-game Architect's Chamber confirms the
   game's "Restricted Rooms" are the Architect reward Vaults (= our `volatile`/
   `architect_room`). A separate `removable_room_cells` heuristic models the snake
   logic (loose ends destabilisation can delete) — see the Mechanic section.
6. Which rooms count as **"valuable"** for the objective/advisor weighting
   (likely user-configurable) + the Prosthetic Research effect.

## Phases & status
- [x] **Phase 1a — Room dataset + schema** — 24 rooms from the authoritative
  source; VERIFY items above are refinements only.
  (`temple/rooms.py`, `tests/test_temple_rooms.py`, 5 tests)
- [x] **Phase 1b — Rules engine** — `temple/engine.py` (+ `tests/test_temple_engine.py`).
  9×9 grid, placement, accessibility BFS from the entrance, generator Manhattan
  power radius (needs network connection), adjacency tier computation, Garrison
  conversions, cannot-connect violation checks, and `removable_room_cells`
  (loose ends destabilisation can delete; a snake leaves only one).
  Offline, no % numbers needed.
- [x] **Phase 2 — Interactive editor (Qt)** — `temple/editor.py` (+ headless
  smoke test `tests/test_temple_editor.py`). 9×9 painter grid, room palette
  (left-click place / right-click erase), category colours, live tiers, hovered
  Generator power-radius highlight, entrance marker, cannot-connect violations
  (red border), status line. Launches via `appraiser temple`.
- [x] **Phase 3 — Per-run advisor** — `temple/advisor.py` (+ `tests/test_temple_advisor.py`).
  `score()` (Σ value·tier − violation penalty), `legal_cells()` (connected only),
  `suggest()` ranks every legal (card, cell) by score delta, `plan_hand()` greedily
  places a whole hand. Wired into the editor: a "hand" list + **Suggest** button
  that ranks placements and gold-highlights the best cell.
- [ ] **Phase 4 (optional/future) — Live overlay:** read the temple grid + drawn
  cards via vision and suggest placements in-game. Hard/fragile — later.

## Engine design notes (for Phase 1b)
- **Grid:** 9×9; placed cells `{(x,y): PlacedRoom(room_id, ...)}`; 2–3 random
  pre-destabilised cells are unusable.
- **Adjacency:** 4-neighbour. Two placed rooms are "connected" if adjacent OR
  linked through a chain of `Path` tiles / adjacent rooms.
- **Accessibility:** BFS from the entrance (bottom-centre) over the path/room
  network; a room is accessible if reachable.
- **Chokepoint risk:** a placed room is an articulation point if removing it
  disconnects some room from the entrance → those are the risky (sole-link) rooms.
- **Tier:** per room, count adjacent rooms matching each `UpgradeRule.source`;
  tier = highest tier whose threshold is met (cap 3, or `fixed_tier`). Generator
  powers rooms in its Manhattan radius if connected to a path.
- **Destab risk score:** expected loss ≈ f(random 2–3 tiles + accessible
  volatile/removable rooms + architect/atziri). Advisor minimises expected loss
  of high-value rooms.

## Key sources
- mobalytics Vaal Temple guide (room table): <https://mobalytics.gg/poe-2/guides/vaal-temple>
- Reference editor (partial room logic, JS): <https://tetriszocker.github.io/atziri-temple-editor/>
- In-game room graph + tooltips + "Hold Alt → room interactions" (authoritative;
  player-provided screenshots).

## Resume here
Phases 1–3 are done (dataset, engine, editor, advisor; `appraiser temple`;
25 temple tests). The planner is usable end-to-end: build a grid, enter your
drawn hand, get ranked placement suggestions.

Remaining / future work:
- Verify the open data items above (upgrade counts, % numbers, card-name and
  Restricted-room mappings) and refine `rooms.py` + per-room `values` weighting.
- Smarter advisor: lookahead / future-upgrade potential, not just immediate gain;
  let the user weight which rooms are "valuable".
- **Phase 4 (optional) — live overlay:** read the temple grid + drawn cards via
  vision and suggest in-game. Hard/fragile; only if the offline planner proves
  useful first.

## Phase 5 plan — auto-detect hand cards & medallions (vision)

Goal: a "Detect from screen" button in the temple editor that fills the **hand**
(and later **medallions**) by reading the live PoE2 Temple Console, reusing the
pricing stack (`vision/capture.py` + `ocr.py`). Read-only: screen capture + OCR
only, no input/memory access.

### 5a — Hand cards (text OCR) — primary, feasible
The left "Room Cards" list shows card **names** as text (e.g. "Spymaster's
Study", "Path", "Chamber of Souls"). Pipeline:
1. Capture the frame (existing backend).
2. Locate the "Room Cards" panel ROI. Anchor by template-matching the
   "Room Cards" header (like the Runeshape header), then take a fixed band below
   it; ~6 card rows.
3. OCR each row's name text.
4. Fuzzy-match (rapidfuzz, same as pricing) against room `name` + `aka`
   (in-game card names differ from our ids — Bronzeworks=Smithy, Chamber of
   Souls=Alchemy Lab, Dynamo=Generator, Guardhouse=Garrison, Surgeon's Ward=
   Flesh Surgeon, …). Build a `CARD_NAME -> room_id` table from `aka`.
5. Populate `self.hand` + `hand_list`.
Risks: OCR on stylised gold-on-dark font; card names wrap/scroll. Mitigate with
the proven `fuzz.ratio` matcher and a name/aka lookup.

### 5b — Medallions (icon match) — secondary, harder
The right "Medallions (n/6)" panel shows **icons**, not text. Options:
- Template-match each medallion icon (needs one clean crop per medallion type),
  or
- (worse) OCR the hover tooltip — needs synthetic hover, out of scope (read-only).
Medallions map to rooms via their "May drop … Medallion" lines already noted on
rooms. Defer until 5a works.

### Integration
- New module `temple/vision.py`: `detect_hand(frame) -> list[room_id]`,
  `detect_medallions(frame) -> list[room_id]`.
- Editor: "Detect from screen" button → capture → detect → set hand/medallions
  (replace or append; ask). Headless-safe (button only active with capture).

### Assets needed from the player (at native resolution)
- A full screenshot of the Temple Console with the Room Cards list populated.
- A crop of the "Room Cards" header (ROI anchor template).
- Later: one clean crop of each medallion icon seen so far.

### Effort
- 5a: medium (ROI calibration + name/aka table + tests on a fixture screenshot).
- 5b: medium-high and fragile (per-icon templates). Optional.
