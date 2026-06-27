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
- **The game never allows orphaned rooms** — you cannot place a room that would
  be (or leave anything) disconnected. So there is NO articulation/orphan risk to
  model; removed the engine logic that flagged it.
- **"Restricted" = a fixed room category**, not topological. Best current read:
  the Architect special reward rooms (Currency/Uniques/… Vaults) that are
  consumed/destroyed after completion (`architect_room=True`). VERIFY.
- **Objective:** maximise **high-tier valuable** rooms (the upgrade graph). Few
  rooms-removed is mostly about NOT fighting the Architect/Atziri (greater
  destabilisation) plus the uncontrollable random 2–3 tiles.

## Data model — BUILT (`src/aldur_appraiser/temple/rooms.py`)
- `Room` dataclass: `id, name, category, bonus, generator, fixed_tier,
  architect_room, upgraded_by (UpgradeRule: source + per-tier counts),
  cannot_connect (symmetric), converts, aka (in-game card names), notes`.
- **24 rooms** encoded from the mobalytics Vaal Temple table + in-game graph.
- `validate()` checks referential integrity + `cannot_connect` symmetry.
- Tests: `tests/test_temple_rooms.py` (5, passing).

## Open VERIFY items (don't block the engine)
1. **Card/display-name mappings:** Barracks=Garrison, Depot=Armoury,
   Dynamo=Generator, **Prosthetic Research=Flesh Surgeon? (guessed)**.
2. **Per-tier upgrade COUNTS** where the table is silent (Armoury, Golem,
   Corruption, …) — currently assumed **1 adjacent → T2, 2 → T3**.
3. **Exact per-tier % numbers** (value display only; not needed for structure).
4. Confirm **"Restricted" rooms** = the Architect special reward rooms (current
   assumption) vs some other fixed category.
5. Which rooms count as **"valuable"** for the objective/advisor weighting
   (likely user-configurable).

## Phases & status
- [x] **Phase 1a — Room dataset + schema** — 24 rooms from the authoritative
  source; VERIFY items above are refinements only.
  (`temple/rooms.py`, `tests/test_temple_rooms.py`, 5 tests)
- [x] **Phase 1b — Rules engine** — `temple/engine.py` (+ `tests/test_temple_engine.py`,
  10 tests). 9×9 grid, placement, accessibility BFS from the entrance, generator
  Manhattan power radius (needs network connection), adjacency tier computation,
  Garrison conversions, cannot-connect violation checks. Offline, no % numbers
  needed. (Orphan/articulation logic removed — the game never allows orphans.)
- [x] **Phase 2 — Interactive editor (Qt)** — `temple/editor.py` (+ headless
  smoke test `tests/test_temple_editor.py`). 9×9 painter grid, room palette
  (left-click place / right-click erase), category colours, live tiers, hovered
  Generator power-radius highlight, entrance marker, cannot-connect violations
  (red border), status line. Launches via `appraiser temple`.
- [ ] **Phase 3 — Per-run advisor:** given current grid + the 6 drawn cards →
  recommend best placements (maximise upgrades, set up future upgrades, protect
  high-value rooms / avoid orphaning).
- [ ] **Phase 4 (optional/future) — Live overlay:** read the temple grid + drawn
  cards via vision and suggest placements in-game. Hard/fragile — later.

## Engine design notes (for Phase 1b)
- **Grid:** 9×9; placed cells `{(x,y): PlacedRoom(room_id, ...)}`; 2–3 random
  pre-destabilised cells are unusable.
- **Adjacency:** 4-neighbour. Two placed rooms are "connected" if adjacent OR
  linked through a chain of `Path` tiles / adjacent rooms.
- **Accessibility:** BFS from the entrance (bottom-centre) over the path/room
  network; a room is accessible if reachable.
- **Orphan/Restricted risk:** a placed room is an articulation point if removing
  it disconnects some room from the entrance → those are the risky rooms.
- **Tier:** per room, count adjacent rooms matching each `UpgradeRule.source`;
  tier = highest tier whose threshold is met (cap 3, or `fixed_tier`). Generator
  powers rooms in its Manhattan radius if connected to a path.
- **Destab risk score:** expected loss ≈ f(random 2–3 tiles + accessible
  restricted rooms + architect/atziri). Advisor minimises expected loss of
  high-value rooms.

## Key sources
- mobalytics Vaal Temple guide (room table): <https://mobalytics.gg/poe-2/guides/vaal-temple>
- Reference editor (partial room logic, JS): <https://tetriszocker.github.io/atziri-temple-editor/>
- In-game room graph + tooltips + "Hold Alt → room interactions" (authoritative;
  player-provided screenshots).

## Resume here
Phases 1 + 2 are done (`temple/rooms.py`, `temple/engine.py`, `temple/editor.py`;
`appraiser temple` launches the editor; 17 temple tests).
Next concrete step is **Phase 3 (per-run advisor)**: given the current grid + the
6 drawn cards, rank placements by resulting tier gain (and future upgrade
potential). Pure function on the engine; unit-testable. Verify the open items
above when convenient (they only affect exact numbers/labels, not the structure).
