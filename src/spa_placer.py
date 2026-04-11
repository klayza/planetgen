from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple


EDGE_ORDER = ("north", "east", "south", "west")
ROOM_MACHINE_GAP = 18.0
MIN_SUBROOM_DOOR_WIDTH = 24.0
DEFAULT_SHELL = {"w": 1100.0, "d": 800.0}
DEFAULT_FULL_HEIGHT_WALL = 120.0
DEFAULT_PARTIAL_HEIGHT_WALL = 50.0


@dataclass
class Rect:
    x: float
    y: float
    w: float
    d: float

    @property
    def x2(self) -> float:
        return self.x + self.w

    @property
    def y2(self) -> float:
        return self.y + self.d

    def to_dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y, "w": self.w, "d": self.d}


def _float_or_default(value: Any, default: float, minimum: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, parsed)


def _int_or_default(value: Any, default: int, minimum: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, parsed)


def _bool_or_default(value: Any, default: bool) -> bool:
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


def _clamp(value: float, minimum: float, maximum: float) -> float:
    if maximum < minimum:
        return maximum
    return min(maximum, max(minimum, value))


def _sanitize_edge(value: Any, default: str = "south") -> str:
    return value if isinstance(value, str) and value in EDGE_ORDER else default


def _opposite_edge(edge: str) -> str:
    return {
        "north": "south",
        "south": "north",
        "east": "west",
        "west": "east",
    }[edge]


