import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from spa_placer import build_room_spec_index, build_spa_defaults, generate_spa_layout, sanitize_spa_request


def load_spa_inputs():
    spec = json.loads((ROOT / "data" / "bcs_spec.json").read_text())
    equipment = json.loads((ROOT / "src" / "spa_equipment.json").read_text())
    room_specs = build_room_spec_index(spec)
    defaults = build_spa_defaults(spec)
    sanitized = sanitize_spa_request(defaults, spec)
    return spec, equipment, room_specs, defaults, sanitized


class SpaLayoutTests(unittest.TestCase):
    def test_spec_loads_with_expected_default_counts(self):
        spec, _, room_specs, defaults, _ = load_spa_inputs()
        self.assertIn("black_card_spa", spec)
        self.assertEqual(defaults["rooms"]["hydromassage_room"]["count"], 1)
        self.assertEqual(defaults["rooms"]["hydromassage_room"]["instances"][0]["machine_count"], 4)
        self.assertEqual(defaults["rooms"]["massage_chair_room"]["count"], 1)
        self.assertEqual(defaults["rooms"]["tanning_room"]["count"], 2)
        self.assertEqual(defaults["rooms"]["hybrid_room"]["count"], 1)
        self.assertEqual(defaults["rooms"]["wellness_pod_room"]["count"], 0)
        self.assertEqual(room_specs["lounge"]["default_room_count"], 1)
        self.assertTrue(room_specs["hydromassage_room"]["fixed_room_count"])

    def test_default_layout_keeps_entry_edge_clear(self):
        _, equipment, room_specs, _, sanitized = load_spa_inputs()
        result = generate_spa_layout(
            shell=sanitized["shell"],
            entry_edge=sanitized["entry_edge"],
            lounge_input=sanitized["lounge"],
            rooms_input=sanitized["rooms"],
            room_specs=room_specs,
            equipment=equipment,
            include_debug=True,
        )
        attached_edges = {room["attached_edge"] for room in result["rooms"] if room["room_type"] != "lounge"}
        self.assertNotIn(sanitized["entry_edge"], attached_edges)
        self.assertEqual(result["lounge"]["room_type"], "lounge")

    def test_machine_counts_and_tv_flags_follow_room_rules(self):
        _, equipment, room_specs, _, sanitized = load_spa_inputs()
        result = generate_spa_layout(
            shell=sanitized["shell"],
            entry_edge=sanitized["entry_edge"],
            lounge_input=sanitized["lounge"],
            rooms_input=sanitized["rooms"],
            room_specs=room_specs,
            equipment=equipment,
            include_debug=True,
        )
        rooms_by_type = {}
        for room in result["rooms"]:
            rooms_by_type.setdefault(room["room_type"], []).append(room)

        self.assertEqual(rooms_by_type["hydromassage_room"][0]["machine_count"], 4)
        self.assertEqual(rooms_by_type["massage_chair_room"][0]["machine_count"], 2)
        self.assertEqual(rooms_by_type["tanning_room"][0]["machine_count"], 1)
        self.assertEqual(rooms_by_type["hybrid_room"][0]["machine_count"], 1)
        self.assertTrue(rooms_by_type["massage_chair_room"][0]["requires_tv"])
        self.assertFalse(rooms_by_type["hydromassage_room"][0]["requires_tv"])
        self.assertFalse(rooms_by_type["tanning_room"][0]["requires_tv"])

        placements_by_room = {}
        for placement in result["placements"]:
            placements_by_room.setdefault(placement["room_id"], []).append(placement)

        self.assertEqual(len(placements_by_room["hydromassage_room-1"]), 4)
        self.assertEqual(len(placements_by_room["massage_chair_room-1"]), 2)
        self.assertEqual(len(placements_by_room["hybrid_room-1"]), 1)

        hydro_room = rooms_by_type["hydromassage_room"][0]
        hydro_rect = hydro_room["rect"]
        hydro_placements = sorted(placements_by_room["hydromassage_room-1"], key=lambda item: item["machine"]["x"])
        if hydro_room["attached_edge"] in {"north", "south"}:
            if hydro_room["attached_edge"] == "north":
                setback = hydro_rect["y"] + hydro_rect["d"] - max(item["machine"]["y"] + item["machine"]["d"] for item in hydro_placements)
            else:
                setback = min(item["machine"]["y"] for item in hydro_placements) - hydro_rect["y"]
        else:
            if hydro_room["attached_edge"] == "east":
                setback = min(item["machine"]["x"] for item in hydro_placements) - hydro_rect["x"]
            else:
                setback = hydro_rect["x"] + hydro_rect["w"] - max(item["machine"]["x"] + item["machine"]["w"] for item in hydro_placements)
        self.assertAlmostEqual(setback, 52.0)

        partial_walls = [wall for wall in result["walls"] if wall.get("source_id") == "hydromassage_room-1" and wall.get("wall_type") == "partial_height"]
        self.assertEqual(len(partial_walls), 4)
        self.assertTrue(all(not wall["full_height"] for wall in partial_walls))

    def test_optional_rooms_default_to_zero_and_overrides_are_honored(self):
        spec, equipment, room_specs, _, _ = load_spa_inputs()
        payload = {
            "shell": {"w": 1200, "d": 900},
            "entry_edge": "west",
            "lounge": {"auto_size": False, "w": 320, "d": 260},
            "rooms": {
                "total_body_enhancement_room": {
                    "count": 1,
                    "instances": [{"variant": "total_body_enhancement_unit", "door_width": 42}]
                },
                "wellness_pod_room": {
                    "count": 1,
                    "instances": [{"variant": "wellness_pod", "door_width": 44}]
                }
            },
            "include_debug": True,
        }
        sanitized = sanitize_spa_request(payload, spec)
        result = generate_spa_layout(
            shell=sanitized["shell"],
            entry_edge=sanitized["entry_edge"],
            lounge_input=sanitized["lounge"],
            rooms_input=sanitized["rooms"],
            room_specs=room_specs,
            equipment=equipment,
            include_debug=True,
        )

        room_ids = {room["id"]: room for room in result["rooms"]}
        self.assertIn("total_body_enhancement_room-1", room_ids)
        self.assertIn("wellness_pod_room-1", room_ids)
        self.assertEqual(room_ids["total_body_enhancement_room-1"]["door_width"], 42)
        self.assertEqual(room_ids["wellness_pod_room-1"]["door_width"], 44)

    def test_hydromassage_room_count_is_fixed_to_one(self):
        spec, _, _, _, _ = load_spa_inputs()
        payload = {
            "rooms": {
                "hydromassage_room": {
                    "count": 3,
                    "instances": [
                        {"variant": "hydromassage_bed", "door_width": 36, "machine_count": 4},
                        {"variant": "hydromassage_bed", "door_width": 36, "machine_count": 4},
                        {"variant": "hydromassage_bed", "door_width": 36, "machine_count": 4},
                    ],
                }
            }
        }
        sanitized = sanitize_spa_request(payload, spec)
        self.assertEqual(sanitized["rooms"]["hydromassage_room"]["count"], 1)
        self.assertEqual(len(sanitized["rooms"]["hydromassage_room"]["instances"]), 1)

    def test_small_shell_returns_unplaced_room_warnings(self):
        spec, equipment, room_specs, _, _ = load_spa_inputs()
        payload = {
            "shell": {"w": 360, "d": 300},
            "entry_edge": "south",
            "lounge": {"auto_size": False, "w": 180, "d": 140},
            "rooms": {
                "hydromassage_room": {"count": 1, "instances": [{"variant": "hydromassage_bed", "door_width": 36}]},
                "massage_chair_room": {"count": 1, "instances": [{"variant": "massage_chair_standard", "door_width": 36}]},
                "tanning_room": {
                    "count": 2,
                    "instances": [
                        {"variant": "tanning_bed", "door_width": 36},
                        {"variant": "tanning_bed", "door_width": 36},
                    ],
                },
                "hybrid_room": {"count": 1, "instances": [{"variant": "hybrid_bed", "door_width": 36}]},
            },
            "include_debug": True,
        }
        sanitized = sanitize_spa_request(payload, spec)
        result = generate_spa_layout(
            shell=sanitized["shell"],
            entry_edge=sanitized["entry_edge"],
            lounge_input=sanitized["lounge"],
            rooms_input=sanitized["rooms"],
            room_specs=room_specs,
            equipment=equipment,
            include_debug=True,
        )

        self.assertGreater(len(result["unplaced_rooms"]), 0)
        self.assertGreater(len(result["warnings"]), 0)
        self.assertIn("rooms", result)
        self.assertIn("doors", result)
        self.assertIn("walls", result)
        self.assertIn("placements", result)


if __name__ == "__main__":
    unittest.main()
