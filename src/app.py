import json
import copy
from pathlib import Path
from flask import Flask, request, jsonify, render_template
from placer import place_layout

app = Flask(__name__)

ROOT_DIR = Path(__file__).resolve().parent
EQUIPMENT = json.loads((ROOT_DIR / "equipment.json").read_text())

DEFAULT_COUNTS = {
    "TREADMILL": 20,
    "CLIMBMILL": 6,
    "ARC_TRAINER_LOW": 8,
    "ELLIPTICAL": 8,
    "UPRIGHT_CYCLE": 10,
    "ROWER": 6,
    "INDOOR_CYCLE": 10
}

TYPE_ORDER = [
    "TREADMILL",
    "CLIMBMILL",
    "ARC_TRAINER_LOW",
    "ELLIPTICAL",
    "UPRIGHT_CYCLE",
    "ROWER",
    "INDOOR_CYCLE"
]

DEFAULT_PLACEMENT_OPTIONS = {
    "row_cap": 17,
    "aisle_gap": 36.0,
    "align_aisles_across_rows": True,
    "full_row_trigger": 17,
    "full_row_side_margin": 36.0,
    "full_row_front_margin": 36.0,
    "full_row_back_aisle": 36.0,
    "enforce_collisions": True,
}


def _float_or_default(value, default: float, minimum: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, parsed)


def _int_or_default(value, default: int, minimum: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, parsed)


def _bool_or_default(value, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _sanitize_type_order(raw_order) -> list[str]:
    defaults = [eq for eq in TYPE_ORDER if eq in EQUIPMENT]
    if not isinstance(raw_order, list):
        return defaults

    seen = set()
    cleaned = []
    for item in raw_order:
        if not isinstance(item, str):
            continue
        if item in defaults and item not in seen:
            cleaned.append(item)
            seen.add(item)

    for item in defaults:
        if item not in seen:
            cleaned.append(item)
    return cleaned


def _sanitize_counts(raw_counts, type_order: list[str]) -> dict[str, int]:
    raw_counts = raw_counts if isinstance(raw_counts, dict) else {}
    return {
        eq_name: _int_or_default(raw_counts.get(eq_name, DEFAULT_COUNTS.get(eq_name, 0)), DEFAULT_COUNTS.get(eq_name, 0), minimum=0)
        for eq_name in type_order
    }


def _sanitize_placement(raw_placement) -> dict:
    raw_placement = raw_placement if isinstance(raw_placement, dict) else {}
    return {
        "row_cap": _int_or_default(raw_placement.get("row_cap"), DEFAULT_PLACEMENT_OPTIONS["row_cap"], minimum=1),
        "aisle_gap": _float_or_default(raw_placement.get("aisle_gap"), DEFAULT_PLACEMENT_OPTIONS["aisle_gap"], minimum=0.0),
        "align_aisles_across_rows": _bool_or_default(raw_placement.get("align_aisles_across_rows"), DEFAULT_PLACEMENT_OPTIONS["align_aisles_across_rows"]),
        "full_row_trigger": _int_or_default(raw_placement.get("full_row_trigger"), DEFAULT_PLACEMENT_OPTIONS["full_row_trigger"], minimum=1),
        "full_row_side_margin": _float_or_default(raw_placement.get("full_row_side_margin"), DEFAULT_PLACEMENT_OPTIONS["full_row_side_margin"], minimum=0.0),
        "full_row_front_margin": _float_or_default(raw_placement.get("full_row_front_margin"), DEFAULT_PLACEMENT_OPTIONS["full_row_front_margin"], minimum=0.0),
        "full_row_back_aisle": _float_or_default(raw_placement.get("full_row_back_aisle"), DEFAULT_PLACEMENT_OPTIONS["full_row_back_aisle"], minimum=0.0),
        "enforce_collisions": _bool_or_default(raw_placement.get("enforce_collisions"), DEFAULT_PLACEMENT_OPTIONS["enforce_collisions"]),
    }


def _merge_equipment_overrides(raw_overrides) -> dict:
    overrides = raw_overrides if isinstance(raw_overrides, dict) else {}
    merged = copy.deepcopy(EQUIPMENT)

    for eq_name, override in overrides.items():
        if eq_name not in merged or not isinstance(override, dict):
            continue

        target = merged[eq_name]
        if not isinstance(target, dict):
            continue

        for group_name in ("footprint", "clearance"):
            source_group = override.get(group_name)
            target_group = target.get(group_name)
            if not isinstance(source_group, dict) or not isinstance(target_group, dict):
                continue
            for key, value in source_group.items():
                if key not in target_group:
                    continue
                target_group[key] = _float_or_default(value, float(target_group[key]), minimum=0.0)

        if "requires_raceway" in override and "requires_raceway" in target:
            target["requires_raceway"] = _bool_or_default(override["requires_raceway"], bool(target["requires_raceway"]))
        if "block_angle_offset" in override and "block_angle_offset" in target:
            target["block_angle_offset"] = _float_or_default(override["block_angle_offset"], float(target["block_angle_offset"]))

    return merged


@app.get("/")
def index():
    return render_template(
        "index.html",
        equipment=EQUIPMENT,
        default_counts=DEFAULT_COUNTS,
        default_type_order=TYPE_ORDER,
        default_placement=DEFAULT_PLACEMENT_OPTIONS,
    )


@app.post("/api/layout")
def api_layout():
    payload = request.get_json(force=True) or {}
    W = _float_or_default(payload.get("w"), 2000.0, minimum=1.0)
    D = _float_or_default(payload.get("d"), 1000.0, minimum=1.0)
    type_order = _sanitize_type_order(payload.get("type_order"))
    counts = _sanitize_counts(payload.get("counts"), type_order)
    placement = _sanitize_placement(payload.get("placement"))
    include_debug = _bool_or_default(payload.get("include_debug"), True)
    equipment = _merge_equipment_overrides(payload.get("equipment_overrides"))

    result = place_layout(
        W=W,
        D=D,
        equipment=equipment,
        counts=counts,
        type_order=type_order,
        placement_options=placement,
        include_debug=include_debug,
    )
    result["input"] = {
        "w": W,
        "d": D,
        "type_order": type_order,
        "counts": counts,
        "placement": placement,
        "include_debug": include_debug,
    }
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
