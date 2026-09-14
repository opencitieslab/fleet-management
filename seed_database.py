#!/usr/bin/env python3
"""
Durban Solid Waste (DSW) Fleet Management Database Seeder.

Seeds the OpenRemote PostgreSQL database with realistic solid waste fleet
management data for the eThekwini Municipality / Durban Solid Waste unit,
including collection vehicles, waste management facilities, collection route
telemetry, and 7-day operational insight datapoints.

Requires: psycopg2-binary
    pip install psycopg2-binary

Usage:
    python seed_database.py [--host HOST] [--port PORT] [--db DB] [--user USER] [--password PASSWORD]
"""
from __future__ import annotations

import argparse
import json
import random
import string
import uuid
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    print("psycopg2 is required. Install it with: pip install psycopg2-binary")
    raise SystemExit(1)

SAST = timezone(timedelta(hours=2))

# ---------------------------------------------------------------------------
# ID generation (matches OpenRemote UniqueIdentifierGenerator)
# ---------------------------------------------------------------------------
BASE62_CHARS = string.ascii_letters + string.digits


def generate_id(seed: Optional[str] = None) -> str:
    if seed is not None:
        rng = random.Random(seed)
        raw = bytes(rng.getrandbits(8) for _ in range(16))
    else:
        raw = uuid.uuid4().bytes
    num = int.from_bytes(raw, "big")
    chars: list[str] = []
    while num > 0:
        num, rem = divmod(num, 62)
        chars.append(BASE62_CHARS[rem])
    return "".join(reversed(chars)).rjust(22, "0")


def generate_imei(prefix: str = "86") -> str:
    body = prefix + "".join(str(random.randint(0, 9)) for _ in range(12))
    total = 0
    for i, ch in enumerate(body):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    check = (10 - (total % 10)) % 10
    return body + str(check)


# ---------------------------------------------------------------------------
# Durban geography
# ---------------------------------------------------------------------------
DURBAN_LOCATIONS: dict[str, dict] = {
    "Durban CBD": {"lat": -29.8587, "lng": 31.0218, "alt": 8.0},
    "Bayhead Industrial": {"lat": -29.8850, "lng": 31.0350, "alt": 5.0},
    "Umhlanga Rocks": {"lat": -29.7300, "lng": 31.0850, "alt": 45.0},
    "La Lucia Ridge": {"lat": -29.7550, "lng": 31.0500, "alt": 120.0},
    "Pinetown": {"lat": -29.8180, "lng": 30.8560, "alt": 305.0},
    "Westville": {"lat": -29.8330, "lng": 30.9230, "alt": 250.0},
    "Chatsworth": {"lat": -29.9170, "lng": 30.8930, "alt": 65.0},
    "Phoenix": {"lat": -29.7170, "lng": 30.9830, "alt": 80.0},
    "Umlazi": {"lat": -29.9670, "lng": 30.8930, "alt": 35.0},
    "KwaMashu": {"lat": -29.7500, "lng": 30.9670, "alt": 90.0},
    "Amanzimtoti": {"lat": -30.0520, "lng": 30.8700, "alt": 15.0},
    "Isipingo": {"lat": -29.9980, "lng": 30.9350, "alt": 20.0},
    "Tongaat": {"lat": -29.5730, "lng": 31.1170, "alt": 60.0},
    "Hillcrest": {"lat": -29.7770, "lng": 30.7670, "alt": 550.0},
    "Cato Ridge": {"lat": -29.7350, "lng": 30.5850, "alt": 680.0},
    "Verulam": {"lat": -29.6430, "lng": 31.0450, "alt": 70.0},
    "Durban North": {"lat": -29.7950, "lng": 31.0350, "alt": 40.0},
    "Berea": {"lat": -29.8500, "lng": 31.0100, "alt": 95.0},
    "Musgrave": {"lat": -29.8400, "lng": 31.0050, "alt": 85.0},
    "Springfield Park": {"lat": -29.8100, "lng": 30.9950, "alt": 30.0},
    "Clairwood": {"lat": -29.9050, "lng": 30.9780, "alt": 15.0},
    "Maydon Wharf": {"lat": -29.8620, "lng": 31.0180, "alt": 5.0},
    "Cornubia": {"lat": -29.6830, "lng": 31.0280, "alt": 95.0},
    "Merebank": {"lat": -29.9350, "lng": 30.9650, "alt": 12.0},
    "Jacobs": {"lat": -29.9150, "lng": 30.9700, "alt": 18.0},
    "Inanda": {"lat": -29.7100, "lng": 30.9350, "alt": 120.0},
    "Bisasar Road": {"lat": -29.8060, "lng": 31.0070, "alt": 60.0},
    "Mariannhill": {"lat": -29.8180, "lng": 30.8290, "alt": 420.0},
    "Buffelsdraai": {"lat": -29.6250, "lng": 30.9850, "alt": 180.0},
}

SA_LICENSE_PLATE_PREFIXES = ["ND", "NP", "NR", "NN"]

# ---------------------------------------------------------------------------
# DSW vehicle fleet
# ---------------------------------------------------------------------------
VEHICLE_MAKES_MODELS = [
    ("FAW", "28.290FD Compactor"),
    ("UD Trucks", "Quester CWE 330"),
    ("Hino", "500 1626 Compactor"),
    ("Isuzu", "FTR 850 Compactor"),
    ("Mercedes-Benz", "Econic 2630"),
    ("Bell", "B30E Articulated"),
    ("Hyundai", "Mighty EX8 Skip"),
    ("Toyota", "Hilux 2.4 GD-6"),
    ("Ford", "Ranger 2.0 Bi-Turbo"),
    ("Nissan", "NP300 Hardbody"),
    ("Hino", "300 714 Flatbed"),
    ("UD Trucks", "Croner PKE 250"),
]

