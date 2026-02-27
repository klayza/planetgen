from dataclasses import asdict, dataclass
from typing import Dict, List, Tuple, Any, Optional


INCHES_PER_FOOT = 12.0


@dataclass
class Rect:
    x: float
    y: float
    w: float
    d: float  # depth in Y

    @property
    def x2(self) -> float:
        return self.x + self.w

    @property
    def y2(self) -> float:
        return self.y + self.d

    def intersects(self, other: "Rect") -> bool:
        return not (self.x2 <= other.x or other.x2 <= self.x or self.y2 <= other.y or other.y2 <= self.y)

    def within(self, W: float, D: float) -> bool:
        return self.x >= 0 and self.y >= 0 and self.x2 <= W and self.y2 <= D


@dataclass
class PlacementOptions:
    row_cap: int = 17
    aisle_gap: float = 36.0
    align_aisles_across_rows: bool = True
    full_row_trigger: int = 17
    full_row_side_margin: float = 36.0
    full_row_front_margin: float = 36.0
    enforce_collisions: bool = True


def _to_int(value: Any, fallback: int, minimum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, parsed)


def _to_float(value: Any, fallback: float, minimum: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, parsed)


def _to_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return fallback
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def parse_placement_options(raw: Optional[Dict[str, Any]]) -> PlacementOptions:
    raw = raw or {}
    return PlacementOptions(
        row_cap=_to_int(raw.get("row_cap"), fallback=17, minimum=1),
        aisle_gap=_to_float(raw.get("aisle_gap"), fallback=36.0, minimum=0.0),
        align_aisles_across_rows=_to_bool(raw.get("align_aisles_across_rows"), fallback=True),
        full_row_trigger=_to_int(raw.get("full_row_trigger"), fallback=17, minimum=1),
        full_row_side_margin=_to_float(raw.get("full_row_side_margin"), fallback=36.0, minimum=0.0),
        full_row_front_margin=_to_float(raw.get("full_row_front_margin"), fallback=36.0, minimum=0.0),
        enforce_collisions=_to_bool(raw.get("enforce_collisions"), fallback=True),
    )


def get_raceway_dims(equipment: Dict[str, Any]) -> Tuple[float, float]:
    r = equipment["RACEWAY"]["footprint"]
    return float(r["w"]), float(r["d"])


def is_powered(eq: Dict[str, Any]) -> bool:
    return bool(eq.get("requires_raceway", False))


