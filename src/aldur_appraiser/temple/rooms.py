"""Temple room dataset + schema (PoE2 Vaal Temple).

The upgrade graph is sourced from the mobalytics Vaal Temple guide
(Room | Bonus | Upgraded-By-Adjacent | converts-to table) plus the in-game room
graph and tooltips. It's the foundation everything else builds on, so it's plain
data with a typed schema and a validator.

Confirmed by the player:
  - Tier upgrades count ADJACENT rooms of the listed type(s) — except the
    Generator/Dynamo, which powers rooms within a Manhattan radius (and must be
    connected to a road/path).
  - "Restricted" is topological: a room whose removal would orphan rooms behind
    it (an articulation point on the path). Modelled in the engine, not as a
    fixed per-room flag.

Still VERIFY: the exact per-tier counts for upgraders the table doesn't spell
out (assumed 1 adjacent -> T2, 2 -> T3) and the exact per-tier % numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

CATEGORIES = {"barrack", "production", "ritual", "utility", "generator", "special", "path"}

# Default per-tier adjacency counts where the source guide doesn't state them.
_DEFAULT_COUNTS = {2: 1, 3: 2}  # VERIFY


@dataclass(frozen=True)
class UpgradeRule:
    """A room's tier rises when enough adjacent `source` rooms are present.

    `counts` maps a target tier to the number of adjacent `source` rooms needed,
    e.g. Commander: {2: 2, 3: 3} = 2 Garrisons for T2, 3 for T3. Sources without
    explicit counts in the guide use _DEFAULT_COUNTS (marked VERIFY).
    """

    source: str
    counts: dict[int, int] = field(default_factory=lambda: dict(_DEFAULT_COUNTS))


@dataclass(frozen=True)
class Room:
    id: str
    name: str
    category: str
    bonus: str = ""                      # effect text (scales with tier)
    generator: bool = False              # powers nearby rooms; must connect to a road
    fixed_tier: int | None = None        # rooms that can't be upgraded (e.g. Vault)
    architect_room: bool = False         # unlocked via Architect; destabilises on complete
    volatile: bool = False               # destabilises (is consumed) once opened/completed
    manual_tier: bool = False            # tier comes from a player action (sacrifice /
    #                                      assassinate), not the layout -> set by hand
    upgraded_by: tuple[UpgradeRule, ...] = ()
    cannot_connect: tuple[str, ...] = ()
    converts: tuple[str, ...] = ()       # "<from>-><to>" conversions this room triggers
    aka: tuple[str, ...] = ()            # in-game card/tier display names (Barracks, Depot…)
    notes: tuple[str, ...] = ()


def _u(source: str, counts: dict[int, int] | None = None) -> UpgradeRule:
    return UpgradeRule(source, counts or dict(_DEFAULT_COUNTS))


def is_volatile(room: "Room") -> bool:
    """True if the room is consumed/destabilised once completed (Treasure Vault,
    Architect reward rooms) — placing it gives a one-time reward but it won't
    persist, so it's a poor pick for a lasting, re-runnable temple."""
    return room.volatile or room.architect_room