DSW_COLOURS = [
    (0, 100, 50),      # DSW municipal green
    (0, 120, 60),      # DSW green variant
    (255, 200, 0),     # DSW yellow
    (255, 255, 255),   # White
    (220, 220, 220),   # Light grey
    (255, 140, 0),     # Orange (high-vis)
]

FLEET_GROUPS = [
    {
        "name": "Residential Collection - North",
        "prefix": "DSW-RN",
        "count": 6,
        "locations": ["KwaMashu", "Phoenix", "Umhlanga Rocks", "Verulam", "Tongaat", "Cornubia"],
        "vehicle_indices": [0, 2, 3, 0, 2, 3],
        "purpose": "North zone residential waste collection",
        "landfill": "Bisasar Road",
    },
    {
        "name": "Residential Collection - South",
        "prefix": "DSW-RS",
        "count": 6,
        "locations": ["Chatsworth", "Umlazi", "Amanzimtoti", "Isipingo", "Clairwood", "Merebank"],
        "vehicle_indices": [0, 1, 2, 3, 0, 2],
        "purpose": "South zone residential waste collection",
        "landfill": "Mariannhill",
    },
    {
        "name": "Residential Collection - Central",
        "prefix": "DSW-RC",
        "count": 5,
        "locations": ["Durban CBD", "Berea", "Musgrave", "Durban North", "Westville"],
        "vehicle_indices": [0, 2, 3, 1, 0],
        "purpose": "Central zone residential waste collection",
        "landfill": "Bisasar Road",
    },
    {
        "name": "Residential Collection - Outer West",
        "prefix": "DSW-RW",
        "count": 4,
        "locations": ["Pinetown", "Hillcrest", "Cato Ridge", "Westville"],
        "vehicle_indices": [0, 2, 3, 1],
        "purpose": "Outer west residential waste collection",
        "landfill": "Mariannhill",
    },
    {
        "name": "Commercial & Industrial Collection",
        "prefix": "DSW-CI",
        "count": 5,
        "locations": ["Bayhead Industrial", "Springfield Park", "Maydon Wharf", "Clairwood", "Jacobs"],
        "vehicle_indices": [4, 1, 4, 1, 11],
        "purpose": "Commercial and industrial waste collection",
        "landfill": "Bisasar Road",
    },
    {
        "name": "Skip Truck Fleet",
        "prefix": "DSW-SK",
        "count": 4,
        "locations": ["Springfield Park", "Chatsworth", "KwaMashu", "Isipingo"],
        "vehicle_indices": [6, 6, 6, 6],
        "purpose": "Skip container delivery and collection",
        "landfill": "Bisasar Road",
    },
    {
        "name": "Illegal Dumping Response",
        "prefix": "DSW-ID",
        "count": 3,
        "locations": ["KwaMashu", "Inanda", "Phoenix"],
        "vehicle_indices": [10, 10, 9],
        "purpose": "Illegal dump site cleanup and response",
        "landfill": "Buffelsdraai",
    },
    {
        "name": "Landfill Operations",
        "prefix": "DSW-LF",
        "count": 3,
        "locations": ["Bisasar Road", "Mariannhill", "Buffelsdraai"],
        "vehicle_indices": [5, 5, 5],
        "purpose": "On-site landfill vehicle operations",
        "landfill": None,
    },
    {
        "name": "Supervisor / Inspection",
        "prefix": "DSW-SI",
        "count": 4,
        "locations": ["Springfield Park", "La Lucia Ridge", "Chatsworth", "Durban CBD"],
        "vehicle_indices": [7, 8, 7, 8],
        "purpose": "Ward inspection and route supervision",
        "landfill": None,
    },
]