def place_layout(
    W: float,
    D: float,
    equipment: Dict[str, Any],
    counts: Dict[str, int],
    type_order: List[str],
    placement_options: Optional[Dict[str, Any]] = None,
    include_debug: bool = True,
) -> Dict[str, Any]:
    opts = parse_placement_options(placement_options)
    raceway_w, raceway_d = get_raceway_dims(equipment)

    placed: List[Dict[str, Any]] = []
    occupied: List[Rect] = []  # occupied rectangles (machine + raceway, no clearance)
    debug_rows: List[Dict[str, Any]] = []

    requested_by_type: Dict[str, int] = {eq_name: max(0, int(counts.get(eq_name, 0))) for eq_name in type_order}
    remaining_by_type: Dict[str, int] = dict(requested_by_type)

    specs: Dict[str, Dict[str, Any]] = {}
    for eq_name in type_order:
        eq = equipment[eq_name]
        if eq.get("default_orientation") != "north":
            raise ValueError("MVP supports north-only placement")
        fp = eq["footprint"]
        cl = eq["clearance"]
        fp_w = float(fp["w"])
        fp_d = float(fp["d"])
        cl_l = float(cl["left"])
        cl_r = float(cl["right"])
        cl_b = float(cl["back"])
        powered = is_powered(eq)
        occ_w = max(fp_w, raceway_w) if powered else fp_w
        slot_w = cl_l + occ_w + cl_r
        specs[eq_name] = {
            "powered": powered,
            "fp_w": fp_w,
            "fp_d": fp_d,
            "cl_l": cl_l,
            "cl_r": cl_r,
            "cl_b": cl_b,
            "slot_w": slot_w,
        }

    powered_order = [eq_name for eq_name in type_order if specs[eq_name]["powered"]]
    nonpowered_order = [eq_name for eq_name in type_order if not specs[eq_name]["powered"]]
    y_cursor = D  # top of remaining space
    aligned_aisle_bands: List[Tuple[float, float]] = []

    def build_row(
        snapshot_remaining: Dict[str, int],
        side_margin: float,
        front_margin: float,
        full_row: bool,
        aisle_bands: List[Tuple[float, float]],
    ) -> Dict[str, Any]:
        row_ref_y = min(D - front_margin, y_cursor)
        usable_w = W - 2.0 * side_margin

        normalized_bands: List[Tuple[float, float]] = []
        for start, end in sorted(aisle_bands, key=lambda b: b[0]):
            clip_start = max(side_margin, float(start))
            clip_end = min(W - side_margin, float(end))
            if clip_end - clip_start > 1e-9:
                normalized_bands.append((clip_start, clip_end))

        attempt: Dict[str, Any] = {
            "equipment": "MIXED",
            "requested": int(sum(snapshot_remaining.values())),
            "row_cap_config": opts.row_cap,
            "aisle_gap_config": opts.aisle_gap,
            "y_cursor_start": y_cursor,
            "row_ref_y": row_ref_y,
            "raceway": {"w": raceway_w, "d": raceway_d},
            "margins": {"side": side_margin, "front": front_margin},
            "usable_w": usable_w,
            "full_row": full_row,
            "align_aisles_across_rows": opts.align_aisles_across_rows,
            "enforce_collisions": opts.enforce_collisions,
            "aisle_bands_input": [{"x1": b[0], "x2": b[1]} for b in normalized_bands],
        }

        if usable_w <= 0:
            attempt["placed"] = 0
            attempt["reason"] = "no_usable_width_after_margins"
            attempt["sequence"] = []
            attempt["consumed"] = {}
            attempt["y_cursor_end"] = y_cursor
            attempt["raceway_connected"] = True
            attempt["aisle_bands_used"] = []
            attempt["aisle_bands_generated"] = []
            return {
                "attempt": attempt,
                "items": [],
                "rects": [],
                "consumed": {},
                "new_y": y_cursor,
                "aisle_bands_generated": [],
            }

        if row_ref_y <= 0:
            attempt["placed"] = 0
            attempt["reason"] = "insufficient_depth"
            attempt["sequence"] = []
            attempt["consumed"] = {}
            attempt["y_cursor_end"] = y_cursor
            attempt["raceway_connected"] = True
            attempt["aisle_bands_used"] = []
            attempt["aisle_bands_generated"] = []
            return {
                "attempt": attempt,
                "items": [],
                "rects": [],
                "consumed": {},
                "new_y": y_cursor,
                "aisle_bands_generated": [],
            }

        local_remaining = dict(snapshot_remaining)
        max_slots = int(sum(local_remaining.values()))
        attempt["target_items"] = max_slots
        consumed: Dict[str, int] = {eq_name: 0 for eq_name in type_order}
        row_items: List[Dict[str, Any]] = []
        row_rects: List[Rect] = []
        cursor_x = side_margin
        right_limit = W - side_margin
        row_depth_with_clearance = 0.0
        stop_reason = "all_items_placed"
        placed_since_aisle = 0
        used_aisles: List[Tuple[float, float]] = []
        generated_aisles: List[Tuple[float, float]] = []

        def find_next_aisle(x_value: float) -> Optional[Tuple[float, float]]:
            for band in normalized_bands:
                if band[1] > x_value + 1e-9:
                    return band
            return None

        slot_index = 0
        guard = 0
        max_iterations = max(1, max_slots * 6)
        while slot_index < max_slots and guard < max_iterations:
            guard += 1
            candidates = [eq_name for eq_name in (powered_order + nonpowered_order) if local_remaining.get(eq_name, 0) > 0]
            if not candidates:
                stop_reason = "no_remaining_items"
                break

            next_aisle = find_next_aisle(cursor_x)
            if next_aisle is not None and cursor_x >= next_aisle[0] - 1e-9:
                cursor_x = max(cursor_x, next_aisle[1])
                used_aisles.append(next_aisle)
                placed_since_aisle = 0
                if cursor_x >= right_limit - 1e-9:
                    stop_reason = f"no_width_after_aligned_aisle_{slot_index}"
                    break
                continue

            using_aligned_aisles = opts.align_aisles_across_rows and len(normalized_bands) > 0
            if (
                not using_aligned_aisles
                and opts.row_cap > 0
                and placed_since_aisle >= opts.row_cap
            ):
                aisle_start = cursor_x
                aisle_end = min(cursor_x + opts.aisle_gap, right_limit)
                if aisle_end - aisle_start <= 1e-9:
                    stop_reason = f"no_width_for_aisle_at_index_{slot_index}"
                    break
                generated_aisles.append((aisle_start, aisle_end))
                cursor_x = aisle_end
                placed_since_aisle = 0
                if cursor_x >= right_limit - 1e-9:
                    stop_reason = f"no_width_after_generated_aisle_{slot_index}"
                    break
                continue

            next_aisle = find_next_aisle(cursor_x)
            segment_limit = right_limit
            if next_aisle is not None and next_aisle[0] > cursor_x + 1e-9:
                segment_limit = min(segment_limit, next_aisle[0])

            selected = None
            failures: List[str] = []
            for eq_name in candidates:
                spec = specs[eq_name]
                slot_w = spec["slot_w"]
                if slot_w <= 0:
                    failures.append("invalid_slot_width")
                    continue
                if cursor_x + slot_w > segment_limit + 1e-9:
                    failures.append("no_width")
                    continue

                occ_y = row_ref_y - raceway_d - spec["fp_d"]
                row_bottom = row_ref_y - raceway_d - spec["fp_d"] - spec["cl_b"]
                if row_bottom < -1e-9:
                    failures.append("insufficient_depth")
                    continue

                machine_x = cursor_x + (slot_w - spec["fp_w"]) / 2.0
                machine_rect = Rect(machine_x, occ_y, spec["fp_w"], spec["fp_d"])
                if spec["powered"]:
                    # Powered slots use a slot-wide raceway so adjacent powered slots form one connected path.
                    race_rect = Rect(cursor_x, row_ref_y - raceway_d, slot_w, raceway_d)
                    occ_rect = Rect(cursor_x, occ_y, slot_w, spec["fp_d"] + raceway_d)
                else:
                    race_rect = None
                    occ_rect = Rect(cursor_x, occ_y, slot_w, spec["fp_d"])

                if not occ_rect.within(W, D):
                    failures.append("bounds_violation")
                    continue

                collision = opts.enforce_collisions and any(occ_rect.intersects(r) for r in occupied)
                if collision:
                    failures.append("collision")
                    continue

                selected = (eq_name, spec, slot_w, occ_rect, machine_rect, race_rect)
                break

            if selected is None:
                if failures and all(f == "no_width" for f in failures):
                    next_aisle = find_next_aisle(cursor_x)
                    if next_aisle is not None and next_aisle[0] > cursor_x + 1e-9:
                        cursor_x = next_aisle[1]
                        used_aisles.append(next_aisle)
                        placed_since_aisle = 0
                        if cursor_x >= right_limit - 1e-9:
                            stop_reason = f"no_width_after_aligned_aisle_{slot_index}"
                            break
                        continue
                    stop_reason = f"no_width_at_index_{slot_index}"
                elif failures and all(f == "insufficient_depth" for f in failures):
                    stop_reason = f"insufficient_depth_at_index_{slot_index}"
                elif "collision" in failures:
                    stop_reason = f"collision_at_index_{slot_index}"
                elif failures and all(f == "invalid_slot_width" for f in failures):
                    stop_reason = f"invalid_slot_width_at_index_{slot_index}"
                else:
                    stop_reason = f"no_fit_at_index_{slot_index}"
                break

            eq_name, spec, slot_w, occ_rect, machine_rect, race_rect = selected
            row_items.append({
                "type": eq_name,
                "orientation": "north",
                "occupied": {"x": occ_rect.x, "y": occ_rect.y, "w": occ_rect.w, "d": occ_rect.d},
                "machine": {"x": machine_rect.x, "y": machine_rect.y, "w": machine_rect.w, "d": machine_rect.d},
                "raceway": (
                    {"x": race_rect.x, "y": race_rect.y, "w": race_rect.w, "d": race_rect.d}
                    if race_rect else None
                ),
            })
            row_rects.append(occ_rect)
            consumed[eq_name] += 1
            local_remaining[eq_name] -= 1
            cursor_x += slot_w
            placed_since_aisle += 1
            row_depth_with_clearance = max(row_depth_with_clearance, spec["fp_d"] + spec["cl_b"])
            slot_index += 1

        placed_in_row = len(row_items)
        attempt["placed"] = placed_in_row
        attempt["reason"] = stop_reason
        attempt["sequence"] = [item["type"] for item in row_items]
        attempt["consumed"] = {eq_name: count for eq_name, count in consumed.items() if count > 0}
        attempt["aisle_bands_used"] = [{"x1": b[0], "x2": b[1]} for b in used_aisles]
        attempt["aisle_bands_generated"] = [{"x1": b[0], "x2": b[1]} for b in generated_aisles]

        raceways = [item["raceway"] for item in row_items if item["raceway"] is not None]
        raceway_connected = True
        all_row_aisles = normalized_bands + generated_aisles
        if len(raceways) > 1:
            for i in range(1, len(raceways)):
                prev = raceways[i - 1]
                curr = raceways[i]
                prev_end = prev["x"] + prev["w"]
                gap = curr["x"] - prev_end
                if abs(gap) <= 1e-6:
                    continue
                bridge_ok = any(
                    abs(prev_end - band[0]) <= 1e-6 and abs(curr["x"] - band[1]) <= 1e-6
                    for band in all_row_aisles
                )
                if not bridge_ok:
                    raceway_connected = False
                    break
        attempt["raceway_connected"] = raceway_connected

        if placed_in_row <= 0:
            attempt["row_bottom_with_back_clearance"] = y_cursor
            attempt["y_cursor_end"] = y_cursor
            return {
                "attempt": attempt,
                "items": [],
                "rects": [],
                "consumed": {},
                "new_y": y_cursor,
                "aisle_bands_generated": generated_aisles,
            }

        new_y = row_ref_y - raceway_d - row_depth_with_clearance
        attempt["row_bottom_with_back_clearance"] = new_y
        attempt["y_cursor_end"] = new_y
        return {
            "attempt": attempt,
            "items": row_items,
            "rects": row_rects,
            "consumed": {eq_name: count for eq_name, count in consumed.items() if count > 0},
            "new_y": new_y,
            "aisle_bands_generated": generated_aisles,
        }

    def remaining_total() -> int:
        return sum(max(0, int(v)) for v in remaining_by_type.values())

    while remaining_total() > 0:
        base_row = build_row(
            remaining_by_type,
            side_margin=0.0,
            front_margin=0.0,
            full_row=False,
            aisle_bands=aligned_aisle_bands,
        )
        if base_row["attempt"]["placed"] <= 0:
            debug_rows.append(base_row["attempt"])
            break

        final_row = base_row
        if base_row["attempt"]["placed"] >= opts.full_row_trigger:
            margined_row = build_row(
                remaining_by_type,
                side_margin=opts.full_row_side_margin,
                front_margin=opts.full_row_front_margin,
                full_row=True,
                aisle_bands=aligned_aisle_bands,
            )
            if margined_row["attempt"]["placed"] > 0:
                final_row = margined_row
            else:
                final_row["attempt"]["margin_fallback_reason"] = margined_row["attempt"]["reason"]

        debug_rows.append(final_row["attempt"])

        for item in final_row["items"]:
            placed.append(item)
        for rect in final_row["rects"]:
            occupied.append(rect)
        for eq_name, used in final_row["consumed"].items():
            remaining_by_type[eq_name] = max(0, remaining_by_type[eq_name] - used)

        if opts.align_aisles_across_rows and len(aligned_aisle_bands) == 0:
            aligned_aisle_bands = list(final_row.get("aisle_bands_generated", []))

        y_cursor = float(final_row["new_y"])
        if y_cursor <= 0:
            break

    unplaced: Dict[str, int] = {eq_name: count for eq_name, count in remaining_by_type.items() if count > 0}

    result: Dict[str, Any] = {
        "gym": {"w": W, "d": D},
        "placed": placed,
        "unplaced": unplaced,
    }

    if include_debug:
        placed_by_type: Dict[str, int] = {}
        for item in placed:
            name = item["type"]
            placed_by_type[name] = placed_by_type.get(name, 0) + 1

        by_type = []
        for eq_name in type_order:
            requested = requested_by_type.get(eq_name, 0)
            placed_count = placed_by_type.get(eq_name, 0)
            unplaced_count = max(0, requested - placed_count)
            by_type.append({
                "equipment": eq_name,
                "requested": requested,
                "placed": placed_count,
                "unplaced": unplaced_count,
            })

        occupied_area = sum(r.w * r.d for r in occupied)
        gym_area = max(1.0, W * D)

        result["debug"] = {
            "options": asdict(opts),
            "summary": {
                "requested_total": sum(requested_by_type.values()),
                "placed_total": len(placed),
                "unplaced_total": sum(unplaced.values()),
                "rows_attempted": len(debug_rows),
                "rows_successful": sum(1 for row in debug_rows if row.get("placed", 0) > 0),
                "occupied_area": occupied_area,
                "occupancy_ratio": occupied_area / gym_area,
            },
            "by_type": by_type,
            "rows": debug_rows,
        }

    return result
