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
  are **volatile**: self-destabilise once used (`is_volatile()`; editor marks them
  magenta / "One-use"). One-time reward, won't persist.
- Separately, the engine flags **chokepoints** (`chokepoint_room_cells`):
  articulation points that are the sole link to rooms behind them, so a random
  2–3 destabilisation there strands those rooms. A **redundant path / loop**
  clears a chokepoint. Editor marks them orange. (A layout heuristic, NOT the
  game's "Restricted Rooms".)
- Both chokepoints and volatile rooms are **discounted** in the advisor score.
- **Objective:** maximise high-tier valuable rooms (the upgrade graph), keep them
  off chokepoints (loops), prefer persistent over volatile, and avoid fighting
  the Architect/Atziri (greater destabilisation) + the random 2–3 tiles.

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
2. **Per-tier upgrade COUNTS** where the table is silent (Armoury, Smithy,
   Generator, Thaumaturge, Corruption, …) — assumed **1 adjacent → T2, 2 → T3**.
   Confirmed: Commander 2/3 Garrison, Alchemy 1/2 Thaumaturge, Golem 2 Generators
   for T3. Still need the rest from in-game "Hold Alt".
3. **Source-tier requirements** not yet modelled (e.g. Thaumaturge needs a T2+
   Sacrificial Chamber; Flesh Surgeon T3 needs a Generator-powered Synthflesh).
   (Sacrifice/assassinate rooms — Sacrificial Chamber, Spymaster — carry a
   `manual_tier` flag and get their tier from a per-cell override in the editor,
   since it can't be derived from the layout.)
3b. **Group/category upgrade counts** not yet modelled: Hold-Alt showed the
   Commander is upgraded by *any* adjacent barrack (Garrison/Legion/Transcendent),
   so its 2/3 count almost certainly SUMS across barrack types — the engine counts
   per-room-type today. Needs an UpgradeRule that can match a category/group.
   Hold-Alt verified: Generator, Thaumaturge, Synthflesh Lab, Smithy, Transcendent
   Barracks, Sacrificial Chamber, Golem Works, Commander, Flesh Surgeon, Alchemy
   Lab, Garrison, Corruption Chamber. Garrison packs 8/12/16, normal -/10/13;
   Alchemy T2 25. Remaining unseen: Armoury, Legion Barracks, Spymaster — all
   inverse-confirmed. Commander is upgraded by
   adjacent Garrison OR Transcendent Barracks (NOT Legion) and upgrades adjacent
   Garrisons in turn. Tier %: Garrison T2 12/T3 20, Armoury T1 10/T3 60, Smithy T2
   30, Golem Works T2 15, Commander T1 10, Thaumaturge T1 8/T2 15/T3 22, Synthflesh
   T1 10/T2 20, Transcendent T3 35.
   IMPORTANT correction: mobalytics had the Spymaster and Golem Works "effect of
   Temple Mods from …" lists SWAPPED. The in-game graph + Hold-Alt are authoritative
   (Golem Works ← Garrison/Commander/Armoury/Smithy/Legion; Spymaster ← Generator/
   Synthflesh/Flesh Surgeon/Transcendent/Alchemy).
   Note: high-tier ritual rooms (Thaumaturge/Sacrificial/Alchemy/Corruption) hold
   a one-use "device" that destabilises the room when used (optional).
4. **Exact per-tier % numbers** (value display only; not needed for structure).
5. **"Restricted Rooms" — RESOLVED:** the in-game Architect's Chamber confirms the
   game's "Restricted Rooms" are the Architect reward Vaults (= our `volatile`/
   `architect_room`). The articulation concept was renamed **chokepoint**
   (`chokepoint_room_cells`) and kept as a layout heuristic, separate from them.
6. Which rooms count as **"valuable"** for the objective/advisor weighting
   (likely user-configurable) + the Prosthetic Research effect.

## Phases & status
- [x] **Phase 1a — Room dataset + schema** — 24 rooms from the authoritative
  source; VERIFY items above are refinements only.
  (`temple/rooms.py`, `tests/test_temple_rooms.py`, 5 tests)
- [x] **Phase 1b — Rules engine** — `temple/engine.py` (+ `tests/test_temple_engine.py`).
  9×9 grid, placement, accessibility BFS from the entrance, generator Manhattan
  power radius (needs network connection), adjacency tier computation, Garrison
  conversions, cannot-connect violation checks, and `chokepoint_room_cells`
  (articulation points = sole links; a redundant loop clears them).
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
  volatile/chokepoint rooms + architect/atziri). Advisor minimises expected loss
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