# ---------------------------------------------------------------------------
# DSW Facilities
# ---------------------------------------------------------------------------
DSW_FACILITIES = [
    {
        "name": "Bisasar Road Landfill",
        "facility_type": "landfill",
        "lat": -29.8060, "lng": 31.0070, "alt": 60.0,
        "daily_capacity_tonnes": 3500,
        "current_load_pct": 72,
        "status": "operational",
        "operating_hours": "05:00-17:00",
        "notes": "Largest landfill in Africa. Methane-to-electricity CDM project on site.",
    },
    {
        "name": "Mariannhill Landfill",
        "facility_type": "landfill",
        "lat": -29.8180, "lng": 30.8290, "alt": 420.0,
        "daily_capacity_tonnes": 2000,
        "current_load_pct": 58,
        "status": "operational",
        "operating_hours": "05:00-17:00",
        "notes": "Serves south and outer west collection zones.",
    },
    {
        "name": "Buffelsdraai Landfill",
        "facility_type": "landfill",
        "lat": -29.6250, "lng": 30.9850, "alt": 180.0,
        "daily_capacity_tonnes": 2500,
        "current_load_pct": 34,
        "status": "operational",
        "operating_hours": "05:00-17:00",
        "notes": "Newest regional landfill with community reforestation project.",
    },
    {
        "name": "Springfield DSW Depot",
        "facility_type": "depot",
        "lat": -29.8100, "lng": 30.9950, "alt": 30.0,
        "daily_capacity_tonnes": 0,
        "current_load_pct": 0,
        "status": "operational",
        "operating_hours": "04:30-22:00",
        "notes": "Main fleet depot. Vehicle maintenance and shift dispatch.",
    },
    {
        "name": "KwaMashu DSW Depot",
        "facility_type": "depot",
        "lat": -29.7500, "lng": 30.9670, "alt": 90.0,
        "daily_capacity_tonnes": 0,
        "current_load_pct": 0,
        "status": "operational",
        "operating_hours": "04:30-18:00",
        "notes": "North zone dispatch depot.",
    },
    {
        "name": "Chatsworth DSW Depot",
        "facility_type": "depot",
        "lat": -29.9170, "lng": 30.8930, "alt": 65.0,
        "daily_capacity_tonnes": 0,
        "current_load_pct": 0,
        "status": "operational",
        "operating_hours": "04:30-18:00",
        "notes": "South zone dispatch depot.",
    },
    {
        "name": "Isipingo DSW Depot",
        "facility_type": "depot",
        "lat": -29.9980, "lng": 30.9350, "alt": 20.0,
        "daily_capacity_tonnes": 0,
        "current_load_pct": 0,
        "status": "operational",
        "operating_hours": "04:30-18:00",
        "notes": "Southern coastal area depot.",
    },
    {
        "name": "Umlazi Transfer Station",
        "facility_type": "transfer_station",
        "lat": -29.9670, "lng": 30.8930, "alt": 35.0,
        "daily_capacity_tonnes": 800,
        "current_load_pct": 45,
        "status": "operational",
        "operating_hours": "05:00-16:00",
        "notes": "Waste consolidation before Mariannhill Landfill transfer.",
    },
    {
        "name": "Phoenix Transfer Station",
        "facility_type": "transfer_station",
        "lat": -29.7170, "lng": 30.9830, "alt": 80.0,
        "daily_capacity_tonnes": 600,
        "current_load_pct": 62,
        "status": "operational",
        "operating_hours": "05:00-16:00",
        "notes": "North zone consolidation point.",
    },
]

# ---------------------------------------------------------------------------
# DSW waste collection routes (residential -> landfill)
# ---------------------------------------------------------------------------
COLLECTION_ROUTES: dict[str, list[tuple[float, float, float]]] = {
    "Bisasar Road": [
        # KwaMashu residential -> Phoenix -> Bisasar Road Landfill
        (-29.750, 30.967, 90), (-29.745, 30.975, 85), (-29.738, 30.980, 82),
        (-29.730, 30.983, 80), (-29.720, 30.983, 80), (-29.717, 30.983, 80),
        (-29.730, 30.990, 75), (-29.750, 31.000, 65), (-29.770, 31.005, 55),
        (-29.790, 31.007, 50), (-29.806, 31.007, 60),
    ],
    "Mariannhill": [
        # Chatsworth suburbs -> via Pinetown Rd -> Mariannhill Landfill
        (-29.917, 30.893, 65), (-29.910, 30.885, 70), (-29.900, 30.875, 80),
        (-29.890, 30.865, 120), (-29.875, 30.855, 180), (-29.860, 30.845, 250),
        (-29.845, 30.838, 320), (-29.830, 30.832, 380), (-29.818, 30.829, 420),
    ],
    "Buffelsdraai": [
        # KwaMashu -> Inanda -> Buffelsdraai Landfill
        (-29.750, 30.967, 90), (-29.740, 30.950, 100), (-29.725, 30.940, 110),
        (-29.710, 30.935, 120), (-29.695, 30.940, 130), (-29.680, 30.950, 145),
        (-29.660, 30.960, 160), (-29.640, 30.975, 170), (-29.625, 30.985, 180),
    ],
    "Central-Bisasar": [
        # Berea / Musgrave -> CBD -> Bisasar Road Landfill
        (-29.840, 31.005, 85), (-29.845, 31.010, 80), (-29.850, 31.015, 70),
        (-29.855, 31.020, 50), (-29.858, 31.022, 8), (-29.850, 31.018, 20),
        (-29.840, 31.012, 35), (-29.825, 31.010, 50), (-29.810, 31.008, 55),
        (-29.806, 31.007, 60),
    ],
    "West-Mariannhill": [
        # Pinetown -> Westville -> Mariannhill Landfill
        (-29.818, 30.856, 305), (-29.820, 30.850, 310), (-29.825, 30.845, 330),
        (-29.830, 30.840, 360), (-29.828, 30.835, 380), (-29.822, 30.832, 400),
        (-29.818, 30.829, 420),
    ],
    "Commercial-Bisasar": [
        # Bayhead Industrial -> Springfield Park -> Bisasar Road Landfill
        (-29.885, 31.035, 5), (-29.870, 31.020, 8), (-29.855, 31.010, 15),
        (-29.840, 31.000, 25), (-29.825, 30.998, 28), (-29.810, 30.995, 30),
        (-29.806, 31.007, 60),
    ],
}

# Map fleet groups to their route key
GROUP_ROUTE_MAP = {
    "Residential Collection - North": "Bisasar Road",
    "Residential Collection - South": "Mariannhill",
    "Residential Collection - Central": "Central-Bisasar",
    "Residential Collection - Outer West": "West-Mariannhill",
    "Commercial & Industrial Collection": "Commercial-Bisasar",
    "Skip Truck Fleet": "Bisasar Road",
    "Illegal Dumping Response": "Buffelsdraai",
}

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def random_sa_plate() -> str:
    prefix = random.choice(SA_LICENSE_PLATE_PREFIXES)
    num = random.randint(10000, 99999)
    suffix = "".join(random.choices(string.ascii_uppercase, k=2))
    return f"{prefix} {num} {suffix}"