def build_room_spec_index(spa_spec: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    rooms = spa_spec.get("black_card_spa", {}).get("rooms", [])
    index: Dict[str, Dict[str, Any]] = {}
    for room in rooms:
        if not isinstance(room, dict):
            continue
        room_type = room.get("room_type")
        if not isinstance(room_type, str):
            continue
        machine_types = room.get("machine_types") or []
        room_copy = dict(room)
        room_copy["machine_type_names"] = [
            item.get("machine_type")
            for item in machine_types
            if isinstance(item, dict) and isinstance(item.get("machine_type"), str)
        ]
        index[room_type] = room_copy
    return index


def build_spa_defaults(spa_spec: Dict[str, Any]) -> Dict[str, Any]:
    room_specs = build_room_spec_index(spa_spec)
    lounge_spec = room_specs["lounge"]
    room_defaults: Dict[str, Any] = {}

    for room_type, spec in room_specs.items():
        if room_type == "lounge":
            continue
        count = _int_or_default(spec.get("default_room_count"), 0, minimum=0)
        default_variant = spec.get("default_variant")
        machine_types = spec.get("machine_type_names") or []
        if default_variant not in machine_types and machine_types:
            default_variant = machine_types[0]
        room_defaults[room_type] = {
            "count": count,
            "instances": [
                {
                    "variant": default_variant,
                    "door_width": _float_or_default(spec.get("default_door_width"), 36.0, minimum=MIN_SUBROOM_DOOR_WIDTH),
                    "machine_count": _int_or_default(spec.get("default_machine_count_per_room"), 1, minimum=0),
                }
                for _ in range(count)
            ],
        }

    lounge_size = lounge_spec.get("default_size") or {}
    return {
        "shell": dict(DEFAULT_SHELL),
        "entry_edge": "south",
        "lounge": {
            "auto_size": True,
            "w": _float_or_default(lounge_size.get("w"), 216.0, minimum=96.0),
            "d": _float_or_default(lounge_size.get("d"), 168.0, minimum=96.0),
        },
        "rooms": room_defaults,
        "include_debug": True,
    }


def sanitize_spa_request(payload: Dict[str, Any], spa_spec: Dict[str, Any]) -> Dict[str, Any]:
    room_specs = build_room_spec_index(spa_spec)
    defaults = build_spa_defaults(spa_spec)
    shell_raw = payload.get("shell") if isinstance(payload, dict) else {}
    shell_w = _float_or_default((shell_raw or {}).get("w"), defaults["shell"]["w"], minimum=120.0)
    shell_d = _float_or_default((shell_raw or {}).get("d"), defaults["shell"]["d"], minimum=120.0)

    lounge_spec = room_specs["lounge"]
    lounge_raw = payload.get("lounge") if isinstance(payload, dict) else {}
    lounge_defaults = defaults["lounge"]
    auto_size = _bool_or_default((lounge_raw or {}).get("auto_size"), lounge_defaults["auto_size"])
    requested_lounge_w = _float_or_default((lounge_raw or {}).get("w"), lounge_defaults["w"], minimum=96.0)
    requested_lounge_d = _float_or_default((lounge_raw or {}).get("d"), lounge_defaults["d"], minimum=96.0)

    if auto_size:
        target_w = max(requested_lounge_w, shell_w * 0.30)
        target_d = max(requested_lounge_d, shell_d * 0.28)
    else:
        target_w = requested_lounge_w
        target_d = requested_lounge_d

    max_lounge_w = max(96.0, shell_w - 96.0)
    max_lounge_d = max(96.0, shell_d - 96.0)
    lounge = {
        "auto_size": auto_size,
        "w": _clamp(target_w, 96.0, max_lounge_w),
        "d": _clamp(target_d, 96.0, max_lounge_d),
        "entry_door_width": _float_or_default(
            (lounge_spec.get("entry_door") or {}).get("door_clear_width"),
            _float_or_default(lounge_spec.get("default_door_width"), 36.0, minimum=36.0),
            minimum=36.0,
        ),
    }

    raw_rooms = payload.get("rooms") if isinstance(payload, dict) else {}
    sanitized_rooms: Dict[str, Dict[str, Any]] = {}
    for room_type, spec in room_specs.items():
        if room_type == "lounge":
            continue
        room_default = defaults["rooms"][room_type]
        raw_room = raw_rooms.get(room_type) if isinstance(raw_rooms, dict) else None
        room_count = _int_or_default((raw_room or {}).get("count"), room_default["count"], minimum=0)
        if _bool_or_default(spec.get("fixed_room_count"), False):
            room_count = 1 if room_count > 0 or room_default["count"] > 0 else 0
        machine_types = spec.get("machine_type_names") or []
        default_variant = spec.get("default_variant")
        if default_variant not in machine_types and machine_types:
            default_variant = machine_types[0]

        raw_instances = (raw_room or {}).get("instances")
        raw_instances = raw_instances if isinstance(raw_instances, list) else []
        default_door_width = _float_or_default(spec.get("default_door_width"), 36.0, minimum=MIN_SUBROOM_DOOR_WIDTH)
        default_machine_count = _int_or_default(spec.get("default_machine_count_per_room"), 1, minimum=0)
        minimum_machine_count = _int_or_default(
            spec.get("minimum_machine_count_per_room"),
            default_machine_count,
            minimum=0,
        )

        instances = []
        for index in range(room_count):
            raw_instance = raw_instances[index] if index < len(raw_instances) and isinstance(raw_instances[index], dict) else {}
            variant = raw_instance.get("variant")
            if variant not in machine_types:
                variant = default_variant
            door_width = _float_or_default(raw_instance.get("door_width"), default_door_width, minimum=MIN_SUBROOM_DOOR_WIDTH)
            machine_count = _int_or_default(raw_instance.get("machine_count"), default_machine_count, minimum=minimum_machine_count)
            instances.append(
                {
                    "variant": variant,
                    "door_width": door_width,
                    "machine_count": machine_count,
                }
            )
        sanitized_rooms[room_type] = {"count": room_count, "instances": instances}

    return {
        "shell": {"w": shell_w, "d": shell_d},
        "entry_edge": _sanitize_edge(payload.get("entry_edge") if isinstance(payload, dict) else None),
        "lounge": lounge,
        "rooms": sanitized_rooms,
        "include_debug": _bool_or_default(payload.get("include_debug") if isinstance(payload, dict) else None, True),
    }


def _estimate_room_size(
    room_spec: Dict[str, Any],
    equipment_spec: Dict[str, Any],
    machine_count: int,
    door_width: float,
) -> Dict[str, float]:
    layout_rules = room_spec.get("layout_rules") or {}
    if layout_rules.get("layout_pattern") == "two_wing":
        slot_w = _float_or_default(layout_rules.get("wing_machine_slot_width"), 55.0, minimum=1.0)
        center_opening = _float_or_default(layout_rules.get("center_opening_width"), max(door_width + 12.0, 72.0), minimum=door_width)
        bottom_offset = _float_or_default(layout_rules.get("bottom_wall_to_machine"), 52.0, minimum=0.0)
        top_clearance = _float_or_default(
            layout_rules.get("top_wall_to_machine"),
            max(_float_or_default((equipment_spec.get("clearance") or {}).get("back"), 12.0, minimum=0.0), 15.0),
            minimum=0.0,
        )
        left_count = max(1, (machine_count + 1) // 2)
        right_count = max(1, machine_count // 2)
        span = (left_count * slot_w) + center_opening + (right_count * slot_w)
        depth = bottom_offset + _float_or_default((equipment_spec.get("footprint") or {}).get("d"), 0.0, minimum=0.0) + top_clearance
        return {
            "layout_pattern": "two_wing",
            "span": span,
            "depth": depth,
            "slot_w": slot_w,
            "center_opening_width": center_opening,
            "bottom_wall_to_machine": bottom_offset,
            "top_wall_to_machine": top_clearance,
            "machine_w": _float_or_default((equipment_spec.get("footprint") or {}).get("w"), 0.0, minimum=0.0),
            "machine_d": _float_or_default((equipment_spec.get("footprint") or {}).get("d"), 0.0, minimum=0.0),
            "left_count": left_count,
            "right_count": right_count,
            "partial_height_divider_required": _bool_or_default(layout_rules.get("partial_height_divider_required"), False),
            "partial_height_divider_height": _float_or_default(
                layout_rules.get("partial_height_divider_height"),
                DEFAULT_PARTIAL_HEIGHT_WALL,
                minimum=0.0,
            ),
        }

    footprint = equipment_spec.get("footprint") or {}
    clearance = equipment_spec.get("clearance") or {}
    machine_w = _float_or_default(footprint.get("w"), 0.0, minimum=0.0)
    machine_d = _float_or_default(footprint.get("d"), 0.0, minimum=0.0)
    left = _float_or_default(clearance.get("left"), 0.0, minimum=0.0)
    right = _float_or_default(clearance.get("right"), 0.0, minimum=0.0)
    front = _float_or_default(clearance.get("front"), 0.0, minimum=0.0)
    back = _float_or_default(clearance.get("back"), 0.0, minimum=0.0)
    divider_gap = ROOM_MACHINE_GAP if machine_count > 1 else 0.0

    span = max(door_width + 12.0, left + right + (machine_count * machine_w) + max(0, machine_count - 1) * divider_gap)
    depth = front + machine_d + back

    if room_spec.get("tv_required"):
        depth += 12.0

    return {
        "layout_pattern": "linear",
        "span": span,
        "depth": depth,
        "machine_w": machine_w,
        "machine_d": machine_d,
        "left": left,
        "right": right,
        "front": front,
        "back": back,
        "divider_gap": divider_gap,
    }


def _hydromassage_local_rects(size: Dict[str, float]) -> Tuple[List[Rect], List[Dict[str, Any]]]:
    left_count = max(1, int(size["left_count"]))
    right_count = max(1, int(size["right_count"]))
    slot_w = float(size["slot_w"])
    center_opening = float(size["center_opening_width"])
    machine_w = float(size["machine_w"])
    machine_d = float(size["machine_d"])
    bottom_offset = float(size["bottom_wall_to_machine"])
    left_start = 0.0
    right_start = left_count * slot_w + center_opening
    machine_y = bottom_offset
    local_rects: List[Rect] = []

    for index in range(left_count):
        slot_x = left_start + index * slot_w
        machine_x = slot_x + max(0.0, (slot_w - machine_w) / 2.0)
        local_rects.append(Rect(machine_x, machine_y, machine_w, machine_d))

    for index in range(right_count):
        slot_x = right_start + index * slot_w
        machine_x = slot_x + max(0.0, (slot_w - machine_w) / 2.0)
        local_rects.append(Rect(machine_x, machine_y, machine_w, machine_d))

    partitions: List[Dict[str, Any]] = []
    if size.get("partial_height_divider_required"):
        wall_height = _float_or_default(size.get("partial_height_divider_height"), DEFAULT_PARTIAL_HEIGHT_WALL, minimum=0.0)
        depth = float(size["depth"])
        divider_length = min(max(42.0, depth * 0.48), max(42.0, depth - bottom_offset - 6.0))
        y1 = max(0.0, depth - divider_length)
        y2 = depth
        divider_x_positions = []

        for index in range(1, left_count):
            divider_x_positions.append(index * slot_w)

        divider_x_positions.append(left_count * slot_w)
        divider_x_positions.append(left_count * slot_w + center_opening)

        wing_start = left_count * slot_w + center_opening
        for index in range(1, right_count):
            divider_x_positions.append(wing_start + index * slot_w)

        for divider_x in divider_x_positions:
            partitions.append(
                {
                    "x1": divider_x,
                    "y1": y1,
                    "x2": divider_x,
                    "y2": y2,
                    "wall_type": "partial_height",
                    "full_height": False,
                    "height": wall_height,
                    "source": "room_feature",
                    "edge": "interior",
                }
            )

    return local_rects, partitions


def _transform_local_rect(local_rect: Rect, room_rect: Rect, open_edge: str) -> Rect:
    if open_edge == "north":
        return Rect(room_rect.x + local_rect.x, room_rect.y + local_rect.y, local_rect.w, local_rect.d)
    if open_edge == "south":
        return Rect(
            room_rect.x + (room_rect.w - (local_rect.x + local_rect.w)),
            room_rect.y + (room_rect.d - (local_rect.y + local_rect.d)),
            local_rect.w,
            local_rect.d,
        )
    if open_edge == "east":
        return Rect(
            room_rect.x + local_rect.y,
            room_rect.y + (room_rect.d - (local_rect.x + local_rect.w)),
            local_rect.d,
            local_rect.w,
        )
    return Rect(
        room_rect.x + (room_rect.w - (local_rect.y + local_rect.d)),
        room_rect.y + local_rect.x,
        local_rect.d,
        local_rect.w,
    )


def _transform_local_segment(segment: Dict[str, Any], room_rect: Rect, open_edge: str) -> Dict[str, Any]:
    x1 = float(segment["x1"])
    y1 = float(segment["y1"])
    x2 = float(segment["x2"])
    y2 = float(segment["y2"])
    width = room_rect.w
    depth = room_rect.d

    if open_edge == "north":
        transformed = {
            "x1": room_rect.x + x1,
            "y1": room_rect.y + y1,
            "x2": room_rect.x + x2,
            "y2": room_rect.y + y2,
        }
    elif open_edge == "south":
        transformed = {
            "x1": room_rect.x + (width - x1),
            "y1": room_rect.y + (depth - y1),
            "x2": room_rect.x + (width - x2),
            "y2": room_rect.y + (depth - y2),
        }
    elif open_edge == "east":
        transformed = {
            "x1": room_rect.x + y1,
            "y1": room_rect.y + (depth - x1),
            "x2": room_rect.x + y2,
            "y2": room_rect.y + (depth - x2),
        }
    else:
        transformed = {
            "x1": room_rect.x + (width - y1),
            "y1": room_rect.y + x1,
            "x2": room_rect.x + (width - y2),
            "y2": room_rect.y + x2,
        }

    if transformed["x1"] > transformed["x2"]:
        transformed["x1"], transformed["x2"] = transformed["x2"], transformed["x1"]
    if transformed["y1"] > transformed["y2"]:
        transformed["y1"], transformed["y2"] = transformed["y2"], transformed["y1"]
    for key in ("wall_type", "full_height", "height", "source", "edge"):
        if key in segment:
            transformed[key] = segment[key]
    return transformed


def _build_machine_placements(
    room: Dict[str, Any],
    room_rect: Rect,
    attached_edge: str,
    equipment_spec: Dict[str, Any],
    size: Dict[str, float],
) -> List[Dict[str, Any]]:
    count = room["machine_count"]
    machine_type = room["variant"]
    block_rotation = _float_or_default(equipment_spec.get("block_angle_offset"), 0.0, minimum=0.0)
    open_edge = _opposite_edge(attached_edge)
    edge_rotation = {
        "north": 180.0,
        "east": 270.0,
        "south": 0.0,
        "west": 90.0,
    }[attached_edge]
    placements: List[Dict[str, Any]] = []

    if size.get("layout_pattern") == "two_wing":
        local_rects, _ = _hydromassage_local_rects(size)
        for index, local_rect in enumerate(local_rects[:count]):
            machine_rect = _transform_local_rect(local_rect, room_rect, open_edge=open_edge)
            placements.append(
                {
                    "id": f"{room['id']}-machine-{index + 1}",
                    "room_id": room["id"],
                    "room_type": room["room_type"],
                    "type": machine_type,
                    "block_name": equipment_spec.get("block_name"),
                    "orientation": attached_edge,
                    "rotation": (block_rotation + edge_rotation) % 360.0,
                    "scale": {"x": 1, "y": 1, "z": 1},
                    "insertion_point": {"x": machine_rect.x, "y": machine_rect.y, "z": 0},
                    "machine": machine_rect.to_dict(),
                }
            )
        return placements

    if attached_edge in {"north", "south"}:
        total_machine_span = (count * size["machine_w"]) + max(0, count - 1) * size["divider_gap"]
        start_x = room_rect.x + max(0.0, (room_rect.w - total_machine_span) / 2.0)
        machine_y = room_rect.y + max(0.0, (room_rect.d - size["machine_d"]) / 2.0)
        for index in range(count):
            machine_x = start_x + index * (size["machine_w"] + size["divider_gap"])
            machine_rect = Rect(machine_x, machine_y, size["machine_w"], size["machine_d"])
            placements.append(
                {
                    "id": f"{room['id']}-machine-{index + 1}",
                    "room_id": room["id"],
                    "room_type": room["room_type"],
                    "type": machine_type,
                    "block_name": equipment_spec.get("block_name"),
                    "orientation": attached_edge,
                    "rotation": (block_rotation + edge_rotation) % 360.0,
                    "scale": {"x": 1, "y": 1, "z": 1},
                    "insertion_point": {"x": machine_rect.x, "y": machine_rect.y, "z": 0},
                    "machine": machine_rect.to_dict(),
                }
            )
    else:
        total_machine_span = (count * size["machine_w"]) + max(0, count - 1) * size["divider_gap"]
        start_y = room_rect.y + max(0.0, (room_rect.d - total_machine_span) / 2.0)
        machine_x = room_rect.x + max(0.0, (room_rect.w - size["machine_d"]) / 2.0)
        for index in range(count):
            machine_y = start_y + index * (size["machine_w"] + size["divider_gap"])
            machine_rect = Rect(machine_x, machine_y, size["machine_d"], size["machine_w"])
            placements.append(
                {
                    "id": f"{room['id']}-machine-{index + 1}",
                    "room_id": room["id"],
                    "room_type": room["room_type"],
                    "type": machine_type,
                    "block_name": equipment_spec.get("block_name"),
                    "orientation": attached_edge,
                    "rotation": (block_rotation + edge_rotation) % 360.0,
                    "scale": {"x": 1, "y": 1, "z": 1},
                    "insertion_point": {"x": machine_rect.x, "y": machine_rect.y, "z": 0},
                    "machine": machine_rect.to_dict(),
                }
            )

    return placements


def _opening_offset(rect: Rect, edge: str, width: float) -> float:
    if edge in {"north", "south"}:
        return max(0.0, (rect.w - width) / 2.0)
    return max(0.0, (rect.d - width) / 2.0)


def _edge_opening_to_segment(rect: Rect, edge: str, offset: float, width: float) -> Dict[str, float]:
    if edge == "north":
        return {"x1": rect.x + offset, "y1": rect.y2, "x2": rect.x + offset + width, "y2": rect.y2}
    if edge == "south":
        return {"x1": rect.x + offset, "y1": rect.y, "x2": rect.x + offset + width, "y2": rect.y}
    if edge == "east":
        return {"x1": rect.x2, "y1": rect.y + offset, "x2": rect.x2, "y2": rect.y + offset + width}
    return {"x1": rect.x, "y1": rect.y + offset, "x2": rect.x, "y2": rect.y + offset + width}


def _split_ranges(length: float, openings: Iterable[Tuple[float, float]]) -> List[Tuple[float, float]]:
    merged: List[Tuple[float, float]] = []
    for start, end in sorted(openings, key=lambda item: item[0]):
        clipped_start = max(0.0, min(length, start))
        clipped_end = max(0.0, min(length, end))
        if clipped_end <= clipped_start:
            continue
        if not merged or clipped_start > merged[-1][1]:
            merged.append((clipped_start, clipped_end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], clipped_end))

    segments: List[Tuple[float, float]] = []
    cursor = 0.0
    for start, end in merged:
        if start > cursor:
            segments.append((cursor, start))
        cursor = end
    if cursor < length:
        segments.append((cursor, length))
    return segments


def _rect_wall_segments(rect: Rect, source: str, source_id: str, openings: Iterable[Dict[str, float]]) -> List[Dict[str, Any]]:
    openings_by_edge = {edge: [] for edge in EDGE_ORDER}
    for opening in openings:
        edge = opening.get("edge")
        if edge not in openings_by_edge:
            continue
        start = _float_or_default(opening.get("offset"), 0.0, minimum=0.0)
        width = _float_or_default(opening.get("width"), 0.0, minimum=0.0)
        openings_by_edge[edge].append((start, start + width))

    wall_segments: List[Dict[str, Any]] = []
    for edge in EDGE_ORDER:
        length = rect.w if edge in {"north", "south"} else rect.d
        for start, end in _split_ranges(length, openings_by_edge[edge]):
            if edge == "north":
                segment = {"x1": rect.x + start, "y1": rect.y2, "x2": rect.x + end, "y2": rect.y2}
            elif edge == "south":
                segment = {"x1": rect.x + start, "y1": rect.y, "x2": rect.x + end, "y2": rect.y}
            elif edge == "east":
                segment = {"x1": rect.x2, "y1": rect.y + start, "x2": rect.x2, "y2": rect.y + end}
            else:
                segment = {"x1": rect.x, "y1": rect.y + start, "x2": rect.x, "y2": rect.y + end}
            segment["source"] = source
            segment["source_id"] = source_id
            segment["edge"] = edge
            segment["wall_type"] = "full_height"
            segment["full_height"] = True
            segment["height"] = DEFAULT_FULL_HEIGHT_WALL
            wall_segments.append(segment)
    return wall_segments


def generate_spa_layout(
    shell: Dict[str, float],
    entry_edge: str,
    lounge_input: Dict[str, Any],
    rooms_input: Dict[str, Any],
    room_specs: Dict[str, Dict[str, Any]],
    equipment: Dict[str, Dict[str, Any]],
    include_debug: bool = True,
) -> Dict[str, Any]:
    shell_rect = Rect(0.0, 0.0, float(shell["w"]), float(shell["d"]))
    warnings: List[str] = []

    lounge_rect = Rect(
        x=max(0.0, (shell_rect.w - float(lounge_input["w"])) / 2.0),
        y=max(0.0, (shell_rect.d - float(lounge_input["d"])) / 2.0),
        w=min(shell_rect.w, float(lounge_input["w"])),
        d=min(shell_rect.d, float(lounge_input["d"])),
    )
    lounge_room = {
        "id": "lounge",
        "room_type": "lounge",
        "classification": room_specs["lounge"].get("classification"),
        "variant": None,
        "machine_count": 0,
        "door_width": float(lounge_input["entry_door_width"]),
        "requires_tv": False,
        "attached_to": None,
        "attached_edge": None,
        "rect": lounge_rect.to_dict(),
        "description": room_specs["lounge"].get("description"),
    }

    requests: List[Dict[str, Any]] = []
    request_sizes: Dict[str, Dict[str, float]] = {}
    for room_type, room_data in rooms_input.items():
        room_spec = room_specs[room_type]
        for index, instance in enumerate(room_data.get("instances", []), start=1):
            variant = instance["variant"]
            equipment_spec = equipment.get(variant, {})
            room_id = f"{room_type}-{index}"
            size = _estimate_room_size(room_spec, equipment_spec, instance["machine_count"], float(instance["door_width"]))
            room_request = {
                "id": room_id,
                "room_type": room_type,
                "classification": room_spec.get("classification"),
                "variant": variant,
                "machine_count": instance["machine_count"],
                "door_width": float(instance["door_width"]),
                "requires_tv": bool(room_spec.get("tv_required")),
                "attached_to": "lounge",
                "description": room_spec.get("description"),
            }
            requests.append(room_request)
            request_sizes[room_id] = size

    requests.sort(
        key=lambda item: (
            -(request_sizes[item["id"]]["span"] * request_sizes[item["id"]]["depth"]),
            -item["machine_count"],
            item["room_type"],
            item["id"],
        )
    )

    edge_capacity = {
        "north": {"remaining": lounge_rect.w, "offset": 0.0, "max_depth": max(0.0, shell_rect.d - lounge_rect.y2)},
        "south": {"remaining": lounge_rect.w, "offset": 0.0, "max_depth": max(0.0, lounge_rect.y)},
        "east": {"remaining": lounge_rect.d, "offset": 0.0, "max_depth": max(0.0, shell_rect.w - lounge_rect.x2)},
        "west": {"remaining": lounge_rect.d, "offset": 0.0, "max_depth": max(0.0, lounge_rect.x)},
    }

    available_edges = [edge for edge in EDGE_ORDER if edge != entry_edge]
    placed_rooms: List[Dict[str, Any]] = [lounge_room]
    placements: List[Dict[str, Any]] = []
    doors: List[Dict[str, Any]] = []
    lounge_openings: List[Dict[str, float]] = []
    room_openings_by_id: Dict[str, List[Dict[str, float]]] = {}
    interior_walls_by_id: Dict[str, List[Dict[str, Any]]] = {}
    unplaced_rooms: List[Dict[str, Any]] = []

    for request in requests:
        size = request_sizes[request["id"]]
        candidate_edges = [
            edge
            for edge in available_edges
            if edge_capacity[edge]["remaining"] >= size["span"] and edge_capacity[edge]["max_depth"] >= size["depth"]
        ]
        candidate_edges.sort(key=lambda edge: (-edge_capacity[edge]["remaining"], edge))

        if not candidate_edges:
            unplaced_rooms.append(
                {
                    "id": request["id"],
                    "room_type": request["room_type"],
                    "variant": request["variant"],
                    "reason": "no_edge_fit",
                    "required_span": size["span"],
                    "required_depth": size["depth"],
                }
            )
            warnings.append(f"Unable to place {request['id']}: no remaining lounge edge can fit the room.")
            continue

        attached_edge = candidate_edges[0]
        edge_state = edge_capacity[attached_edge]

        if attached_edge == "north":
            room_rect = Rect(lounge_rect.x + edge_state["offset"], lounge_rect.y2, size["span"], size["depth"])
        elif attached_edge == "south":
            room_rect = Rect(lounge_rect.x + edge_state["offset"], lounge_rect.y - size["depth"], size["span"], size["depth"])
        elif attached_edge == "east":
            room_rect = Rect(lounge_rect.x2, lounge_rect.y + edge_state["offset"], size["depth"], size["span"])
        else:
            room_rect = Rect(lounge_rect.x - size["depth"], lounge_rect.y + edge_state["offset"], size["depth"], size["span"])

        edge_state["offset"] += size["span"]
        edge_state["remaining"] = max(0.0, edge_state["remaining"] - size["span"])

        room_output = dict(request)
        room_output["attached_edge"] = attached_edge
        room_output["rect"] = room_rect.to_dict()
        room_output["layout_pattern"] = size.get("layout_pattern", "linear")
        placed_rooms.append(room_output)

        room_open_edge = _opposite_edge(attached_edge)
        room_open_offset = _opening_offset(room_rect, room_open_edge, request["door_width"])
        room_opening = {"edge": room_open_edge, "offset": room_open_offset, "width": request["door_width"]}
        room_openings_by_id[request["id"]] = [room_opening]

        if attached_edge in {"north", "south"}:
            lounge_offset = room_rect.x - lounge_rect.x + room_open_offset
        else:
            lounge_offset = room_rect.y - lounge_rect.y + room_open_offset
        lounge_openings.append({"edge": attached_edge, "offset": lounge_offset, "width": request["door_width"]})

        door_segment = _edge_opening_to_segment(room_rect, room_open_edge, room_open_offset, request["door_width"])
        doors.append(
            {
                "id": f"{request['id']}-door",
                "room_id": request["id"],
                "attached_to": "lounge",
                "edge": room_open_edge,
                "width": request["door_width"],
                **door_segment,
            }
        )

        if size.get("layout_pattern") == "two_wing":
            _, local_partitions = _hydromassage_local_rects(size)
            room_open_edge = _opposite_edge(attached_edge)
            interior_walls_by_id[request["id"]] = [
                {
                    **_transform_local_segment(segment, room_rect, open_edge=room_open_edge),
                    "source_id": request["id"],
                }
                for segment in local_partitions
            ]

        placements.extend(
            _build_machine_placements(
                request,
                room_rect,
                attached_edge=attached_edge,
                equipment_spec=equipment.get(request["variant"], {}),
                size=size,
            )
        )

    entry_offset = _opening_offset(lounge_rect, entry_edge, float(lounge_input["entry_door_width"]))
    lounge_openings.append({"edge": entry_edge, "offset": entry_offset, "width": float(lounge_input["entry_door_width"])})
    entry_segment = _edge_opening_to_segment(lounge_rect, entry_edge, entry_offset, float(lounge_input["entry_door_width"]))
    doors.append(
        {
            "id": "lounge-entry-door",
            "room_id": "lounge",
            "attached_to": "entry",
            "edge": entry_edge,
            "width": float(lounge_input["entry_door_width"]),
            **entry_segment,
        }
    )

    walls: List[Dict[str, Any]] = []
    walls.extend(_rect_wall_segments(shell_rect, source="shell", source_id="shell", openings=[]))
    walls.extend(_rect_wall_segments(lounge_rect, source="room", source_id="lounge", openings=lounge_openings))
    for room in placed_rooms[1:]:
        room_rect = Rect(**room["rect"])
        walls.extend(
            _rect_wall_segments(
                room_rect,
                source="room",
                source_id=room["id"],
                openings=room_openings_by_id.get(room["id"], []),
            )
        )
        walls.extend(interior_walls_by_id.get(room["id"], []))

    result: Dict[str, Any] = {
        "shell": shell_rect.to_dict(),
        "entry_edge": entry_edge,
        "lounge": lounge_room,
        "rooms": placed_rooms,
        "doors": doors,
        "walls": walls,
        "placements": placements,
        "unplaced_rooms": unplaced_rooms,
        "warnings": warnings,
    }

    if include_debug:
        placed_counts: Dict[str, int] = {}
        for room in placed_rooms[1:]:
            placed_counts[room["room_type"]] = placed_counts.get(room["room_type"], 0) + 1

        requested_counts = {room_type: room_data["count"] for room_type, room_data in rooms_input.items()}
        debug_rooms = []
        for room_type, requested_count in requested_counts.items():
            debug_rooms.append(
                {
                    "room_type": room_type,
                    "requested": requested_count,
                    "placed": placed_counts.get(room_type, 0),
                    "unplaced": max(0, requested_count - placed_counts.get(room_type, 0)),
                }
            )

        result["debug"] = {
            "summary": {
                "requested_room_total": sum(requested_counts.values()),
                "placed_room_total": len(placed_rooms) - 1,
                "unplaced_room_total": len(unplaced_rooms),
                "placed_machine_total": len(placements),
                "warning_total": len(warnings),
            },
            "edge_capacity": edge_capacity,
            "requested_by_type": debug_rooms,
        }

    return result