ROOMS: dict[str, Room] = {
    # --- barracks line -------------------------------------------------------
    "garrison": Room(
        id="garrison", name="Garrison", category="barrack",
        bonus="increased Number of Magic Monster Packs",
        aka=("Barracks", "Guardhouse"),
        converts=("garrison->transcendent_barracks", "garrison->legion_barracks"),
        notes=(
            "Base room; an adjacent Synthflesh Lab converts it to Transcendent "
            "Barracks, an adjacent Spymaster converts it to Legion Barracks.",
            "Tier %: T2 ~12% packs / 10% Normal Effectiveness, T3 ~20% / 30% (VERIFY).",
        ),
    ),
    "commander": Room(
        id="commander", name="Commander's Chamber", category="barrack",
        bonus="Rare Monsters have increased Effectiveness",
        upgraded_by=(
            _u("garrison", {2: 2, 3: 3}),
            _u("legion_barracks", {2: 2, 3: 3}),
            _u("transcendent_barracks", {2: 2, 3: 3}),
        ),
        cannot_connect=("spymaster",),
        notes=(
            "Upgraded by adjacent barracks (Garrison/Legion/Transcendent). The 2/3 "
            "count likely SUMS across barrack types; the engine counts per-type for "
            "now (VERIFY — needs a category/group upgrade rule).",
        ),
    ),
    "legion_barracks": Room(
        id="legion_barracks", name="Legion Barracks", category="barrack",
        bonus="more Rare Monsters; High chance for an Advanced Medallion",
        notes=("Created when a Spymaster converts an adjacent Garrison.",),
    ),
    "transcendent_barracks": Room(
        id="transcendent_barracks", name="Transcendent Barracks", category="barrack",
        bonus="more Magic Monsters (T3 35%)",
        upgraded_by=(_u("generator"), _u("synthflesh_lab")),
        notes=("Created when a Synthflesh Lab converts an adjacent Garrison.",),
    ),
    # --- production line -----------------------------------------------------
    "armoury": Room(
        id="armoury", name="Armoury", category="production",
        bonus="Humanoid Monsters have increased Effectiveness; contains Equipment",
        aka=("Depot",),
        upgraded_by=(_u("smithy"), _u("alchemy_lab")),
    ),
    "smithy": Room(
        id="smithy", name="Smithy", category="production",
        bonus="Chests have increased Item Rarity (T2 30%); Vaal Infuser",
        upgraded_by=(_u("golem_works"), _u("generator")),
    ),
    "golem_works": Room(
        id="golem_works", name="Golem Works", category="production",
        bonus="increased Effect of Temple Mods from Generators/Synthflesh/Flesh "
              "Surgeons/Transcendent Barracks/Alchemy Labs; adds High Priest",
        upgraded_by=(_u("generator"),),
    ),
    "synthflesh_lab": Room(
        id="synthflesh_lab", name="Synthflesh Lab", category="production",
        bonus="Monsters grant increased Experience (T1 10% / T2 20%)",
        aka=("Prosthetic Research",),  # the card that places a Synthflesh Lab
        cannot_connect=("spymaster",),
        converts=("garrison->transcendent_barracks",),
        upgraded_by=(_u("flesh_surgeon", {2: 1}), _u("generator", {3: 1})),
    ),
    "flesh_surgeon": Room(
        id="flesh_surgeon", name="Flesh Surgeon's Ward", category="production",
        bonus="Unique Monsters have increased Effectiveness; Limb Modification; "
              "T3 Transcension Device",
        upgraded_by=(_u("synthflesh_lab", {2: 1}),),
        notes=("A Synthflesh Lab powered by a Generator upgrades it to T3.",),
    ),
    # --- generator -----------------------------------------------------------
    "generator": Room(
        id="generator", name="Generator", category="generator", generator=True,
        bonus="Construct Monsters have increased Effectiveness; adds Corrupted "
              "Abomination; powers Smithy/Golem Works/Synthflesh/Transcendent",
        aka=("Dynamo",),
        upgraded_by=(_u("thaumaturge"), _u("sacrificial_chamber")),
        notes=(
            "Must be connected to a Road/Path to function.",
            "Power range is Manhattan distance 3/4/5 tiles by tier (T1/T2/T3).",
        ),
    ),
    # --- ritual / corruption line -------------------------------------------
    "thaumaturge": Room(
        id="thaumaturge", name="Thaumaturge's Laboratory", category="ritual",
        bonus="increased Effect of Temple Mods from Corruption Chambers/Treasure "
              "Vaults/Sacrificial Chambers (T1 8% / T2 15% / T3 22%); "
              "adds Quadrilla Sergeant",
        upgraded_by=(_u("sacrificial_chamber"),),
        notes=(
            "Upgraded by an adjacent Sacrificial Chamber of Tier 2 or 3.",
            "T3 holds a Gem Corrupter device; using it destabilises the room (one-use).",
        ),
    ),
    "alchemy_lab": Room(
        id="alchemy_lab", name="Alchemy Lab", category="ritual",
        bonus="increased Rarity of Items and Gold found; T1-2 Soul Core Cache, "
              "T3 Soul Core Infuser (-> Core Destabiliser)",
        upgraded_by=(_u("thaumaturge", {2: 1, 3: 2}),),
    ),
    "corruption_chamber": Room(
        id="corruption_chamber", name="Corruption Chamber", category="ritual",
        bonus="Rare Monsters have a chance for an additional Modifier; T1-2 "
              "Corruption Altar, T3 Corruption Instiller (-> Architect's Orb)",
        upgraded_by=(_u("thaumaturge"), _u("sacrificial_chamber")),
    ),
    "sacrificial_chamber": Room(
        id="sacrificial_chamber", name="Sacrificial Chamber", category="ritual",
        bonus="increased number of Rare Chests; T3 Morphology Mechanism "
              "(-> Vaal Cultivation Orb)",
        manual_tier=True,
        notes=(
            "Upgraded by SACRIFICING other placed rooms (irreversible), not by "
            "adjacency. Upgrades adjacent Generator/Thaumaturge/Corruption Chamber.",
            "Holds a Morphology Mechanism device; using it destabilises the room.",
        ),
    ),
    "treasure_vault": Room(
        id="treasure_vault", name="Treasure Vault", category="ritual",
        bonus="25% increased Rarity of Items Dropped by Monsters",
        fixed_tier=1,
        volatile=True,
        aka=("Sealed Vault",),
        notes=(
            "Contains valuable Chests based on surrounding rooms.",
            "Room destabilises once the central Vault is opened — one-use.",
        ),
    ),
    # --- utility -------------------------------------------------------------
    "spymaster": Room(
        id="spymaster", name="Spymaster's Study", category="utility",
        bonus="increased Effect of Temple Mods from Garrisons/Commanders/"
              "Armouries/Smithies/Legion Barracks; High chance for a Lock Medallion",
        manual_tier=True,
        cannot_connect=("commander", "synthflesh_lab"),
        converts=("garrison->legion_barracks",),
        notes=("Upgraded by assassinating other Spymasters, not by adjacency.",),
    ),
    # --- path connector ------------------------------------------------------
    "path": Room(
        id="path", name="Path", category="path",
        bonus="No bonus; expands the path / connects rooms.",
    ),
    # --- Architect-unlocked special rooms (destabilise after completion) -----
    "royal_access_chamber": Room(
        id="royal_access_chamber", name="Royal Access Chamber", category="special",
        architect_room=True, bonus="Unlocks Atziri's Chamber",
    ),
    "extraction_chamber": Room(
        id="extraction_chamber", name="Extraction Chamber", category="special",
        architect_room=True,
        bonus="Extraction Workbench (destroys an item, returns its Augments; "
              "-> Orb of Extraction)",
    ),
    "augments_vault": Room(
        id="augments_vault", name="Augments Vault", category="special",
        architect_room=True, bonus="Rune Cache (a high-level endgame Rune)",
    ),
    "currency_vault": Room(
        id="currency_vault", name="Currency Vault", category="special",
        architect_room=True, bonus="Two Treasure Chests of random Currency",
    ),
    "lineage_gems_vault": Room(
        id="lineage_gems_vault", name="Lineage Gems Vault", category="special",
        architect_room=True, bonus="A random Lineage Support Gem",
    ),
    "tablets_vault": Room(
        id="tablets_vault", name="Tablets Vault", category="special",
        architect_room=True,
        bonus="Corrupted Precursor Machine (modifies a Precursor Tablet; "
              "-> Ancient Infuser)",
    ),
    "uniques_vault": Room(
        id="uniques_vault", name="Uniques Vault", category="special",
        architect_room=True, bonus="A Display granting a random Unique Item",
    ),
}


def validate(rooms: dict[str, Room] = ROOMS) -> list[str]:
    """Return a list of dataset problems (empty == OK).

    Checks referential integrity so a typo'd room id surfaces immediately. Both
    sides of a `cannot_connect` must agree (the constraint is symmetric).
    """
    problems: list[str] = []
    for rid, room in rooms.items():
        if rid != room.id:
            problems.append(f"{rid}: key != room.id ({room.id!r})")
        if room.category not in CATEGORIES:
            problems.append(f"{rid}: unknown category {room.category!r}")
        for rule in room.upgraded_by:
            if rule.source not in rooms:
                problems.append(f"{rid}: upgraded_by unknown room {rule.source!r}")
            if not rule.counts:
                problems.append(f"{rid}: upgrade rule from {rule.source!r} has no tier counts")
        for other in room.cannot_connect:
            if other not in rooms:
                problems.append(f"{rid}: cannot_connect unknown room {other!r}")
            elif rid not in rooms[other].cannot_connect:
                problems.append(f"{rid}: cannot_connect {other!r} is not symmetric")
        for conv in room.converts:
            src, _, dst = conv.partition("->")
            if src not in rooms or dst not in rooms:
                problems.append(f"{rid}: converts references unknown room(s) {conv!r}")
    return problems