def jitter_location(lat: float, lng: float, radius_km: float = 1.5) -> tuple[float, float]:
    lat_offset = random.gauss(0, radius_km / 111.0)
    lng_offset = random.gauss(0, radius_km / (111.0 * math.cos(math.radians(lat))))
    return round(lat + lat_offset, 6), round(lng + lng_offset, 6)


def build_attribute(name: str, value_type: str, value, timestamp_ms: int,
                    meta: Optional[dict] = None) -> dict:
    return {
        "meta": meta or {},
        "name": name,
        "type": value_type,
        "value": value,
        "timestamp": timestamp_ms,
    }


PAYLOAD_META = {"storeDataPoints": True, "ruleState": True, "readOnly": True}


def build_car_attributes(
    *, imei: str, lat: float, lng: float, alt: float,
    direction: int, speed: float, odometer: float,
    ignition: bool, movement: bool, model_number: str,
    license_plate: str, model_year: int,
    colour: tuple[int, int, int], satellites: int,
    priority: int, timestamp_ms: int,
) -> dict:
    attrs: dict[str, dict] = {}
    attrs["location"] = build_attribute(
        "location", "GEO_JSONPoint",
        {"type": "Point", "coordinates": [lng, lat, alt]},
        timestamp_ms, meta={**PAYLOAD_META, "label": "Location"},
    )
    attrs["IMEI"] = build_attribute("IMEI", "text", imei, timestamp_ms)
    attrs["lastContact"] = build_attribute(
        "lastContact", "dateAndTime", timestamp_ms, timestamp_ms,
        meta={**PAYLOAD_META, "label": "Last message time"},
    )
    attrs["modelNumber"] = build_attribute("modelNumber", "text", model_number, timestamp_ms)
    attrs["direction"] = build_attribute(
        "direction", "direction", direction, timestamp_ms,
        meta={**PAYLOAD_META, "label": "Direction"},
    )
    attrs["color"] = build_attribute(
        "color", "colourRGB",
        {"r": colour[0], "g": colour[1], "b": colour[2]}, timestamp_ms,
    )
    attrs["modelYear"] = build_attribute("modelYear", "positiveInteger", model_year, timestamp_ms)
    attrs["licensePlate"] = build_attribute("licensePlate", "text", license_plate, timestamp_ms)
    attrs["239"] = build_attribute(
        "239", "boolean", ignition, timestamp_ms,
        meta={**PAYLOAD_META, "label": "Ignition status"},
    )
    attrs["240"] = build_attribute(
        "240", "boolean", movement, timestamp_ms,
        meta={**PAYLOAD_META, "label": "Movement status"},
    )
    attrs["16"] = build_attribute(
        "16", "number", odometer, timestamp_ms,
        meta={**PAYLOAD_META, "label": "Odometer"},
    )
    attrs["sp"] = build_attribute(
        "sp", "number", speed, timestamp_ms,
        meta={**PAYLOAD_META, "label": "Speed"},
    )
    attrs["alt"] = build_attribute(
        "alt", "number", alt, timestamp_ms,
        meta={**PAYLOAD_META, "label": "Altitude"},
    )
    attrs["sat"] = build_attribute(
        "sat", "number", satellites, timestamp_ms,
        meta={**PAYLOAD_META, "label": "Number of satellites in use"},
    )
    attrs["pr"] = build_attribute(
        "pr", "number", priority, timestamp_ms,
        meta={**PAYLOAD_META, "label": "Payload priority (0-2)"},
    )
    attrs["evt"] = build_attribute(
        "evt", "number", 0, timestamp_ms,
        meta={**PAYLOAD_META, "label": "Event triggered by"},
    )
    attrs["notes"] = build_attribute("notes", "text", "", timestamp_ms)
    return attrs


def build_facility_attributes(facility: dict, timestamp_ms: int) -> dict:
    attrs: dict[str, dict] = {}
    attrs["location"] = build_attribute(
        "location", "GEO_JSONPoint",
        {"type": "Point", "coordinates": [facility["lng"], facility["lat"], facility["alt"]]},
        timestamp_ms,
    )
    attrs["facilityType"] = build_attribute("facilityType", "text", facility["facility_type"], timestamp_ms)
    attrs["status"] = build_attribute(
        "status", "text", facility["status"], timestamp_ms,
        meta={**PAYLOAD_META, "label": "Operational Status"},
    )
    attrs["dailyCapacityTonnes"] = build_attribute(
        "dailyCapacityTonnes", "number", facility["daily_capacity_tonnes"], timestamp_ms,
        meta={**PAYLOAD_META, "label": "Daily Capacity (tonnes)"},
    )
    attrs["currentLoadPercentage"] = build_attribute(
        "currentLoadPercentage", "number", facility["current_load_pct"], timestamp_ms,
        meta={**PAYLOAD_META, "label": "Current Load %"},
    )
    attrs["operatingHours"] = build_attribute("operatingHours", "text", facility["operating_hours"], timestamp_ms)
    attrs["notes"] = build_attribute("notes", "text", facility.get("notes", ""), timestamp_ms)
    return attrs


# ---------------------------------------------------------------------------
# Route interpolation and bearing
# ---------------------------------------------------------------------------

