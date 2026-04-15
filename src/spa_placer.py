from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple


EDGE_ORDER = ("north", "east", "south", "west")
ROOM_MACHINE_GAP = 18.0
MIN_SUBROOM_DOOR_WIDTH = 24.0
DEFAULT_SHELL = {"w": 1100.0, "d": 800.0}
DEFAULT_FULL_HEIGHT_WALL = 120.0
DEFAULT_PARTIAL_HEIGHT_WALL = 50.0
DEFAULT_WALL_THICKNESS = 4.875
DEFAULT_HALLWAY_WIDTH = 60.0
DEFAULT_HALLWAY_LENGTH = 0.0
DEFAULT_HALLWAY_POSITION = 0.0


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

    def intersects(self, other: "Rect") -> bool:
        return not (self.x2 <= other.x or other.x2 <= self.x or self.y2 <= other.y or other.y2 <= self.y)

    def within_rect(self, other: "Rect") -> bool:
        return self.x >= other.x and self.y >= other.y and self.x2 <= other.x2 and self.y2 <= other.y2


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


def _edge_length(rect: Rect, edge: str) -> float:
    return rect.w if edge in {"north", "south"} else rect.d


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
    global_rules = spa_spec.get("black_card_spa", {}).get("global_rules", {})
    hallway_defaults = global_rules.get("hallway_defaults") or {}
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
        "wall_thickness": _float_or_default(global_rules.get("wall_thickness"), DEFAULT_WALL_THICKNESS, minimum=0.0),
        "lounge": {
            "auto_size": True,
            "w": _float_or_default(lounge_size.get("w"), 216.0, minimum=96.0),
            "d": _float_or_default(lounge_size.get("d"), 168.0, minimum=96.0),
        },
        "hallway": {
            "enabled": _float_or_default(hallway_defaults.get("length"), DEFAULT_HALLWAY_LENGTH, minimum=0.0) > 0.0,
            "position": _float_or_default(hallway_defaults.get("position"), DEFAULT_HALLWAY_POSITION, minimum=0.0),
            "length": _float_or_default(hallway_defaults.get("length"), DEFAULT_HALLWAY_LENGTH, minimum=0.0),
            "width": _float_or_default(hallway_defaults.get("width"), DEFAULT_HALLWAY_WIDTH, minimum=1.0),
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

    hallway_defaults = defaults["hallway"]
    hallway_raw = payload.get("hallway") if isinstance(payload, dict) else {}
    hallway_length = _float_or_default((hallway_raw or {}).get("length"), hallway_defaults["length"], minimum=0.0)
    hallway_width = _float_or_default((hallway_raw or {}).get("width"), hallway_defaults["width"], minimum=1.0)
    hallway_enabled = _bool_or_default((hallway_raw or {}).get("enabled"), hallway_defaults["enabled"]) and hallway_length > 0.0
    hallway = {
        "enabled": hallway_enabled,
        "position": _clamp(_float_or_default((hallway_raw or {}).get("position"), hallway_defaults["position"], minimum=0.0), 0.0, 1.0),
        "length": hallway_length,
        "width": hallway_width,
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
        minimum_machine_count = _int_or_default(spec.get("minimum_machine_count_per_room"), default_machine_count, minimum=0)

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
        "wall_thickness": _float_or_default(payload.get("wall_thickness") if isinstance(payload, dict) else None, defaults["wall_thickness"], minimum=0.0),
        "lounge": lounge,
        "hallway": hallway,
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
        divider_x_positions: List[float] = []

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
        transformed = {"x1": room_rect.x + x1, "y1": room_rect.y + y1, "x2": room_rect.x + x2, "y2": room_rect.y + y2}
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
    cad_scale_raw = equipment_spec.get("cad_scale") or {}
    cad_offset_raw = equipment_spec.get("cad_offset") or {}
    cad_scale = {
        "x": _float_or_default(cad_scale_raw.get("x"), 1.0, minimum=0.0001),
        "y": _float_or_default(cad_scale_raw.get("y"), 1.0, minimum=0.0001),
        "z": _float_or_default(cad_scale_raw.get("z"), 1.0, minimum=0.0001),
    }
    cad_offset = {
        "x": _float_or_default(cad_offset_raw.get("x"), 0.0),
        "y": _float_or_default(cad_offset_raw.get("y"), 0.0),
    }
    cad_alignment_mode = equipment_spec.get("cad_alignment_mode") if isinstance(equipment_spec.get("cad_alignment_mode"), str) else "bbox_center"
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
                    "scale": dict(cad_scale),
                    "insertion_point": {"x": machine_rect.x + (machine_rect.w / 2.0), "y": machine_rect.y + (machine_rect.d / 2.0), "z": 0},
                    "insertion_anchor": "center",
                    "alignment_mode": cad_alignment_mode,
                    "cad_offset": dict(cad_offset),
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
                    "scale": dict(cad_scale),
                    "insertion_point": {"x": machine_rect.x + (machine_rect.w / 2.0), "y": machine_rect.y + (machine_rect.d / 2.0), "z": 0},
                    "insertion_anchor": "center",
                    "alignment_mode": cad_alignment_mode,
                    "cad_offset": dict(cad_offset),
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
                    "scale": dict(cad_scale),
                    "insertion_point": {"x": machine_rect.x + (machine_rect.w / 2.0), "y": machine_rect.y + (machine_rect.d / 2.0), "z": 0},
                    "insertion_anchor": "center",
                    "alignment_mode": cad_alignment_mode,
                    "cad_offset": dict(cad_offset),
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


def _rect_wall_segments(
    rect: Rect,
    source: str,
    source_id: str,
    openings: Iterable[Dict[str, float]],
    wall_thickness: float,
) -> List[Dict[str, Any]]:
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
        length = _edge_length(rect, edge)
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
            segment["thickness"] = wall_thickness
            wall_segments.append(segment)
    return wall_segments


def _split_segments(segments: List[Tuple[float, float]], start: float, end: float) -> List[Tuple[float, float]]:
    next_segments: List[Tuple[float, float]] = []
    for seg_start, seg_end in segments:
        if end <= seg_start or start >= seg_end:
            next_segments.append((seg_start, seg_end))
            continue
        if start > seg_start:
            next_segments.append((seg_start, start))
        if end < seg_end:
            next_segments.append((end, seg_end))
    return next_segments


def _max_segment_length(segments: List[Tuple[float, float]]) -> float:
    if not segments:
        return 0.0
    return max(max(0.0, end - start) for start, end in segments)


def _local_start_from_directional(edge_length: float, span: float, offset: float, direction: int) -> float:
    if direction >= 0:
        return offset
    return edge_length - span - offset


def _room_rect_from_host(host_rect: Rect, edge: str, local_start: float, span: float, depth: float) -> Rect:
    if edge == "north":
        return Rect(host_rect.x + local_start, host_rect.y2, span, depth)
    if edge == "south":
        return Rect(host_rect.x + local_start, host_rect.y - depth, span, depth)
    if edge == "east":
        return Rect(host_rect.x2, host_rect.y + local_start, depth, span)
    return Rect(host_rect.x - depth, host_rect.y + local_start, depth, span)


def _host_opening(edge: str, local_start: float, span: float, width: float) -> Dict[str, float]:
    return {"edge": edge, "offset": local_start + max(0.0, (span - width) / 2.0), "width": width}


def _hallway_traversal_specs(entry_edge: str) -> List[Tuple[str, int]]:
    return {
        "south": [("west", 1), ("north", 1), ("east", -1)],
        "north": [("east", -1), ("south", -1), ("west", 1)],
        "east": [("north", -1), ("west", -1), ("south", 1)],
        "west": [("south", 1), ("east", 1), ("north", -1)],
    }[_sanitize_edge(entry_edge)]


def _hallway_side_mapping(hallway_edge: str) -> List[Tuple[str, str]]:
    return {
        "north": [("hallway_side_left", "west"), ("hallway_side_right", "east")],
        "south": [("hallway_side_left", "east"), ("hallway_side_right", "west")],
        "east": [("hallway_side_left", "north"), ("hallway_side_right", "south")],
        "west": [("hallway_side_left", "south"), ("hallway_side_right", "north")],
    }[hallway_edge]


def _hallway_side_direction(hallway_edge: str) -> int:
    return 1 if hallway_edge in {"north", "east"} else -1


def _max_depth_from_edge(host_rect: Rect, shell_rect: Rect, edge: str) -> float:
    if edge == "north":
        return max(0.0, shell_rect.y2 - host_rect.y2)
    if edge == "south":
        return max(0.0, host_rect.y - shell_rect.y)
    if edge == "east":
        return max(0.0, shell_rect.x2 - host_rect.x2)
    return max(0.0, host_rect.x - shell_rect.x)


def _hallway_end_rect(hallway_rect: Rect, hallway_edge: str, hallway_width: float) -> Rect:
    if hallway_edge == "north":
        return Rect(hallway_rect.x, hallway_rect.y2 - hallway_width, hallway_width, hallway_width)
    if hallway_edge == "south":
        return Rect(hallway_rect.x, hallway_rect.y, hallway_width, hallway_width)
    if hallway_edge == "east":
        return Rect(hallway_rect.x2 - hallway_width, hallway_rect.y, hallway_width, hallway_width)
    return Rect(hallway_rect.x, hallway_rect.y, hallway_width, hallway_width)


def _build_hallway(
    lounge_rect: Rect,
    shell_rect: Rect,
    entry_edge: str,
    hallway_input: Dict[str, Any],
    warnings: List[str],
) -> Dict[str, Any]:
    requested_length = _float_or_default(hallway_input.get("length"), DEFAULT_HALLWAY_LENGTH, minimum=0.0)
    hallway_width = _float_or_default(hallway_input.get("width"), DEFAULT_HALLWAY_WIDTH, minimum=1.0)
    hallway_enabled = _bool_or_default(hallway_input.get("enabled"), requested_length > 0.0) and requested_length > 0.0
    hallway_position = _clamp(_float_or_default(hallway_input.get("position"), DEFAULT_HALLWAY_POSITION, minimum=0.0), 0.0, 1.0)

    hallway_output: Dict[str, Any] = {
        "enabled": False,
        "position": hallway_position,
        "length": 0.0,
        "requested_length": requested_length,
        "width": hallway_width,
        "edge": None,
        "rect": None,
        "opening": None,
        "end_rect": None,
    }
    if not hallway_enabled:
        return hallway_output

    traversal_specs = _hallway_traversal_specs(entry_edge)
    usable_runs: List[Tuple[str, int, float, float]] = []
    total_usable = 0.0
    for edge, direction in traversal_specs:
        edge_length = _edge_length(lounge_rect, edge)
        usable_length = max(0.0, edge_length - hallway_width)
        usable_runs.append((edge, direction, edge_length, usable_length))
        total_usable += usable_length

    if total_usable <= 0.0:
        warnings.append("Unable to place hallway: no non-entry lounge edge can fit the hallway width.")
        return hallway_output

    target = hallway_position * total_usable
    selected_edge = usable_runs[-1][0]
    selected_direction = usable_runs[-1][1]
    selected_edge_length = usable_runs[-1][2]
    selected_start = usable_runs[-1][3]
    remaining = target
    for index, (edge, direction, edge_length, usable_length) in enumerate(usable_runs):
        if remaining <= usable_length or index == len(usable_runs) - 1:
            selected_edge = edge
            selected_direction = direction
            selected_edge_length = edge_length
            selected_start = min(usable_length, remaining)
            break
        remaining -= usable_length

    hallway_start = _local_start_from_directional(selected_edge_length, hallway_width, selected_start, selected_direction)
    max_length = _max_depth_from_edge(lounge_rect, shell_rect, selected_edge)
    actual_length = min(requested_length, max_length)
    if actual_length <= 0.0:
        warnings.append("Unable to place hallway: there is no shell depth available beyond the selected lounge edge.")
        return hallway_output
    if actual_length < requested_length:
        warnings.append(f"Hallway length truncated from {requested_length:.1f}\" to {actual_length:.1f}\" to stay within the shell.")

    if selected_edge == "north":
        hallway_rect = Rect(lounge_rect.x + hallway_start, lounge_rect.y2, hallway_width, actual_length)
    elif selected_edge == "south":
        hallway_rect = Rect(lounge_rect.x + hallway_start, lounge_rect.y - actual_length, hallway_width, actual_length)
    elif selected_edge == "east":
        hallway_rect = Rect(lounge_rect.x2, lounge_rect.y + hallway_start, actual_length, hallway_width)
    else:
        hallway_rect = Rect(lounge_rect.x - actual_length, lounge_rect.y + hallway_start, actual_length, hallway_width)

    opening_segment = _edge_opening_to_segment(lounge_rect, selected_edge, hallway_start, hallway_width)
    hallway_output.update(
        {
            "enabled": True,
            "length": actual_length,
            "edge": selected_edge,
            "rect": hallway_rect.to_dict(),
            "opening": {
                "edge": selected_edge,
                "offset": hallway_start,
                "width": hallway_width,
                **opening_segment,
            },
            "end_rect": _hallway_end_rect(hallway_rect, selected_edge, hallway_width).to_dict(),
        }
    )
    return hallway_output


def _place_room_on_linear_host(
    request: Dict[str, Any],
    size: Dict[str, float],
    host: Dict[str, Any],
    occupied: List[Rect],
    shell_rect: Rect,
) -> Tuple[Rect, float] | None:
    span = float(size["span"])
    depth = float(size["depth"])
    edge_length = _edge_length(host["rect"], host["edge"])

    for index, (seg_start, seg_end) in enumerate(host["segments"]):
        if seg_end - seg_start < span:
            continue
        local_start = _local_start_from_directional(edge_length, span, seg_start, host["direction"])
        room_rect = _room_rect_from_host(host["rect"], host["edge"], local_start, span, depth)
        if not room_rect.within_rect(shell_rect):
            continue
        if any(room_rect.intersects(rect) for rect in occupied):
            continue
        host["segments"][index] = (seg_start + span, seg_end)
        host["segments"] = [segment for segment in host["segments"] if segment[1] - segment[0] > 1e-6]
        return room_rect, local_start
    return None


def _place_room_on_cap_host(
    size: Dict[str, float],
    host: Dict[str, Any],
    occupied: List[Rect],
    shell_rect: Rect,
) -> Rect | None:
    if host.get("used"):
        return None

    span = float(size["span"])
    depth = float(size["depth"])
    host_rect = host["rect"]
    edge = host["edge"]

    if edge == "north":
        room_rect = Rect(host_rect.x + (host_rect.w - span) / 2.0, host_rect.y2, span, depth)
    elif edge == "south":
        room_rect = Rect(host_rect.x + (host_rect.w - span) / 2.0, host_rect.y - depth, span, depth)
    elif edge == "east":
        room_rect = Rect(host_rect.x2, host_rect.y + (host_rect.d - span) / 2.0, depth, span)
    else:
        room_rect = Rect(host_rect.x - depth, host_rect.y + (host_rect.d - span) / 2.0, depth, span)

    if not room_rect.within_rect(shell_rect):
        return None
    if any(room_rect.intersects(rect) for rect in occupied):
        return None
    host["used"] = True
    return room_rect


def _room_output(
    request: Dict[str, Any],
    room_rect: Rect,
    attached_edge: str,
    attached_to: str,
    attachment_slot: str | None,
    size: Dict[str, float],
) -> Dict[str, Any]:
    room_output = dict(request)
    room_output["attached_to"] = attached_to
    room_output["attachment_slot"] = attachment_slot
    room_output["attached_edge"] = attached_edge
    room_output["rect"] = room_rect.to_dict()
    room_output["layout_pattern"] = size.get("layout_pattern", "linear")
    return room_output


def _room_door_output(room_id: str, room_rect: Rect, attached_edge: str, width: float) -> Tuple[Dict[str, Any], Dict[str, float]]:
    room_open_edge = _opposite_edge(attached_edge)
    room_open_offset = _opening_offset(room_rect, room_open_edge, width)
    door_segment = _edge_opening_to_segment(room_rect, room_open_edge, room_open_offset, width)
    return (
        {
            "id": f"{room_id}-door",
            "room_id": room_id,
            "attached_to": "interior",
            "edge": room_open_edge,
            "width": width,
            **door_segment,
        },
        {"edge": room_open_edge, "offset": room_open_offset, "width": width},
    )


def generate_spa_layout(
    shell: Dict[str, float],
    entry_edge: str,
    lounge_input: Dict[str, Any],
    hallway_input: Dict[str, Any],
    rooms_input: Dict[str, Any],
    room_specs: Dict[str, Dict[str, Any]],
    equipment: Dict[str, Dict[str, Any]],
    wall_thickness: float = DEFAULT_WALL_THICKNESS,
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
        "attachment_slot": None,
        "attached_edge": None,
        "rect": lounge_rect.to_dict(),
        "description": room_specs["lounge"].get("description"),
    }

    hallway = _build_hallway(lounge_rect, shell_rect, entry_edge, hallway_input, warnings)
    hallway_rect = Rect(**hallway["rect"]) if hallway.get("rect") else None

    requests: List[Dict[str, Any]] = []
    request_sizes: Dict[str, Dict[str, float]] = {}
    for room_type, room_data in rooms_input.items():
        room_spec = room_specs[room_type]
        for index, instance in enumerate(room_data.get("instances", []), start=1):
            variant = instance["variant"]
            equipment_spec = equipment.get(variant, {})
            room_id = f"{room_type}-{index}"
            size = _estimate_room_size(room_spec, equipment_spec, instance["machine_count"], float(instance["door_width"]))
            requests.append(
                {
                    "id": room_id,
                    "room_type": room_type,
                    "classification": room_spec.get("classification"),
                    "variant": variant,
                    "machine_count": instance["machine_count"],
                    "door_width": float(instance["door_width"]),
                    "requires_tv": bool(room_spec.get("tv_required")),
                    "description": room_spec.get("description"),
                }
            )
            request_sizes[room_id] = size

    requests.sort(
        key=lambda item: (
            -(request_sizes[item["id"]]["span"] * request_sizes[item["id"]]["depth"]),
            -item["machine_count"],
            item["room_type"],
            item["id"],
        )
    )

    lounge_hosts: List[Dict[str, Any]] = []
    hallway_hosts: List[Dict[str, Any]] = []
    hallway_end_host: Dict[str, Any] | None = None
    lounge_openings: List[Dict[str, float]] = []
    hallway_openings: List[Dict[str, float]] = []
    room_openings_by_id: Dict[str, List[Dict[str, float]]] = {}
    interior_walls_by_id: Dict[str, List[Dict[str, Any]]] = {}

    hallway_edge = hallway.get("edge")
    hallway_opening = hallway.get("opening") or {}
    for edge in EDGE_ORDER:
        if edge == entry_edge:
            continue
        segments = [(0.0, _edge_length(lounge_rect, edge))]
        if hallway.get("enabled") and edge == hallway_edge:
            open_start = _float_or_default(hallway_opening.get("offset"), 0.0, minimum=0.0)
            open_end = open_start + _float_or_default(hallway_opening.get("width"), 0.0, minimum=0.0)
            segments = _split_segments(segments, open_start, open_end)
        lounge_hosts.append(
            {
                "host_id": "lounge",
                "rect": lounge_rect,
                "edge": edge,
                "direction": 1,
                "segments": segments,
                "attached_to": "lounge",
                "attachment_slot": None,
            }
        )

    if hallway.get("enabled") and hallway_rect is not None:
        hallway_openings.append({"edge": _opposite_edge(hallway_edge), "offset": 0.0, "width": hallway["width"]})
        direction = _hallway_side_direction(hallway_edge)
        side_length = float(hallway["length"])
        for slot_name, side_edge in _hallway_side_mapping(hallway_edge):
            hallway_hosts.append(
                {
                    "host_id": "hallway",
                    "rect": hallway_rect,
                    "edge": side_edge,
                    "direction": direction,
                    "segments": [(0.0, side_length)],
                    "attached_to": "hallway_side",
                    "attachment_slot": slot_name,
                }
            )
        hallway_end_host = {
            "host_id": "hallway",
            "rect": hallway_rect,
            "edge": hallway_edge,
            "attached_to": "hallway_end",
            "attachment_slot": "hallway_end",
            "used": False,
        }

    occupied: List[Rect] = [lounge_rect]
    if hallway_rect is not None:
        occupied.append(hallway_rect)

    placed_rooms: List[Dict[str, Any]] = [lounge_room]
    doors: List[Dict[str, Any]] = []
    placements: List[Dict[str, Any]] = []
    unplaced_rooms: List[Dict[str, Any]] = []

    hydromassage_request = next((request for request in requests if request["room_type"] == "hydromassage_room"), None)
    pending_requests = [request for request in requests if request["id"] != (hydromassage_request or {}).get("id")]
    lounge_queue: List[Dict[str, Any]] = []

    hallway_first_types = {
        "massage_chair_room",
        "tanning_room",
        "hybrid_room",
        "total_body_enhancement_room",
        "wellness_pod_room",
        "cryolounge_room",
    }

    def try_linear_hosts(request: Dict[str, Any], hosts: List[Dict[str, Any]]) -> bool:
        size = request_sizes[request["id"]]
        ordered_hosts = sorted(hosts, key=lambda host: (-_max_segment_length(host["segments"]), host["edge"], host["attachment_slot"] or ""))
        for host in ordered_hosts:
            if size["depth"] > _max_depth_from_edge(host["rect"], shell_rect, host["edge"]):
                continue
            placement = _place_room_on_linear_host(request, size, host, occupied, shell_rect)
            if placement is None:
                continue
            room_rect, local_start = placement
            room_output = _room_output(request, room_rect, host["edge"], host["attached_to"], host["attachment_slot"], size)
            placed_rooms.append(room_output)
            occupied.append(room_rect)

            door_output, room_opening = _room_door_output(request["id"], room_rect, host["edge"], request["door_width"])
            door_output["attached_to"] = host["attached_to"]
            door_output["attachment_slot"] = host["attachment_slot"]
            doors.append(door_output)
            room_openings_by_id[request["id"]] = [room_opening]

            host_opening = _host_opening(host["edge"], local_start, size["span"], request["door_width"])
            if host["host_id"] == "lounge":
                lounge_openings.append(host_opening)
            else:
                hallway_openings.append(host_opening)

            if size.get("layout_pattern") == "two_wing":
                _, local_partitions = _hydromassage_local_rects(size)
                room_open_edge = _opposite_edge(host["edge"])
                interior_walls_by_id[request["id"]] = [
                    {
                        **_transform_local_segment(segment, room_rect, open_edge=room_open_edge),
                        "source_id": request["id"],
                        "thickness": wall_thickness,
                    }
                    for segment in local_partitions
                ]

            placements.extend(
                _build_machine_placements(
                    request,
                    room_rect,
                    attached_edge=host["edge"],
                    equipment_spec=equipment.get(request["variant"], {}),
                    size=size,
                )
            )
            return True
        return False

    def try_hallway_end(request: Dict[str, Any]) -> bool:
        if hallway_end_host is None or hallway_rect is None:
            return False
        size = request_sizes[request["id"]]
        if request["door_width"] > hallway["width"]:
            return False
        if size["depth"] > _max_depth_from_edge(hallway_rect, shell_rect, hallway_end_host["edge"]):
            return False
        room_rect = _place_room_on_cap_host(size, hallway_end_host, occupied, shell_rect)
        if room_rect is None:
            return False

        room_output = _room_output(request, room_rect, hallway_end_host["edge"], "hallway_end", "hallway_end", size)
        placed_rooms.append(room_output)
        occupied.append(room_rect)

        door_output, room_opening = _room_door_output(request["id"], room_rect, hallway_end_host["edge"], request["door_width"])
        door_output["attached_to"] = "hallway_end"
        door_output["attachment_slot"] = "hallway_end"
        doors.append(door_output)
        room_openings_by_id[request["id"]] = [room_opening]
        hallway_openings.append({"edge": hallway_end_host["edge"], "offset": _opening_offset(hallway_rect, hallway_end_host["edge"], request["door_width"]), "width": request["door_width"]})

        if size.get("layout_pattern") == "two_wing":
            _, local_partitions = _hydromassage_local_rects(size)
            room_open_edge = _opposite_edge(hallway_end_host["edge"])
            interior_walls_by_id[request["id"]] = [
                {
                    **_transform_local_segment(segment, room_rect, open_edge=room_open_edge),
                    "source_id": request["id"],
                    "thickness": wall_thickness,
                }
                for segment in local_partitions
            ]

        placements.extend(
            _build_machine_placements(
                request,
                room_rect,
                attached_edge=hallway_end_host["edge"],
                equipment_spec=equipment.get(request["variant"], {}),
                size=size,
            )
        )
        return True

    if hydromassage_request is not None:
        hallway_hydromassage_placed = hallway.get("enabled") and try_hallway_end(hydromassage_request)
        if hallway.get("enabled") and not hallway_hydromassage_placed:
            warnings.append("Hydromassage could not fit at the hallway end and was returned to direct lounge placement.")
        if not hallway_hydromassage_placed:
            lounge_queue.append(hydromassage_request)

    for request in pending_requests:
        placed = False
        if hallway.get("enabled") and request["room_type"] in hallway_first_types:
            placed = try_linear_hosts(request, hallway_hosts)
            if not placed:
                placed = try_hallway_end(request)
        if placed:
            continue
        lounge_queue.append(request)

    for request in lounge_queue:
        if try_linear_hosts(request, lounge_hosts):
            continue
        unplaced_rooms.append(
            {
                "id": request["id"],
                "room_type": request["room_type"],
                "variant": request["variant"],
                "reason": "no_fit_after_hallway_and_lounge",
                "required_span": request_sizes[request["id"]]["span"],
                "required_depth": request_sizes[request["id"]]["depth"],
            }
        )
        warnings.append(f"Unable to place {request['id']}: no hallway or lounge attachment position can fit the room.")

    entry_offset = _opening_offset(lounge_rect, entry_edge, float(lounge_input["entry_door_width"]))
    lounge_openings.append({"edge": entry_edge, "offset": entry_offset, "width": float(lounge_input["entry_door_width"])})
    entry_segment = _edge_opening_to_segment(lounge_rect, entry_edge, entry_offset, float(lounge_input["entry_door_width"]))
    doors.append(
        {
            "id": "lounge-entry-door",
            "room_id": "lounge",
            "attached_to": "entry",
            "attachment_slot": "entry",
            "edge": entry_edge,
            "width": float(lounge_input["entry_door_width"]),
            **entry_segment,
        }
    )

    walls: List[Dict[str, Any]] = []
    walls.extend(_rect_wall_segments(lounge_rect, source="room", source_id="lounge", openings=lounge_openings, wall_thickness=wall_thickness))
    if hallway_rect is not None:
        walls.extend(_rect_wall_segments(hallway_rect, source="hallway", source_id="hallway", openings=hallway_openings, wall_thickness=wall_thickness))
    for room in placed_rooms[1:]:
        room_rect = Rect(**room["rect"])
        walls.extend(
            _rect_wall_segments(
                room_rect,
                source="room",
                source_id=room["id"],
                openings=room_openings_by_id.get(room["id"], []),
                wall_thickness=wall_thickness,
            )
        )
        walls.extend(interior_walls_by_id.get(room["id"], []))

    result: Dict[str, Any] = {
        "shell": shell_rect.to_dict(),
        "entry_edge": entry_edge,
        "wall_thickness": wall_thickness,
        "hallway": hallway,
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
                "hallway_enabled": bool(hallway.get("enabled")),
            },
            "hallway": hallway,
            "requested_by_type": debug_rooms,
            "lounge_hosts": [
                {"edge": host["edge"], "segments": host["segments"], "remaining": _max_segment_length(host["segments"])}
                for host in lounge_hosts
            ],
            "hallway_hosts": [
                {
                    "edge": host["edge"],
                    "attachment_slot": host["attachment_slot"],
                    "segments": host["segments"],
                    "remaining": _max_segment_length(host["segments"]),
                }
                for host in hallway_hosts
            ],
        }

    return result