def interpolate_route(
    route: list[tuple[float, float, float]], num_points: int,
) -> list[tuple[float, float, float]]:
    if num_points <= len(route):
        return route[:num_points]
    total_dist = 0.0
    dists = [0.0]
    for i in range(1, len(route)):
        d = math.sqrt((route[i][0] - route[i - 1][0]) ** 2 + (route[i][1] - route[i - 1][1]) ** 2)
        total_dist += d
        dists.append(total_dist)
    result: list[tuple[float, float, float]] = []
    for j in range(num_points):
        t = (j / (num_points - 1)) * total_dist if num_points > 1 else 0
        for i in range(1, len(dists)):
            if dists[i] >= t:
                seg_len = dists[i] - dists[i - 1]
                frac = (t - dists[i - 1]) / seg_len if seg_len > 0 else 0
                lat = route[i - 1][0] + frac * (route[i][0] - route[i - 1][0])
                lng = route[i - 1][1] + frac * (route[i][1] - route[i - 1][1])
                alt = route[i - 1][2] + frac * (route[i][2] - route[i - 1][2])
                jlat, jlng = jitter_location(lat, lng, radius_km=0.05)
                result.append((round(jlat, 6), round(jlng, 6), round(alt, 1)))
                break
        else:
            result.append(route[-1])
    return result


def bearing_between(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    d_lng = math.radians(lng2 - lng1)
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    x = math.sin(d_lng) * math.cos(lat2_r)
    y = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(d_lng)
    return int((math.degrees(math.atan2(x, y)) + 360) % 360)


# ---------------------------------------------------------------------------
# Shift-aware datapoint generation
# ---------------------------------------------------------------------------

def generate_shift_datapoints(
    vehicle: dict, route: list[tuple[float, float, float]],
    day_offset: int, now: datetime, is_afternoon: bool = False,
) -> list[tuple]:
    """Generate one full shift of datapoints for a vehicle on a given day.

    Simulates: depot departure -> collection leg -> landfill dump -> return
    collection -> landfill dump -> depot return.  Two landfill trips per shift.
    """
    rows: list[tuple] = []
    vid = vehicle["id"]

    shift_start_hour = 14 if is_afternoon else 5
    shift_start_min = random.randint(0, 30)
    base_day = now - timedelta(days=day_offset)
    shift_start = base_day.replace(
        hour=shift_start_hour, minute=shift_start_min, second=0, microsecond=0,
        tzinfo=SAST,
    )

    base_odo = vehicle["attributes"]["16"]["value"] - random.uniform(200, 1000) - day_offset * random.uniform(60, 150)
    odo = base_odo
    t = shift_start

    reversed_route = list(reversed(route))

    for trip in range(2):
        # --- Collection leg: slow driving through residential area ---
        collection_points = random.randint(15, 25)
        for cp in range(collection_points):
            frac = cp / max(collection_points - 1, 1)
            idx = min(int(frac * (len(route) - 1)), len(route) - 2)
            sub_frac = frac * (len(route) - 1) - idx
            lat = route[idx][0] + sub_frac * (route[idx + 1][0] - route[idx][0])
            lng = route[idx][1] + sub_frac * (route[idx + 1][1] - route[idx][1])
            alt = route[idx][2] + sub_frac * (route[idx + 1][2] - route[idx][2])
            jlat, jlng = jitter_location(lat, lng, radius_km=0.08)

            is_stopped = random.random() < 0.35
            speed = 0.0 if is_stopped else round(random.uniform(4, 18), 1)
            movement = speed > 0
            odo += random.uniform(0.05, 0.4) if movement else 0

            if cp < collection_points - 1:
                nxt_frac = (cp + 1) / max(collection_points - 1, 1)
                nxt_idx = min(int(nxt_frac * (len(route) - 1)), len(route) - 2)
                nxt_sf = nxt_frac * (len(route) - 1) - nxt_idx
                nxt_lat = route[nxt_idx][0] + nxt_sf * (route[nxt_idx + 1][0] - route[nxt_idx][0])
                nxt_lng = route[nxt_idx][1] + nxt_sf * (route[nxt_idx + 1][1] - route[nxt_idx][1])
                direction = bearing_between(jlat, jlng, nxt_lat, nxt_lng)
            else:
                direction = 0

            ts_no_tz = t.astimezone(timezone.utc).replace(tzinfo=None)
            ts_ms = int(t.timestamp() * 1000)
            priority = 2 if (is_stopped and random.random() < 0.05) else 0

            rows.extend([
                (ts_no_tz, vid, "location", json.dumps({"type": "Point", "coordinates": [round(jlng, 6), round(jlat, 6), round(alt, 1)]})),
                (ts_no_tz, vid, "sp", json.dumps(speed)),
                (ts_no_tz, vid, "direction", json.dumps(direction)),
                (ts_no_tz, vid, "16", json.dumps(round(odo, 1))),
                (ts_no_tz, vid, "alt", json.dumps(round(alt, 1))),
                (ts_no_tz, vid, "sat", json.dumps(random.randint(8, 14))),
                (ts_no_tz, vid, "239", json.dumps(True)),
                (ts_no_tz, vid, "240", json.dumps(movement)),
                (ts_no_tz, vid, "lastContact", json.dumps(ts_ms)),
                (ts_no_tz, vid, "pr", json.dumps(priority)),
            ])

            stop_duration = random.uniform(20, 90) if is_stopped else 0
            t += timedelta(seconds=random.uniform(30, 120) + stop_duration)

        # --- Transit to landfill: faster driving ---
        landfill_pt = route[-1]
        transit_steps = random.randint(5, 8)
        for ts_idx in range(transit_steps):
            frac = ts_idx / max(transit_steps - 1, 1)
            prev = route[len(route) // 2]
            lat = prev[0] + frac * (landfill_pt[0] - prev[0])
            lng = prev[1] + frac * (landfill_pt[1] - prev[1])
            alt = prev[2] + frac * (landfill_pt[2] - prev[2])
            jlat, jlng = jitter_location(lat, lng, radius_km=0.1)
            speed = round(random.uniform(35, 65), 1)
            odo += random.uniform(0.5, 2.0)
            direction = bearing_between(jlat, jlng, landfill_pt[0], landfill_pt[1])

            ts_no_tz = t.astimezone(timezone.utc).replace(tzinfo=None)
            ts_ms = int(t.timestamp() * 1000)
            rows.extend([
                (ts_no_tz, vid, "location", json.dumps({"type": "Point", "coordinates": [round(jlng, 6), round(jlat, 6), round(alt, 1)]})),
                (ts_no_tz, vid, "sp", json.dumps(speed)),
                (ts_no_tz, vid, "direction", json.dumps(direction)),
                (ts_no_tz, vid, "16", json.dumps(round(odo, 1))),
                (ts_no_tz, vid, "239", json.dumps(True)),
                (ts_no_tz, vid, "240", json.dumps(True)),
                (ts_no_tz, vid, "lastContact", json.dumps(ts_ms)),
            ])
            t += timedelta(seconds=random.uniform(60, 180))

        # --- Dwell at landfill: stationary 15-30 min ---
        dwell_minutes = random.uniform(15, 30)
        dwell_points = random.randint(4, 8)
        for dp in range(dwell_points):
            jlat, jlng = jitter_location(landfill_pt[0], landfill_pt[1], radius_km=0.05)
            ts_no_tz = t.astimezone(timezone.utc).replace(tzinfo=None)
            ts_ms = int(t.timestamp() * 1000)
            rows.extend([
                (ts_no_tz, vid, "location", json.dumps({"type": "Point", "coordinates": [round(jlng, 6), round(jlat, 6), round(landfill_pt[2], 1)]})),
                (ts_no_tz, vid, "sp", json.dumps(0.0)),
                (ts_no_tz, vid, "239", json.dumps(True)),
                (ts_no_tz, vid, "240", json.dumps(False)),
                (ts_no_tz, vid, "lastContact", json.dumps(ts_ms)),
                (ts_no_tz, vid, "pr", json.dumps(1 if random.random() < 0.1 else 0)),
            ])
            t += timedelta(minutes=dwell_minutes / dwell_points)

        # --- Return transit to collection zone ---
        return_steps = random.randint(4, 6)
        start_pt = route[0]
        for rs_idx in range(return_steps):
            frac = rs_idx / max(return_steps - 1, 1)
            lat = landfill_pt[0] + frac * (start_pt[0] - landfill_pt[0])
            lng = landfill_pt[1] + frac * (start_pt[1] - landfill_pt[1])
            alt = landfill_pt[2] + frac * (start_pt[2] - landfill_pt[2])
            jlat, jlng = jitter_location(lat, lng, radius_km=0.1)
            speed = round(random.uniform(40, 70), 1)
            odo += random.uniform(0.5, 2.0)
            direction = bearing_between(jlat, jlng, start_pt[0], start_pt[1])

            ts_no_tz = t.astimezone(timezone.utc).replace(tzinfo=None)
            ts_ms = int(t.timestamp() * 1000)
            rows.extend([
                (ts_no_tz, vid, "location", json.dumps({"type": "Point", "coordinates": [round(jlng, 6), round(jlat, 6), round(alt, 1)]})),
                (ts_no_tz, vid, "sp", json.dumps(speed)),
                (ts_no_tz, vid, "direction", json.dumps(direction)),
                (ts_no_tz, vid, "16", json.dumps(round(odo, 1))),
                (ts_no_tz, vid, "239", json.dumps(True)),
                (ts_no_tz, vid, "240", json.dumps(True)),
                (ts_no_tz, vid, "lastContact", json.dumps(ts_ms)),
            ])
            t += timedelta(seconds=random.uniform(60, 180))

        # Mid-shift break after first trip
        if trip == 0:
            break_mins = random.uniform(20, 40)
            ts_no_tz = t.astimezone(timezone.utc).replace(tzinfo=None)
            ts_ms = int(t.timestamp() * 1000)
            rows.extend([
                (ts_no_tz, vid, "sp", json.dumps(0.0)),
                (ts_no_tz, vid, "239", json.dumps(False)),
                (ts_no_tz, vid, "240", json.dumps(False)),
                (ts_no_tz, vid, "lastContact", json.dumps(ts_ms)),
                (ts_no_tz, vid, "pr", json.dumps(0)),
            ])
            t += timedelta(minutes=break_mins)

    # --- Shift end: ignition off ---
    ts_no_tz = t.astimezone(timezone.utc).replace(tzinfo=None)
    ts_ms = int(t.timestamp() * 1000)
    rows.extend([
        (ts_no_tz, vid, "sp", json.dumps(0.0)),
        (ts_no_tz, vid, "239", json.dumps(False)),
        (ts_no_tz, vid, "240", json.dumps(False)),
        (ts_no_tz, vid, "lastContact", json.dumps(ts_ms)),
    ])

    return rows


# ---------------------------------------------------------------------------
# Main seeding logic
# ---------------------------------------------------------------------------

def seed_database(conn_params: dict) -> None:
    conn = psycopg2.connect(**conn_params)
    conn.autocommit = False
    cur = conn.cursor()

    print("Connected to PostgreSQL database.")

    now = datetime.now(timezone.utc)
    now_ms = int(now.timestamp() * 1000)

    vehicles: list[dict] = []
    all_assets: list[dict] = []

    # ------------------------------------------------------------------
    # 1. Create DSW facility assets (ThingAsset)
    # ------------------------------------------------------------------
    facility_assets: list[dict] = []
    for fac in DSW_FACILITIES:
        fac_id = generate_id(f"dsw-facility-{fac['name']}")
        attrs = build_facility_attributes(fac, now_ms)
        facility_asset = {
            "id": fac_id,
            "name": fac["name"],
            "type": "ThingAsset",
            "realm": "master",
            "parent_id": None,
            "path": fac_id,
            "access_public_read": False,
            "version": 0,
            "created_on": now - timedelta(days=random.randint(365, 1095)),
            "attributes": attrs,
        }
        facility_assets.append(facility_asset)
        all_assets.append(facility_asset)

    print(f"Prepared {len(facility_assets)} DSW facility assets.")

    # ------------------------------------------------------------------
    # 2. Create vehicle assets (CarAsset)
    # ------------------------------------------------------------------
    for group in FLEET_GROUPS:
        for i in range(group["count"]):
            loc_name = group["locations"][i % len(group["locations"])]
            loc = DURBAN_LOCATIONS[loc_name]
            vi = group["vehicle_indices"][i % len(group["vehicle_indices"])]
            make, model = VEHICLE_MAKES_MODELS[vi]

            imei = generate_imei(prefix=f"86{random.randint(10, 99):02d}")
            asset_id = generate_id(imei)
            vehicle_name = f"{group['prefix']}-{i + 1:03d}"
            full_name = f"{vehicle_name} ({make} {model})"

            is_collection = "Collection" in group["name"] or "Skip" in group["name"]
            is_moving = random.random() < (0.55 if is_collection else 0.35)
            speed = round(random.uniform(5, 20 if is_collection else 60), 1) if is_moving else 0.0
            ignition = True if is_moving else random.random() < 0.2

            lat, lng = jitter_location(loc["lat"], loc["lng"])
            alt = loc["alt"] + random.uniform(-5, 5)
            direction = random.randint(0, 359) if is_moving else 0
            odometer = round(random.uniform(45000, 380000), 1)
            model_year = random.randint(2017, 2024)
            colour = random.choice(DSW_COLOURS)
            plate = random_sa_plate()
            satellites = random.randint(7, 14)
            priority = random.choices([0, 1, 2], weights=[75, 20, 5])[0]

            minutes_ago = random.randint(0, 60) if is_moving else random.randint(10, 300)
            last_contact = now - timedelta(minutes=minutes_ago)
            contact_ms = int(last_contact.timestamp() * 1000)

            attributes = build_car_attributes(
                imei=imei, lat=lat, lng=lng, alt=round(alt, 1),
                direction=direction, speed=speed, odometer=odometer,
                ignition=ignition, movement=is_moving,
                model_number="FMC003", license_plate=plate,
                model_year=model_year, colour=colour,
                satellites=satellites, priority=priority,
                timestamp_ms=contact_ms,
            )

            vehicle = {
                "id": asset_id,
                "name": full_name,
                "type": "CarAsset",
                "realm": "master",
                "parent_id": None,
                "path": asset_id,
                "access_public_read": False,
                "version": 0,
                "created_on": last_contact - timedelta(days=random.randint(60, 900)),
                "attributes": attributes,
                "imei": imei,
                "location_name": loc_name,
                "group": group["name"],
                "is_moving": is_moving,
                "route_key": GROUP_ROUTE_MAP.get(group["name"]),
            }
            vehicles.append(vehicle)
            all_assets.append(vehicle)

    print(f"Prepared {len(vehicles)} vehicle assets across {len(FLEET_GROUPS)} fleet groups.")

    # ------------------------------------------------------------------
    # Insert all assets
    # ------------------------------------------------------------------
    insert_sql = """
        INSERT INTO asset (id, attributes, created_on, name, parent_id, path, realm, type, access_public_read, version)
        VALUES (%s, %s::jsonb, %s, %s, %s, %s::ltree, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            attributes = EXCLUDED.attributes,
            name = EXCLUDED.name,
            version = asset.version + 1
    """
    for asset in all_assets:
        cur.execute(insert_sql, (
            asset["id"], json.dumps(asset["attributes"]),
            asset["created_on"], asset["name"], asset["parent_id"],
            asset["path"], asset["realm"], asset["type"],
            asset["access_public_read"], asset["version"],
        ))

    print(f"Inserted/updated {len(all_assets)} total assets.")

    # ------------------------------------------------------------------
    # 3. Generate 7-day shift-aware datapoints
    # ------------------------------------------------------------------
    print("Generating 7-day operational datapoints...")
    datapoint_rows: list[tuple] = []

    route_vehicles = [v for v in vehicles if v.get("route_key")]

    for vehicle in route_vehicles:
        route_key = vehicle["route_key"]
        route = COLLECTION_ROUTES.get(route_key)
        if not route:
            continue

        for day in range(7):
            is_afternoon = random.random() < 0.15
            day_rows = generate_shift_datapoints(vehicle, route, day, now, is_afternoon)
            datapoint_rows.extend(day_rows)

    # Supervisor / landfill ops get simpler patrol datapoints
    patrol_vehicles = [v for v in vehicles if not v.get("route_key")]
    for vehicle in patrol_vehicles:
        for day in range(7):
            base_day = now - timedelta(days=day)
            t = base_day.replace(hour=random.randint(6, 8), minute=random.randint(0, 59),
                                 second=0, microsecond=0, tzinfo=SAST)
            loc = DURBAN_LOCATIONS[vehicle["location_name"]]
            odo = vehicle["attributes"]["16"]["value"] - day * random.uniform(30, 80)

            for _ in range(random.randint(10, 20)):
                jlat, jlng = jitter_location(loc["lat"], loc["lng"], radius_km=3.0)
                speed = round(random.uniform(0, 50), 1)
                odo += random.uniform(0.2, 1.5)
                ts_no_tz = t.astimezone(timezone.utc).replace(tzinfo=None)
                ts_ms = int(t.timestamp() * 1000)
                datapoint_rows.extend([
                    (ts_no_tz, vehicle["id"], "location", json.dumps({"type": "Point", "coordinates": [round(jlng, 6), round(jlat, 6), loc["alt"]]})),
                    (ts_no_tz, vehicle["id"], "sp", json.dumps(speed)),
                    (ts_no_tz, vehicle["id"], "16", json.dumps(round(odo, 1))),
                    (ts_no_tz, vehicle["id"], "239", json.dumps(True)),
                    (ts_no_tz, vehicle["id"], "240", json.dumps(speed > 0)),
                    (ts_no_tz, vehicle["id"], "lastContact", json.dumps(ts_ms)),
                ])
                t += timedelta(minutes=random.uniform(10, 45))

    # Facility load percentage history
    for fac_asset in facility_assets:
        fac_data = next((f for f in DSW_FACILITIES if f["name"] == fac_asset["name"]), None)
        if not fac_data or fac_data["daily_capacity_tonnes"] == 0:
            continue
        for day in range(7):
            base_day = now - timedelta(days=day)
            for hour in range(5, 18):
                t = base_day.replace(hour=hour, minute=0, second=0, microsecond=0, tzinfo=SAST)
                ts_no_tz = t.astimezone(timezone.utc).replace(tzinfo=None)
                load_pct = max(10, min(95, fac_data["current_load_pct"] + random.gauss(0, 8) + (hour - 5) * random.uniform(0.5, 2.0)))
                datapoint_rows.append(
                    (ts_no_tz, fac_asset["id"], "currentLoadPercentage", json.dumps(round(load_pct, 1)))
                )

    if datapoint_rows:
        dp_sql = """
            INSERT INTO asset_datapoint (timestamp, entity_id, attribute_name, value)
            VALUES %s
            ON CONFLICT DO NOTHING
        """
        execute_values(cur, dp_sql, datapoint_rows, page_size=1000)

    print(f"Inserted {len(datapoint_rows)} historical datapoints.")

    conn.commit()
    cur.close()
    conn.close()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    total_collection = sum(g["count"] for g in FLEET_GROUPS if "Collection" in g["name"] or "Skip" in g["name"])
    total_support = sum(g["count"] for g in FLEET_GROUPS if "Collection" not in g["name"] and "Skip" not in g["name"])

    print("\n" + "=" * 70)
    print("  DURBAN SOLID WASTE — FLEET SEED COMPLETE")
    print("=" * 70)
    print(f"  Facility assets       : {len(facility_assets)}  (landfills, depots, transfer stations)")
    print(f"  Vehicle assets        : {len(vehicles)}  ({total_collection} collection + {total_support} support)")
    print(f"  Total assets seeded   : {len(all_assets)}")
    print(f"  Historical datapoints : {len(datapoint_rows):,}  (7-day history)")
    print(f"  Realm                 : master")
    print()
    print("  DSW Facilities:")
    for fa in facility_assets:
        ftype = fa["attributes"]["facilityType"]["value"]
        print(f"    [{ftype:16s}]  {fa['name']}")
    print()
    print("  Fleet Divisions:")
    for g in FLEET_GROUPS:
        print(f"    {g['name']:40s}  {g['count']} vehicles  ({g['purpose']})")
    print()
    print("  Sample Vehicles:")
    for v in vehicles[:6]:
        status = "MOVING" if v["is_moving"] else "PARKED"
        print(f"    [{status:6s}] {v['name']:50s} @ {v['location_name']}")
    if len(vehicles) > 6:
        print(f"    ... and {len(vehicles) - 6} more")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed the DSW fleet management PostgreSQL database with Durban solid waste data."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Database host (default: 127.0.0.1)")
    parser.add_argument("--port", default=5999, type=int, help="Database port (default: 5999)")
    parser.add_argument("--db", default="openremote", help="Database name (default: openremote)")
    parser.add_argument("--user", default="postgres", help="Database user (default: postgres)")
    parser.add_argument("--password", default="postgres", help="Database password (default: postgres)")
    args = parser.parse_args()

    conn_params = {
        "host": args.host,
        "port": args.port,
        "dbname": args.db,
        "user": args.user,
        "password": args.password,
    }

    print(f"Connecting to PostgreSQL at {args.host}:{args.port}/{args.db} ...")
    seed_database(conn_params)


if __name__ == "__main__":
    main()
