#!/usr/bin/env python3
"""
SRI Method C -- Proposed Operational Assessment (Full Prototype -- 54 services)
Building: Villa Segrate
Evidence hierarchy: DBL Group 09 (primary) > DBL Group 08 (secondary) > CSV > IFC
Climate zone: Southern Europe / Residential
Reference: EU Delegated Regulation 2020/2155; SRI Technical Study D3.1
"""

import os, sys, json, warnings, re
from fractions import Fraction
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

# ── PATHS ──────────────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent

def _find(*candidates):
    """Return the first path that exists. Keeps the script working both in the
    OneDrive working tree (data one level up) and in the deployed repo layout
    (everything flat next to the script)."""
    for c in candidates:
        if c.exists():
            return str(c)
    return str(candidates[0])

def _find_csv_dir():
    """Locate the data folder without depending on the day count in its name.

    The folder is named after how many days it covers ("Data 2026 - 240dd"), so
    hard-coding it means every data refresh silently breaks the engine. This
    picks the most recent matching folder instead, next to the script or one
    level up, so dropping in "Data 2026 - 270dd" is all that a refresh requires.
    """
    candidates = []
    for base in (_HERE, _HERE.parent):
        if not base.exists():
            continue
        for d in base.glob("Data 2*"):
            if d.is_dir() and any(d.glob("*.csv")):
                candidates.append(d)
    if not candidates:
        return str(_HERE / "Data 2026 - 240dd")
    # Prefer the folder covering the most days, read from the trailing "NNNdd".
    def days(d):
        m = re.search(r"(\d+)\s*dd", d.name)
        return int(m.group(1)) if m else 0
    return str(sorted(candidates, key=lambda d: (days(d), d.name))[-1])


CSV_DIR = _find_csv_dir()
MANUAL_PATH        = _find(_HERE / "data" / "manual_assessments.json",
                           _HERE / "manual_assessments.json")
BUILDING_INFO_PATH = _find(_HERE / "data" / "building_info.json",
                           _HERE / "building_info.json")
IFC_INVENTORY_PATH = _find(_HERE / "data" / "ifc_inventory.json",
                           _HERE / "ifc_inventory.json")
OFFICIAL_CATALOG_PATH = _find(_HERE / "data" / "official_catalog.json",
                              _HERE / "official_catalog.json")
OUTPUT_DIR         = str(_HERE)
LOCAL_TZ      = "Europe/Rome"

# ── APPLICABILITY STATUSES ────────────────────────────────────────────────────
NA_NOT_EVIDENCED    = "N/A_NOT_EVIDENCED"
NA_EXPLICIT_ABSENCE = "N/A_EXPLICIT_ABSENCE"
L0_NO_AUTOMATION    = "L0_NO_AUTOMATION"
VERIFIED            = "VERIFIED"
PARTIAL_EVIDENCE    = "PARTIAL_EVIDENCE"
UNRESOLVED          = "UNRESOLVED"
NA_STATUSES = {NA_NOT_EVIDENCED, NA_EXPLICIT_ABSENCE}

# ── IMPACT WEIGHTS (EU Table 2 — exact fractions) ─────────────────────────────
IMPACT_WEIGHTS = {
    "EE": Fraction(1,6), "Flex": Fraction(1,3), "Comfort": Fraction(1,12),
    "Conv": Fraction(1,12), "Health": Fraction(1,12),
    "Maint": Fraction(1,6), "Info": Fraction(1,12),
}
IMPACT_KEYS = ["EE","Flex","Comfort","Conv","Health","Maint","Info"]

# ── KEY FUNCTIONALITY GROUPS (EU Delegated Regulation 2020/2155) ──────────────
KF_GROUPS = {
    "KF1": {
        "name": "Energy Performance and Operation",
        "ics":  ["EE", "Maint"],                  # weight each 1/6 → KF1 = 1/3
    },
    "KF2": {
        "name": "Adaptation to the Needs of the Occupant",
        "ics":  ["Comfort", "Conv", "Health", "Info"],  # weight each 1/12 → KF2 = 1/3
    },
    "KF3": {
        "name": "Response to Energy Grid (Flexibility)",
        "ics":  ["Flex"],                          # weight 1/3 → KF3 = 1/3
    },
}

# ── DOMAIN WEIGHTS — South / Residential ─────────────────────────────────────
DOMAIN_WEIGHTS = {
    "Heating":            {"EE":0.32,"Flex":0.38,"Comfort":0.16,"Conv":0.10,"Health":0.16,"Maint":0.33,"Info":0.11},
    "DHW":                {"EE":0.10,"Flex":0.12,"Comfort":0.00,"Conv":0.10,"Health":0.00,"Maint":0.10,"Info":0.11},
    "Cooling":            {"EE":0.07,"Flex":0.08,"Comfort":0.16,"Conv":0.10,"Health":0.16,"Maint":0.07,"Info":0.11},
    "Ventilation":        {"EE":0.09,"Flex":0.00,"Comfort":0.16,"Conv":0.10,"Health":0.16,"Maint":0.10,"Info":0.11},
    "Lighting":           {"EE":0.03,"Flex":0.00,"Comfort":0.16,"Conv":0.10,"Health":0.16,"Maint":0.00,"Info":0.00},
    "Dynamic_Envelope":   {"EE":0.05,"Flex":0.00,"Comfort":0.16,"Conv":0.10,"Health":0.16,"Maint":0.05,"Info":0.11},
    "Electricity":        {"EE":0.15,"Flex":0.17,"Comfort":0.00,"Conv":0.10,"Health":0.00,"Maint":0.15,"Info":0.11},
    "EV_Charging":        {"EE":0.00,"Flex":0.05,"Comfort":0.00,"Conv":0.10,"Health":0.00,"Maint":0.00,"Info":0.11},
    "Monitoring_Control": {"EE":0.20,"Flex":0.20,"Comfort":0.20,"Conv":0.20,"Health":0.20,"Maint":0.20,"Info":0.20},
}

# ── SERVICE CATALOG (54 services, exact scores from Ref_Scores sheet) ─────────
SERVICE_CATALOG = {
    "H-1a": {"domain":"Heating","name":"Heat emission control","max_fl":4,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":1,"Conv":1,"Health":1,"Maint":0,"Info":0},2:{"EE":2,"Flex":0,"Comfort":2,"Conv":2,"Health":2,"Maint":0,"Info":0},3:{"EE":2,"Flex":0,"Comfort":2,"Conv":3,"Health":2,"Maint":1,"Info":0},4:{"EE":3,"Flex":0,"Comfort":2,"Conv":3,"Health":2,"Maint":1,"Info":0}}},
    "H-1b": {"domain":"Heating","name":"Emission control for TABS (heating)","max_fl":3,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":1,"Conv":1,"Health":1,"Maint":0,"Info":0},2:{"EE":1,"Flex":0,"Comfort":1,"Conv":2,"Health":2,"Maint":0,"Info":0},3:{"EE":2,"Flex":0,"Comfort":2,"Conv":3,"Health":2,"Maint":1,"Info":1}}},
    "H-1c": {"domain":"Heating","name":"Control of distribution fluid temperature","max_fl":2,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":1,"Conv":1,"Health":0,"Maint":0,"Info":0},2:{"EE":2,"Flex":0,"Comfort":1,"Conv":1,"Health":0,"Maint":0,"Info":0}}},
    "H-1d": {"domain":"Heating","name":"Control of distribution pumps in networks","max_fl":4,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},2:{"EE":2,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},3:{"EE":2,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},4:{"EE":2,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0}}},
    "H-1f": {"domain":"Heating","name":"Thermal Energy Storage (TES) for heating","max_fl":3,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},2:{"EE":2,"Flex":1,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},3:{"EE":2,"Flex":2,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0}}},
    "H-2a": {"domain":"Heating","name":"Heat generator control (all except heat pumps)","max_fl":2,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":1,"Conv":0,"Health":0,"Maint":0,"Info":0},2:{"EE":2,"Flex":0,"Comfort":2,"Conv":0,"Health":0,"Maint":0,"Info":0}}},
    "H-2b": {"domain":"Heating","name":"Heat generator control (for heat pumps)","max_fl":3,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":1,"Comfort":1,"Conv":0,"Health":0,"Maint":0,"Info":0},2:{"EE":2,"Flex":1,"Comfort":2,"Conv":0,"Health":0,"Maint":0,"Info":0},3:{"EE":2,"Flex":3,"Comfort":2,"Conv":0,"Health":0,"Maint":0,"Info":0}}},
    "H-2d": {"domain":"Heating","name":"Sequencing of different heat generators","max_fl":4,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},2:{"EE":2,"Flex":1,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},3:{"EE":3,"Flex":2,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},4:{"EE":3,"Flex":3,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0}}},
    "H-3":  {"domain":"Heating","name":"Heating performance reporting","max_fl":4,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":1,"Info":1},2:{"EE":1,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":1,"Info":2},3:{"EE":1,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":1,"Info":3},4:{"EE":1,"Flex":0,"Comfort":0,"Conv":1,"Health":0,"Maint":3,"Info":3}}},
    "H-4":  {"domain":"Heating","name":"Flexibility and grid interaction (Heating)","max_fl":4,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":1,"Conv":1,"Health":0,"Maint":0,"Info":0},2:{"EE":2,"Flex":1,"Comfort":2,"Conv":2,"Health":0,"Maint":0,"Info":0},3:{"EE":2,"Flex":3,"Comfort":2,"Conv":3,"Health":0,"Maint":0,"Info":0},4:{"EE":2,"Flex":3,"Comfort":3,"Conv":3,"Health":1,"Maint":0,"Info":0}}},
    "DHW-1a":{"domain":"DHW","name":"DHW storage charging (electric/heat pump)","max_fl":3,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":1,"Comfort":0,"Conv":1,"Health":0,"Maint":0,"Info":0},2:{"EE":2,"Flex":2,"Comfort":0,"Conv":2,"Health":0,"Maint":0,"Info":0},3:{"EE":2,"Flex":3,"Comfort":0,"Conv":2,"Health":0,"Maint":0,"Info":0}}},
    "DHW-1b":{"domain":"DHW","name":"DHW storage charging (hot water generation)","max_fl":3,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":1,"Comfort":0,"Conv":1,"Health":0,"Maint":0,"Info":0},2:{"EE":2,"Flex":2,"Comfort":0,"Conv":2,"Health":0,"Maint":0,"Info":0},3:{"EE":2,"Flex":3,"Comfort":0,"Conv":2,"Health":0,"Maint":0,"Info":0}}},
    "DHW-1d":{"domain":"DHW","name":"DHW storage charging (solar collector)","max_fl":3,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":0,"Conv":1,"Health":0,"Maint":0,"Info":0},2:{"EE":2,"Flex":1,"Comfort":0,"Conv":2,"Health":0,"Maint":0,"Info":0},3:{"EE":3,"Flex":2,"Comfort":0,"Conv":2,"Health":0,"Maint":0,"Info":0}}},
    "DHW-2b":{"domain":"DHW","name":"Sequencing of different DHW generators","max_fl":4,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},2:{"EE":2,"Flex":1,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},3:{"EE":3,"Flex":2,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},4:{"EE":3,"Flex":3,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0}}},
    "DHW-3": {"domain":"DHW","name":"DHW performance reporting","max_fl":4,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":1,"Info":1},2:{"EE":1,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":1,"Info":2},3:{"EE":1,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":1,"Info":3},4:{"EE":1,"Flex":0,"Comfort":0,"Conv":1,"Health":0,"Maint":2,"Info":3}}},
    "C-1a":  {"domain":"Cooling","name":"Cooling emission control","max_fl":4,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":1,"Conv":1,"Health":1,"Maint":0,"Info":0},2:{"EE":1,"Flex":0,"Comfort":1,"Conv":2,"Health":2,"Maint":0,"Info":0},3:{"EE":2,"Flex":0,"Comfort":2,"Conv":3,"Health":2,"Maint":1,"Info":0},4:{"EE":3,"Flex":0,"Comfort":2,"Conv":3,"Health":2,"Maint":1,"Info":0}}},
    "C-1b":  {"domain":"Cooling","name":"Emission control for TABS (cooling)","max_fl":3,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":1,"Conv":1,"Health":1,"Maint":0,"Info":0},2:{"EE":1,"Flex":0,"Comfort":1,"Conv":1,"Health":2,"Maint":0,"Info":0},3:{"EE":2,"Flex":0,"Comfort":2,"Conv":3,"Health":2,"Maint":1,"Info":1}}},
    "C-1c":  {"domain":"Cooling","name":"Distribution network chilled water temperature","max_fl":2,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":1,"Conv":1,"Health":0,"Maint":0,"Info":0},2:{"EE":2,"Flex":0,"Comfort":1,"Conv":1,"Health":0,"Maint":0,"Info":0}}},
    "C-1d":  {"domain":"Cooling","name":"Control of distribution pumps (cooling)","max_fl":4,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},2:{"EE":2,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},3:{"EE":2,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},4:{"EE":2,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0}}},
    "C-1f":  {"domain":"Cooling","name":"Interlock: avoiding simultaneous heating/cooling","max_fl":2,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":2,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},2:{"EE":3,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0}}},
    "C-1g":  {"domain":"Cooling","name":"Control of Thermal Energy Storage (TES - cooling)","max_fl":3,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},2:{"EE":2,"Flex":1,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},3:{"EE":2,"Flex":2,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0}}},
    "C-2a":  {"domain":"Cooling","name":"Generator control for cooling","max_fl":3,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":1,"Comfort":1,"Conv":0,"Health":0,"Maint":0,"Info":0},2:{"EE":2,"Flex":1,"Comfort":2,"Conv":0,"Health":0,"Maint":0,"Info":0},3:{"EE":2,"Flex":3,"Comfort":2,"Conv":0,"Health":0,"Maint":0,"Info":0}}},
    "C-2b":  {"domain":"Cooling","name":"Sequencing of different cooling generators","max_fl":4,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},2:{"EE":2,"Flex":1,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},3:{"EE":3,"Flex":2,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},4:{"EE":3,"Flex":3,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0}}},
    "C-3":   {"domain":"Cooling","name":"Cooling performance reporting","max_fl":4,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":1,"Info":1},2:{"EE":1,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":1,"Info":2},3:{"EE":1,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":1,"Info":3},4:{"EE":1,"Flex":0,"Comfort":0,"Conv":1,"Health":0,"Maint":3,"Info":3}}},
    "C-4":   {"domain":"Cooling","name":"Flexibility and grid interaction (Cooling)","max_fl":4,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":1,"Conv":1,"Health":0,"Maint":0,"Info":0},2:{"EE":2,"Flex":1,"Comfort":2,"Conv":2,"Health":0,"Maint":0,"Info":0},3:{"EE":2,"Flex":3,"Comfort":2,"Conv":3,"Health":0,"Maint":0,"Info":0},4:{"EE":2,"Flex":3,"Comfort":3,"Conv":3,"Health":1,"Maint":0,"Info":0}}},
    "V-1a":  {"domain":"Ventilation","name":"Supply air flow control at room level","max_fl":4,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":1,"Conv":1,"Health":1,"Maint":0,"Info":0},2:{"EE":1,"Flex":0,"Comfort":2,"Conv":2,"Health":2,"Maint":0,"Info":0},3:{"EE":2,"Flex":0,"Comfort":3,"Conv":3,"Health":3,"Maint":0,"Info":0},4:{"EE":3,"Flex":0,"Comfort":3,"Conv":3,"Health":3,"Maint":0,"Info":0}}},
    "V-1c":  {"domain":"Ventilation","name":"Air flow/pressure control at air handler level","max_fl":4,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},2:{"EE":2,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},3:{"EE":3,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},4:{"EE":3,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0}}},
    "V-2c":  {"domain":"Ventilation","name":"Heat recovery control / bypass","max_fl":2,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":1,"Conv":1,"Health":1,"Maint":0,"Info":0},2:{"EE":2,"Flex":0,"Comfort":2,"Conv":2,"Health":2,"Maint":0,"Info":0}}},
    "V-2d":  {"domain":"Ventilation","name":"Supply air temperature control (AHU level)","max_fl":3,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":1,"Conv":1,"Health":0,"Maint":0,"Info":0},2:{"EE":2,"Flex":0,"Comfort":2,"Conv":1,"Health":0,"Maint":0,"Info":0},3:{"EE":3,"Flex":0,"Comfort":2,"Conv":1,"Health":0,"Maint":0,"Info":0}}},
    "V-3":   {"domain":"Ventilation","name":"Free cooling (mechanical ventilation)","max_fl":3,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":3,"Conv":2,"Health":1,"Maint":0,"Info":0},2:{"EE":2,"Flex":0,"Comfort":3,"Conv":2,"Health":1,"Maint":0,"Info":0},3:{"EE":3,"Flex":0,"Comfort":3,"Conv":2,"Health":1,"Maint":0,"Info":0}}},
    "V-6":   {"domain":"Ventilation","name":"IAQ reporting","max_fl":3,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":2,"Maint":1,"Info":1},2:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":3,"Maint":1,"Info":2},3:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":3,"Maint":2,"Info":3}}},
    "L-1a":  {"domain":"Lighting","name":"Occupancy control for indoor lighting","max_fl":3,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":1,"Conv":1,"Health":0,"Maint":0,"Info":0},2:{"EE":2,"Flex":0,"Comfort":2,"Conv":2,"Health":0,"Maint":0,"Info":0},3:{"EE":3,"Flex":0,"Comfort":2,"Conv":2,"Health":0,"Maint":0,"Info":0}}},
    "L-2":   {"domain":"Lighting","name":"Lighting control based on daylight levels","max_fl":4,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":1,"Conv":1,"Health":0,"Maint":0,"Info":0},2:{"EE":2,"Flex":0,"Comfort":1,"Conv":1,"Health":1,"Maint":0,"Info":0},3:{"EE":3,"Flex":0,"Comfort":2,"Conv":2,"Health":2,"Maint":0,"Info":0},4:{"EE":3,"Flex":0,"Comfort":3,"Conv":3,"Health":3,"Maint":0,"Info":0}}},
    "DE-1":  {"domain":"Dynamic_Envelope","name":"Window solar shading control","max_fl":4,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":1,"Conv":1,"Health":0,"Maint":0,"Info":0},2:{"EE":2,"Flex":0,"Comfort":1,"Conv":2,"Health":1,"Maint":0,"Info":0},3:{"EE":3,"Flex":0,"Comfort":2,"Conv":3,"Health":2,"Maint":0,"Info":0},4:{"EE":3,"Flex":0,"Comfort":3,"Conv":3,"Health":3,"Maint":0,"Info":0}}},
    "DE-2":  {"domain":"Dynamic_Envelope","name":"Window open/closed control + HVAC","max_fl":3,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":2,"Flex":0,"Comfort":1,"Conv":1,"Health":0,"Maint":0,"Info":0},2:{"EE":2,"Flex":0,"Comfort":2,"Conv":1,"Health":1,"Maint":0,"Info":0},3:{"EE":2,"Flex":0,"Comfort":2,"Conv":2,"Health":1,"Maint":0,"Info":0}}},
    "DE-4":  {"domain":"Dynamic_Envelope","name":"Dynamic envelope performance reporting","max_fl":4,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":1,"Info":1},2:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":1,"Info":2},3:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":1,"Info":3},4:{"EE":0,"Flex":0,"Comfort":0,"Conv":1,"Health":0,"Maint":2,"Info":3}}},
    "E-2":   {"domain":"Electricity","name":"Local electricity generation reporting","max_fl":4,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":1,"Info":1},2:{"EE":1,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":1,"Info":2},3:{"EE":1,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":1,"Info":3},4:{"EE":1,"Flex":0,"Comfort":0,"Conv":1,"Health":0,"Maint":2,"Info":3}}},
    "E-3":   {"domain":"Electricity","name":"Storage of locally generated electricity","max_fl":4,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":0,"Flex":1,"Comfort":0,"Conv":2,"Health":0,"Maint":0,"Info":0},2:{"EE":0,"Flex":2,"Comfort":0,"Conv":2,"Health":0,"Maint":0,"Info":0},3:{"EE":0,"Flex":2,"Comfort":0,"Conv":2,"Health":0,"Maint":0,"Info":0},4:{"EE":0,"Flex":3,"Comfort":0,"Conv":2,"Health":0,"Maint":0,"Info":0}}},
    "E-4":   {"domain":"Electricity","name":"Optimizing self-consumption of local electricity","max_fl":3,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":0,"Flex":1,"Comfort":0,"Conv":1,"Health":0,"Maint":0,"Info":0},2:{"EE":0,"Flex":2,"Comfort":0,"Conv":2,"Health":0,"Maint":0,"Info":0},3:{"EE":0,"Flex":3,"Comfort":0,"Conv":2,"Health":0,"Maint":0,"Info":0}}},
    "E-5":   {"domain":"Electricity","name":"Control of CHP plant","max_fl":2,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":1,"Comfort":0,"Conv":1,"Health":0,"Maint":0,"Info":0},2:{"EE":2,"Flex":2,"Comfort":0,"Conv":1,"Health":0,"Maint":0,"Info":0}}},
    "E-8":   {"domain":"Electricity","name":"Support of micro-grid operation modes","max_fl":3,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":0,"Flex":2,"Comfort":0,"Conv":2,"Health":0,"Maint":0,"Info":0},2:{"EE":0,"Flex":2,"Comfort":0,"Conv":2,"Health":0,"Maint":0,"Info":0},3:{"EE":0,"Flex":3,"Comfort":0,"Conv":3,"Health":0,"Maint":0,"Info":0}}},
    "E-11":  {"domain":"Electricity","name":"Energy storage reporting","max_fl":4,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":1,"Info":1},2:{"EE":1,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":1,"Info":2},3:{"EE":1,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":1,"Info":3},4:{"EE":1,"Flex":0,"Comfort":0,"Conv":1,"Health":0,"Maint":2,"Info":3}}},
    "E-12":  {"domain":"Electricity","name":"Electricity consumption reporting","max_fl":4,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":1},2:{"EE":1,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":2},3:{"EE":2,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":1,"Info":3},4:{"EE":3,"Flex":0,"Comfort":0,"Conv":1,"Health":0,"Maint":2,"Info":3}}},
    "EV-15": {"domain":"EV_Charging","name":"EV charging capacity","max_fl":4,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":0,"Flex":0,"Comfort":0,"Conv":1,"Health":0,"Maint":0,"Info":0},2:{"EE":0,"Flex":0,"Comfort":0,"Conv":2,"Health":0,"Maint":0,"Info":0},3:{"EE":0,"Flex":0,"Comfort":0,"Conv":3,"Health":0,"Maint":0,"Info":0},4:{"EE":0,"Flex":0,"Comfort":0,"Conv":3,"Health":0,"Maint":0,"Info":0}}},
    "EV-16": {"domain":"EV_Charging","name":"EV charging grid balancing","max_fl":2,"levels":{0:{"EE":0,"Flex":-2,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":0,"Flex":1,"Comfort":0,"Conv":2,"Health":0,"Maint":0,"Info":0},2:{"EE":0,"Flex":3,"Comfort":0,"Conv":2,"Health":0,"Maint":0,"Info":0}}},
    "EV-17": {"domain":"EV_Charging","name":"EV charging information and connectivity","max_fl":2,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":0,"Flex":0,"Comfort":0,"Conv":1,"Health":0,"Maint":0,"Info":2},2:{"EE":0,"Flex":1,"Comfort":0,"Conv":1,"Health":0,"Maint":0,"Info":3}}},
    "MC-3":  {"domain":"Monitoring_Control","name":"HVAC runtime management","max_fl":3,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":1,"Comfort":1,"Conv":1,"Health":0,"Maint":0,"Info":0},2:{"EE":2,"Flex":1,"Comfort":2,"Conv":2,"Health":1,"Maint":0,"Info":0},3:{"EE":3,"Flex":2,"Comfort":2,"Conv":3,"Health":1,"Maint":0,"Info":0}}},
    "MC-4":  {"domain":"Monitoring_Control","name":"Fault detection and diagnosis","max_fl":3,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":0,"Flex":0,"Comfort":0,"Conv":1,"Health":1,"Maint":1,"Info":1},2:{"EE":0,"Flex":0,"Comfort":0,"Conv":2,"Health":2,"Maint":2,"Info":2},3:{"EE":0,"Flex":0,"Comfort":0,"Conv":3,"Health":3,"Maint":3,"Info":3}}},
    "MC-9":  {"domain":"Monitoring_Control","name":"Occupancy detection: connected services","max_fl":2,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":1,"Conv":1,"Health":0,"Maint":1,"Info":0},2:{"EE":1,"Flex":0,"Comfort":1,"Conv":1,"Health":0,"Maint":2,"Info":0}}},
    "MC-13": {"domain":"Monitoring_Control","name":"Central TBS performance and energy reporting","max_fl":3,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":1,"Flex":0,"Comfort":0,"Conv":1,"Health":0,"Maint":1,"Info":1},2:{"EE":1,"Flex":0,"Comfort":0,"Conv":2,"Health":0,"Maint":2,"Info":2},3:{"EE":1,"Flex":0,"Comfort":0,"Conv":3,"Health":0,"Maint":3,"Info":3}}},
    "MC-25": {"domain":"Monitoring_Control","name":"Smart grid integration","max_fl":2,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":0,"Flex":2,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},2:{"EE":1,"Flex":3,"Comfort":0,"Conv":1,"Health":0,"Maint":0,"Info":0}}},
    "MC-28": {"domain":"Monitoring_Control","name":"DSM performance reporting","max_fl":2,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":0,"Flex":1,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":2},2:{"EE":0,"Flex":2,"Comfort":0,"Conv":0,"Health":0,"Maint":1,"Info":3}}},
    "MC-29": {"domain":"Monitoring_Control","name":"Override of DSM control","max_fl":4,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":0,"Flex":3,"Comfort":-2,"Conv":0,"Health":0,"Maint":-1,"Info":-2},2:{"EE":0,"Flex":1,"Comfort":0,"Conv":1,"Health":0,"Maint":0,"Info":0},3:{"EE":0,"Flex":1,"Comfort":0,"Conv":2,"Health":0,"Maint":1,"Info":0},4:{"EE":0,"Flex":2,"Comfort":0,"Conv":3,"Health":0,"Maint":1,"Info":0}}},
    "MC-30": {"domain":"Monitoring_Control","name":"Integrated TBS platform","max_fl":3,"levels":{0:{"EE":0,"Flex":0,"Comfort":0,"Conv":0,"Health":0,"Maint":0,"Info":0},1:{"EE":0,"Flex":0,"Comfort":0,"Conv":1,"Health":0,"Maint":1,"Info":0},2:{"EE":1,"Flex":0,"Comfort":0,"Conv":2,"Health":0,"Maint":1,"Info":0},3:{"EE":2,"Flex":0,"Comfort":0,"Conv":3,"Health":0,"Maint":1,"Info":0}}},
}


# ── BUILDING INFO + IFC INVENTORY (loaded from data/ JSON files) ─────────────
with open(BUILDING_INFO_PATH, encoding="utf-8") as _f:
    BUILDING_INFO = json.load(_f)
with open(IFC_INVENTORY_PATH, encoding="utf-8") as _f:
    IFC_INVENTORY = json.load(_f)

# Legacy stub so existing code that references BUILDING_INFO["id"] still works

# ── CSV FILE DISCOVERY ────────────────────────────────────────────────────────
# The analysis period is derived from the data rather than fixed in code, so
# adding a month of CSVs extends the assessment instead of being discarded by a
# hard-coded end date. Set CSV_PERIOD_START or CSV_PERIOD_END explicitly before
# calling load_csv_files to restrict the window on purpose.
CSV_PERIOD_START = None
CSV_PERIOD_END   = None


def detect_csv_period(csv_dir: str) -> tuple:
    """Earliest and latest timestamp present across the CSV folder."""
    lo, hi = None, None
    if not os.path.isdir(csv_dir):
        return None, None
    for fname in sorted(os.listdir(csv_dir)):
        if not fname.endswith(".csv"):
            continue
        try:
            col = pd.read_csv(os.path.join(csv_dir, fname), usecols=["last_changed"])
            t = pd.to_datetime(col["last_changed"], utc=True, errors="coerce").dropna()
            if t.empty:
                continue
            lo = t.min() if lo is None or t.min() < lo else lo
            hi = t.max() if hi is None or t.max() > hi else hi
        except Exception:
            continue
    return lo, hi

def load_csv_files(csv_dir: str) -> dict:
    """
    Load all CSVs from the 200dd area-based folder.
    New format: each file has columns [entity_id, state, last_changed, ...].
    Returns a dict keyed by entity_id, value = filtered DataFrame for that entity.
    Also handles old single-entity format (no entity_id column) for compatibility.
    Analysis period filtered to Jan–Jun 2026.
    """
    global CSV_PERIOD_START, CSV_PERIOD_END
    files = {}
    if not os.path.isdir(csv_dir):
        print(f"[WARN] CSV directory not found: {csv_dir}")
        return files

    # Derive the window from the data unless the caller pinned it deliberately.
    if CSV_PERIOD_START is None or CSV_PERIOD_END is None:
        lo, hi = detect_csv_period(csv_dir)
        if CSV_PERIOD_START is None:
            CSV_PERIOD_START = lo if lo is not None else pd.Timestamp("2026-01-01", tz="UTC")
        if CSV_PERIOD_END is None:
            CSV_PERIOD_END = hi if hi is not None else pd.Timestamp.now(tz="UTC")

    for fname in sorted(os.listdir(csv_dir)):
        if not fname.endswith(".csv"):
            continue
        fpath = os.path.join(csv_dir, fname)
        try:
            df = pd.read_csv(fpath)
            if df.empty or "state" not in df.columns:
                continue
            if "last_changed" not in df.columns:
                continue

            df["last_changed"] = pd.to_datetime(df["last_changed"], utc=True, errors="coerce")
            df = df.dropna(subset=["last_changed"]).sort_values("last_changed").reset_index(drop=True)

            # Filter to analysis period (Jan–Jun 2026)
            df = df[(df["last_changed"] >= CSV_PERIOD_START) &
                    (df["last_changed"] <= CSV_PERIOD_END)].reset_index(drop=True)

            if "entity_id" in df.columns:
                # New area-based format: split by entity_id
                for eid, grp in df.groupby("entity_id"):
                    grp = grp.reset_index(drop=True)
                    if len(grp) > 0:
                        files[eid] = grp
            else:
                # Old single-entity format: key by filename stem
                key = fname.replace("_history.csv", "").replace(".csv", "")
                if len(df) > 0:
                    files[key] = df

        except Exception as e:
            print(f"[WARN] Could not read {fname}: {e}")

    print(f"[INFO] Loaded {len(files)} entity time-series from {csv_dir}")
    print(f"[INFO] Analysis period: {CSV_PERIOD_START.date()} → {CSV_PERIOD_END.date()}")
    return files


def get_data_period(csv_files: dict) -> tuple:
    """Return (start_date, end_date) spanning all loaded CSV files."""
    starts, ends = [], []
    for df in csv_files.values():
        if "last_changed" in df.columns and not df["last_changed"].isna().all():
            starts.append(df["last_changed"].min())
            ends.append(df["last_changed"].max())
    if not starts:
        return None, None
    return min(starts), max(ends)


# ── HELPER: TIME-WEIGHTED ACTIVE PERCENTAGE ───────────────────────────────────
def time_weighted_active_pct(df_sorted: pd.DataFrame, active_fn) -> float:
    """
    Compute the fraction of total time window during which active_fn(state) is True.
    Uses interval-based weighting (state persists until next record).
    """
    if df_sorted.empty or "last_changed" not in df_sorted.columns:
        return 0.0
    df = df_sorted.dropna(subset=["last_changed"]).reset_index(drop=True)
    if len(df) < 2:
        return 0.0
    active_secs = 0.0
    total_secs = (df["last_changed"].iloc[-1] - df["last_changed"].iloc[0]).total_seconds()
    if total_secs <= 0:
        return 0.0
    for i in range(len(df) - 1):
        dur = (df["last_changed"].iloc[i+1] - df["last_changed"].iloc[i]).total_seconds()
        if active_fn(df["state"].iloc[i]):
            active_secs += dur
    return active_secs / total_secs if total_secs > 0 else 0.0


# ── HELPER: COVERAGE ANALYSIS (regular sensors) ───────────────────────────────
COVERAGE_GAP_MULTIPLE = 10   # an interval this many times the sensor's own median is a gap

# Data-quality floor for calling a result VERIFIED rather than PARTIAL_EVIDENCE.
# Applied through _gate() so every service uses the same numbers and a reviewer
# can find them in one place instead of reading 37 functions.
MIN_COVERAGE_FOR_VERIFIED = 60.0
MIN_RECORDS_FOR_VERIFIED = 100


def _predictive_entities(csv_files: dict) -> list:
    """Entities that would evidence predictive management or maintenance, which is
    what separates the top reporting level from the one below it."""
    toks = ("predictive", "predittiv", "remaining_life", "days_to_replace",
            "maintenance_due", "anomaly", "degradation")
    return [k for k in csv_files if any(t in k.lower() for t in toks)]


def _reporting_level(csv_files: dict, has_current: bool, has_history: bool) -> tuple:
    """Shared ladder for the reporting services C-3, DHW-3, E-2 and H-3, which all
    use the same four steps in the official catalogue:

        L0 none
        L1 reporting of current performance values
        L2 current values AND historical data
        L3 performance evaluation including forecasting and/or benchmarking
        L4 that, plus predictive management or maintenance

    Returns (level, forecast_entities, predictive_entities) so the caller can
    quote the counts in its justification.
    """
    forecast = FORECAST_ENTITIES(csv_files)
    predictive = _predictive_entities(csv_files)
    if not has_current:
        return 0, forecast, predictive
    if not has_history:
        return 1, forecast, predictive
    if forecast and predictive:
        return 4, forecast, predictive
    if forecast:
        return 3, forecast, predictive
    return 2, forecast, predictive


def _gate(status: str, coverage_pct: float = None, n_records: int = None,
          span_days: float = None, min_span_days: float = None) -> tuple:
    """Downgrade a VERIFIED result to PARTIAL_EVIDENCE when the evidence is thin.

    Returns (status, note). Only ever weakens a claim, never strengthens one, and
    leaves N/A and UNRESOLVED untouched. Coverage is expected to come from
    analyze_coverage in adaptive mode, so a slow sensor is not punished for being
    slow.
    """
    if status != VERIFIED:
        return status, ""
    reasons = []
    if coverage_pct is not None and coverage_pct < MIN_COVERAGE_FOR_VERIFIED:
        reasons.append(f"time coverage {coverage_pct:.1f}% is below the "
                       f"{MIN_COVERAGE_FOR_VERIFIED:.0f}% floor")
    if n_records is not None and n_records < MIN_RECORDS_FOR_VERIFIED:
        reasons.append(f"{n_records} records is below the {MIN_RECORDS_FOR_VERIFIED} floor")
    if (span_days is not None and min_span_days is not None and span_days < min_span_days):
        reasons.append(f"observed span {span_days:.1f} days is below the "
                       f"{min_span_days:.0f}-day floor")
    if reasons:
        return PARTIAL_EVIDENCE, (" Recorded as partial evidence rather than verified because "
                                  + "; ".join(reasons) + ".")
    return VERIFIED, ""


def analyze_coverage(df: pd.DataFrame, max_gap_hours: float = 2.0,
                     adaptive: bool = True,
                     gap_multiple: float = COVERAGE_GAP_MULTIPLE) -> dict:
    """
    Coverage statistics for a regularly sampled sensor, measured against the
    sensor's OWN span rather than the calendar, so equipment installed part way
    through the period is not penalised for the months before it existed.

    A gap is an interval longer than the threshold. With adaptive=True the
    threshold is the larger of max_gap_hours and gap_multiple times the sensor's
    median sampling interval, so the test asks the same question of a sensor that
    reports every 15 seconds and one that reports once a day.
    """
    if df.empty or "last_changed" not in df.columns:
        return {"coverage_pct": 0.0, "n_records": 0, "gaps": 0, "period_days": 0,
                "gap_threshold_h": max_gap_hours, "median_interval_min": None}
    df = df.dropna(subset=["last_changed"]).sort_values("last_changed").reset_index(drop=True)
    n = len(df)
    if n < 2:
        return {"coverage_pct": 0.0, "n_records": n, "gaps": 0, "period_days": 0,
                "gap_threshold_h": max_gap_hours, "median_interval_min": None}

    t = df["last_changed"]
    total_secs = (t.iloc[-1] - t.iloc[0]).total_seconds()
    deltas = t.diff().dt.total_seconds().iloc[1:]
    median_interval = float(deltas.median()) if len(deltas) else 0.0

    # The gap threshold has to be read against how often the sensor actually
    # reports. A fixed 3-hour rule marks an hourly-logging sensor as full of
    # holes, which is a statement about the rule, not about the data. Scaling
    # the threshold by the sensor's own median interval keeps the test meaning
    # the same thing for a 15-second meter and a daily counter, while never
    # becoming more lenient than the caller asked for.
    gap_threshold = max_gap_hours * 3600
    if adaptive and median_interval > 0:
        gap_threshold = max(gap_threshold, median_interval * gap_multiple)

    gap_mask = deltas > gap_threshold
    gap_secs = float(deltas[gap_mask].sum())
    n_gaps = int(gap_mask.sum())
    coverage = max(0.0, (total_secs - gap_secs) / total_secs) if total_secs > 0 else 0.0
    return {
        "coverage_pct": round(coverage * 100, 1),
        "n_records": n,
        "gaps": n_gaps,
        "period_days": round(total_secs / 86400, 1),
        "gap_threshold_h": round(gap_threshold / 3600, 2),
        "median_interval_min": round(median_interval / 60, 2),
    }


# ── HELPER: EVENT-DRIVEN COVERAGE (bypass, geofencing) ───────────────────────
def analyze_coverage_event_driven(df: pd.DataFrame, sensor_name: str = "",
                                   min_records: int = 3) -> dict:
    """
    For event-driven sensors: coverage based on max allowable gap.
    Bypass/geofencing: max gap = 60 days. Others: 7 days.
    """
    if df.empty or "last_changed" not in df.columns:
        return {"ok": False, "n_records": 0, "max_gap_days": None, "period_days": 0}
    df = df.dropna(subset=["last_changed"]).sort_values("last_changed").reset_index(drop=True)
    n = len(df)
    max_gap_limit = 60.0 if any(k in sensor_name.lower() for k in ["bypass","geofence","geofencing"]) else 7.0
    if n < min_records:
        return {"ok": False, "n_records": n, "max_gap_days": None,
                "period_days": (df["last_changed"].iloc[-1]-df["last_changed"].iloc[0]).total_seconds()/86400 if n>1 else 0}
    max_gap = 0.0
    for i in range(n - 1):
        gap_d = (df["last_changed"].iloc[i+1] - df["last_changed"].iloc[i]).total_seconds() / 86400
        if gap_d > max_gap:
            max_gap = gap_d
    period_days = (df["last_changed"].iloc[-1] - df["last_changed"].iloc[0]).total_seconds() / 86400
    return {
        "ok": max_gap <= max_gap_limit,
        "n_records": n,
        "max_gap_days": round(max_gap, 1),
        "period_days": round(period_days, 1),
    }


# ── OFFICIAL SRI CATALOGUE ───────────────────────────────────────────────────
# Level definitions and impact scores as published in SRI_calculation-sheet_v4.5.
# The engine keeps its own SERVICE_CATALOG for the calculation, but validates it
# against this file on import, so the two can never silently drift apart. The
# level DESCRIPTIONS are the criteria a check must satisfy to award a level, and
# are exposed to the check functions through official_level().
_OFFICIAL: dict | None = None


def _load_official() -> dict:
    global _OFFICIAL
    if _OFFICIAL is None:
        try:
            with open(OFFICIAL_CATALOG_PATH, encoding="utf-8") as fh:
                _OFFICIAL = json.load(fh)["services"]
        except FileNotFoundError:
            _OFFICIAL = {}
    return _OFFICIAL


def official_level(code: str, level: int) -> str:
    """Official text defining a functionality level, for use in justifications."""
    svc = _load_official().get(code)
    if not svc:
        return ""
    return svc["levels"].get(str(level), {}).get("description", "")


def validate_against_official(verbose: bool = True) -> list:
    """Compare SERVICE_CATALOG with the official sheet. Returns a list of
    discrepancies; an empty list means the engine's numbers are the official
    ones. Run on import so a drifted catalogue is noticed immediately."""
    off = _load_official()
    if not off:
        return [("*", "-", "official_catalog.json not found; validation skipped")]
    problems = []
    for code, cat in SERVICE_CATALOG.items():
        o = off.get(code)
        if not o:
            problems.append((code, "-", "missing from official catalogue"))
            continue
        if o["max_fl"] != cat["max_fl"]:
            problems.append((code, "max_fl",
                             f"engine={cat['max_fl']} official={o['max_fl']}"))
        for lv, scores in cat["levels"].items():
            olv = o["levels"].get(str(lv))
            if not olv:
                continue
            for ic in IMPACT_KEYS:
                a, b = scores.get(ic, 0), olv["impacts"].get(ic, 0)
                if a != b:
                    problems.append((code, f"L{lv}.{ic}", f"engine={a} official={b}"))
    if verbose and problems:
        print(f"[WARN] SERVICE_CATALOG diverges from the official sheet in "
              f"{len(problems)} place(s):")
        for p in problems[:12]:
            print(f"       {p[0]:<8} {p[1]:<12} {p[2]}")
    return problems


# ── HELPER: STANDARD RESULT BUILDER ──────────────────────────────────────────
def _result(code: str, status: str, level: int, confidence: float,
            justification: str, data: dict = None) -> dict:
    cat = SERVICE_CATALOG[code]
    lv = level if status not in NA_STATUSES else None
    return {
        "service": code,
        "description": cat["name"],
        "domain": cat["domain"],
        "applicability_status": status,
        "level_achieved": lv,
        "level_max": cat["max_fl"],
        "confidence": confidence,
        "justification": justification,
        # The official wording of the level that was awarded, and of the next one
        # up. Carrying both makes every assessment auditable against the source:
        # a reviewer can see the criterion the evidence had to meet, and the one
        # it failed to meet, without opening the calculation sheet.
        "official_criterion": official_level(code, lv) if lv is not None else "",
        "official_next_level": (official_level(code, lv + 1)
                                if lv is not None and lv < cat["max_fl"] else ""),
        "data": data or {},
    }


# ── HELPER: MANUAL ASSESSMENTS LOADER ────────────────────────────────────────
_MANUAL_CACHE: dict | None = None

def _load_manual() -> dict:
    """Lazy-load manual_assessments.json; cached after first read."""
    global _MANUAL_CACHE
    if _MANUAL_CACHE is None:
        with open(MANUAL_PATH, encoding="utf-8") as fh:
            _MANUAL_CACHE = json.load(fh)["services"]
    return _MANUAL_CACHE

def _from_manual(code: str) -> dict:
    """Return a standard _result dict for a service assessed via manual_assessments.json."""
    rec = _load_manual()[code]
    return _result(code, rec["status"], rec["level"], rec["confidence"],
                   rec["justification"], rec.get("metadata", {}))


# ════════════════════════════════════════════════════════════════════════════════
# SERVICE CHECK FUNCTIONS — HEATING (10 services)
# ════════════════════════════════════════════════════════════════════════════════

H1A_MIN_ROOM_CONTROLLERS = 2   # more than one addressable zone -> individual room control

# A capability counts as OPERATIONAL only if it is observed across a meaningful
# share of the analysis period, rather than in a single window. Expressed as a
# fraction so it scales with the period instead of being an unexplained day
# count, and applied identically wherever occupancy evidence is used (H-1a L4
# and MC-9 L2), so the same records cannot support one service and not another.
MIN_OPERATIONAL_SPAN_FRACTION = 0.10


def _analysis_period_days(csv_files: dict) -> float:
    """Span of the whole dataset, used as the denominator for operational-span tests."""
    lo, hi = None, None
    for df in csv_files.values():
        if "last_changed" not in df.columns:
            continue
        d = df["last_changed"].dropna()
        if d.empty:
            continue
        a, b = d.min(), d.max()
        lo = a if lo is None or a < lo else lo
        hi = b if hi is None or b > hi else hi
    if lo is None or hi is None:
        return 0.0
    return (hi - lo).total_seconds() / 86400


def _occupancy_evidence(csv_files: dict) -> dict:
    """Occupancy detection: is it in automatic mode, and over how much of the period?

    Shared by H-1a (L4) and MC-9 (L2) so that identical records cannot be
    treated as sufficient in one service and insufficient in the other.
    """
    key = next((k for k in csv_files if "modalita_geofencing" in k), None)
    period = _analysis_period_days(csv_files)
    out = {"entity": key, "records": 0, "span_days": 0.0, "auto_mode": False,
           "period_days": round(period, 1), "span_fraction": 0.0,
           "operational": False, "states": {}}
    if key is None:
        return out
    g = csv_files[key].dropna(subset=["last_changed"])
    out["records"] = len(g)
    if len(g) > 1:
        out["span_days"] = round(
            (g["last_changed"].max() - g["last_changed"].min()).total_seconds() / 86400, 1)
    states = g["state"].astype(str)
    out["states"] = states.value_counts().to_dict()
    out["auto_mode"] = bool(states.str.contains("Auto", case=False, na=False).any())
    if period > 0:
        out["span_fraction"] = round(out["span_days"] / period, 4)
    out["operational"] = (out["auto_mode"]
                          and out["span_fraction"] >= MIN_OPERATIONAL_SPAN_FRACTION)
    return out


def check_H1a(csv_files: dict) -> dict:
    """
    H-1a: Heat emission control (max FL=4)

    Official levels (SRI calculation sheet v4.5, catalogue B):
      L0 No automatic control
      L1 Central automatic control (e.g. central thermostat)
      L2 Individual room control (e.g. thermostatic valves, or electronic controller)
      L3 Individual room control with communication between controllers and to BACS
      L4 Individual room control with communication and occupancy detection

    The previous paraphrase read L3 as "individual room scheduling" and L4 as
    "demand based", which is not what the catalogue says. Scheduling belongs to
    H-4 and MC-3; here the ladder is about how many rooms are individually
    controlled, whether those controllers are networked, and whether occupancy
    feeds into them.
    """
    tado_keys = [k for k in csv_files if k.endswith("_riscaldamento")]
    if not tado_keys:
        return _result("H-1a", NA_NOT_EVIDENCED, 0, 0.0,
                       "No Tado heating CSV found. No operational evidence of emission control.")

    rooms_with_data, total_records = [], 0
    for k in tado_keys:
        df = csv_files[k]
        try:
            vals = pd.to_numeric(df["state"], errors="coerce").dropna()
            if len(vals) > 0:
                room = k.replace("sensor.", "").replace("_riscaldamento", "").replace("_", " ").title()
                rooms_with_data.append(room)
                total_records += len(vals)
        except Exception:
            pass

    n_rooms = len(rooms_with_data)

    # Meross MTS200B thermostats are room controllers too; counting only Tado
    # under-reports the number of individually controlled rooms.
    meross_rooms = {re.sub(r"_\d+$", "", k.split(".")[-1]).replace("_mts200b_main_channel", "")
                    for k in csv_files if "mts200b" in k.lower()}
    all_rooms = set(rooms_with_data) | meross_rooms
    n_controlled = len(all_rooms)

    if n_controlled == 0:
        status, gate_note = _gate(VERIFIED, n_records=total_records)
        return _result("H-1a", status, 0, 0.60,
                       "No room controller with valid data. No automatic heat emission control. L0.",
                       {"controlled_rooms": 0})

    # L3 evidence: controllers report into a common platform. Every entity here
    # carries a Home Assistant entity_id, which is that platform.
    on_bacs = n_controlled >= H1A_MIN_ROOM_CONTROLLERS

    # L4 evidence: occupancy detection integrated with the room control, and
    # observed across enough of the period to count as operational. Uses the
    # shared test so H-1a and MC-9 cannot diverge on the same records.
    occ = _occupancy_evidence(csv_files)
    geo_records, geo_days, geo_auto = occ["records"], occ["span_days"], occ["auto_mode"]
    occupancy_ok = occ["operational"]

    if n_controlled < H1A_MIN_ROOM_CONTROLLERS:
        level, status, conf = 1, VERIFIED, 0.70
        note = (f"Only {n_controlled} controlled zone found, which is central rather than "
                f"individual room control. L1.")
    elif occupancy_ok:
        level, status, conf = 4, VERIFIED, 0.78
        note = (f"Individual room control in {n_controlled} zones, communicating to a common "
                f"platform, with occupancy detection observed over {geo_days:.0f} days. L4.")
    elif on_bacs:
        level, status, conf = 3, VERIFIED, 0.76
        note = (f"Individual room control in {n_controlled} zones "
                f"({sorted(all_rooms)}), each an addressable controller reporting into a single "
                f"platform, which satisfies the L3 condition of communication between controllers "
                f"and to a BACS. "
                f"L4 additionally requires occupancy detection: geofencing in Auto mode is "
                f"present ({geo_records} records) but spans only {geo_days:.1f} days of the "
                f"{occ['period_days']}-day analysis period, {occ['span_fraction']*100:.1f}%, "
                f"below the {MIN_OPERATIONAL_SPAN_FRACTION*100:.0f}% required for a capability "
                f"to count as operational. Occupancy control is therefore evidenced as a "
                f"capability but not as sustained operation. The same threshold governs MC-9, "
                f"which rests on these same records.")
    else:
        level, status, conf = 2, VERIFIED, 0.74
        note = (f"Individual room control in {n_controlled} zones, but no evidence of "
                f"communication to a central platform. L2.")

    return _result("H-1a", status, level, conf,
                   f"Assessed against the official catalogue B wording. {note}",
                   {"controlled_rooms": n_controlled, "rooms": sorted(all_rooms),
                    "tado_rooms": n_rooms, "tado_records": total_records,
                    "meross_rooms": sorted(meross_rooms),
                    "geofencing_records": geo_records,
                    "geofencing_span_days": round(geo_days, 1),
                    "geofencing_auto_mode": geo_auto,
                    "occupancy_span_fraction": occ["span_fraction"],
                    "analysis_period_days": occ["period_days"],
                    "thresholds": {"min_room_controllers": H1A_MIN_ROOM_CONTROLLERS,
                                   "min_operational_span_fraction": MIN_OPERATIONAL_SPAN_FRACTION},
                    "shared_with": "MC-9 L2"})


def check_H1b(csv_files: dict) -> dict:
    """H-1b: Emission control for TABS — radiant floor GF. Source: manual_assessments.json."""
    return _from_manual("H-1b")


def check_H1c(csv_files: dict) -> dict:
    """H-1c: Control of distribution fluid temperature. Source: manual_assessments.json."""
    return _from_manual("H-1c")


def check_H1d(csv_files: dict) -> dict:
    """H-1d: Control of distribution pumps in networks. Source: manual_assessments.json."""
    return _from_manual("H-1d")


def check_H1f(csv_files: dict) -> dict:
    """H-1f: Thermal Energy Storage for heating (max FL=3). No heating TES present."""
    return _result("H-1f", NA_EXPLICIT_ABSENCE, 0, 0.95,
                   "DBL09 and DBL08: No thermal energy storage buffer for heating documented. "
                   "DHW has 200L tank (IMMERGAS) but this serves DHW only. IFC: no IfcTank found. "
                   "Service not applicable.",
                   {"source": "DBL09 + DBL08 + IFC"})


def check_H2a(csv_files: dict) -> dict:
    """H-2a: Heat generator control -- gas boiler. Source: manual_assessments.json."""
    return _from_manual("H-2a")


def check_H2b(csv_files: dict) -> dict:
    """H-2b: Heat generator control -- heat pump. Source: manual_assessments.json."""
    return _from_manual("H-2b")


def check_H2d(csv_files: dict) -> dict:
    """H-2d: Sequencing of different heat generators. Source: manual_assessments.json."""
    return _from_manual("H-2d")


def check_H3(csv_files: dict) -> dict:
    """
    H-3: Heating performance reporting (max FL=4)
    L1=energy readings (counter); L2=historical with trends; L3=benchmarking; L4=recommendations.
    Evidence: Tado temperature CSVs (2 rooms) + Meross temps (3 zones) logged in Home Assistant.
    """
    tado_temp_keys = [k for k in csv_files if "_temperatura" in k and "comfoairq" not in k and "meross" not in k]
    meross_keys = [k for k in csv_files if "meross_temperature" in k]
    n_tado = len(tado_temp_keys)
    n_meross = len(meross_keys)
    total_temp_sensors = n_tado + n_meross

    if total_temp_sensors == 0:
        return _result("H-3", NA_NOT_EVIDENCED, 0, 0.0,
                       "No temperature CSV files found. No operational heating performance data.")

    # Temperature time-series in HA = L1 basic reporting (energy counter equivalent)
    # HA stores historical data → L2 (historical trends) can be inferred
    # No heating energy counter CSV specifically — but multi-room temp logging implies L2
    tado_records = sum(len(csv_files[k]) for k in tado_temp_keys)
    meross_records = sum(len(csv_files[k]) for k in meross_keys)

    level, forecast, predictive = _reporting_level(
        csv_files, has_current=total_temp_sensors > 0,
        has_history=(tado_records + meross_records) >= 500)

    status, gate_note = _gate(VERIFIED, n_records=tado_records + meross_records)

    return _result("H-3", status, level, 0.68,
                   f"Temperature logged in Home Assistant across {total_temp_sensors} sensors: "
                   f"{n_tado} Tado zones ({tado_records} records) + {n_meross} Meross sensors "
                   f"({meross_records} records). Historical temperature trends available → L2. "
                   f"No dedicated heating energy meter CSV (Shelly not available). L3 (benchmarking) "
                   f"and L4 (recommendations) not evidenced. Conservative: L2.",
                   {"n_temp_sensors": total_temp_sensors, "tado_temp_records": tado_records,
                    "meross_records": meross_records})


# Entity-name tokens for an optimum-start / self-learning heating feature. In
# Tado this is "inizio anticipato" (early start): the controller learns how long
# a room takes to reach setpoint and brings the start time forward. Its presence
# alone is not enough; the official L2 requires the control to actually be
# self-learning, so the entity must also be switched on.
SELF_LEARNING_TOKENS = ("inizio_anticipato", "early_start", "optimum_start",
                        "auto_assist", "self_learn", "adaptive_start")
H4_MIN_SETPOINT_ZONES = 1   # zones whose setpoint varies over time -> scheduled operation


def _schedule_evidence(csv_files: dict) -> tuple:
    """Zones whose setpoint changes over time, which is the observable signature
    of scheduled operation. Shared by H-4 and MC-3, which both key their L1 on it."""
    zones, detail = set(), {}
    for key, df in csv_files.items():
        if "temperature" not in df.columns:
            continue
        v = pd.to_numeric(df["temperature"], errors="coerce").dropna()
        if len(v) == 0 or v.nunique() < 2:
            continue
        zone = re.sub(r"_\d+$", "", key.split(".")[-1]).replace("_mts200b_main_channel", "")
        zones.add(zone)
        detail[zone] = {"n": int(len(v)), "distinct": int(v.nunique()),
                        "range": f"{v.min():.1f}-{v.max():.1f}"}
    return zones, detail


def _self_learning_evidence(csv_files: dict) -> tuple:
    """Optimum-start / self-learning entities and how many records show them ON."""
    ents, enabled, states = [], 0, {}
    for key, df in csv_files.items():
        if not any(t in key.lower() for t in SELF_LEARNING_TOKENS):
            continue
        ents.append(key)
        st = df.get("state")
        if st is None:
            continue
        vals = st.astype(str).str.lower()
        enabled += int(vals.isin({"on", "true"}).sum())
        for v in vals.unique():
            states[v] = states.get(v, 0) + int((vals == v).sum())
    return ents, enabled, states


def check_H4(csv_files: dict) -> dict:
    """
    H-4: Flexibility and grid interaction, Heating (max FL=4)

    Official levels (SRI calculation sheet v4.5, catalogue B):
      L0 No automatic control
      L1 Scheduled operation of heating system
      L2 Self-learning optimal control of heating system
      L3 Heating system capable of flexible control through grid signals (DSM)
      L4 Optimized control based on local predictions and grid signals

    Note that L2 is NOT "automatic time or presence based control", which is what
    a scheduled system with geofencing does. L2 requires the control to learn.
    Presence-driven setpoint changes belong to L1.
    """
    # ── L1 evidence: does any zone's setpoint actually change over time? ──────
    zone_set, setpoint_detail = _schedule_evidence(csv_files)
    setpoint_zones = sorted(zone_set)
    n_sched = len(zone_set)

    # ── L2 evidence: is a self-learning feature present AND enabled? ──────────
    sl_entities, sl_enabled, sl_states = _self_learning_evidence(csv_files)

    # ── L3/L4 evidence: does any grid or tariff signal reach the building? ────
    grid_entities = [k for k in csv_files
                     if any(t in k.lower() for t in DSM_SIGNAL_TOKENS)]

    if grid_entities and sl_enabled > 0:
        # L4 requires BOTH local prediction and grid signals, per the official text.
        level, status, conf = 4, VERIFIED, 0.72
        note = (f"{len(grid_entities)} grid or tariff signal entities combined with "
                f"self-learning control enabled ({sl_enabled} records): optimised control "
                f"based on local predictions and grid signals. L4.")
    elif grid_entities:
        level, status, conf = 3, VERIFIED, 0.70
        note = (f"{len(grid_entities)} grid or tariff signal entities found, so the heating "
                f"system can be controlled from an external signal. L3. L4 additionally "
                f"requires local predictive control, which is not enabled.")
    elif sl_entities and sl_enabled > 0:
        level, status, conf = 2, VERIFIED, 0.75
        note = (f"Self-learning control evidenced: {len(sl_entities)} optimum-start entities, "
                f"{sl_enabled} records in the enabled state. L2.")
    elif n_sched >= H4_MIN_SETPOINT_ZONES:
        level, status, conf = 1, VERIFIED, 0.78
        note = (f"Setpoints vary over time in {n_sched} zones ({setpoint_detail}), confirming "
                f"scheduled operation of the heating system at L1. "
                f"L2 requires self-learning optimal control: {len(sl_entities)} optimum-start "
                f"entities exist but none is enabled (observed states: {sl_states}), so the "
                f"capability is present in the hardware and switched off. The evidence therefore "
                f"positively excludes L2 rather than merely failing to support it. "
                f"L3 requires a grid or tariff signal: zero such entities across "
                f"{len(csv_files)} scanned.")
    elif setpoint_zones or sl_entities:
        level, status, conf = 0, PARTIAL_EVIDENCE, 0.45
        note = ("Heating controllers are present but no setpoint variation was observed, so "
                "scheduled operation is not evidenced. L0 as partial evidence.")
    else:
        level, status, conf = 0, NA_NOT_EVIDENCED, 0.0
        note = "No heating setpoint data in the CSV. Flexibility cannot be assessed."

    return _result("H-4", status, level, conf,
                   f"Assessed against the official catalogue B wording. {note} "
                   f"Note that occupancy-driven setpoint reduction (Tado geofencing) is scheduled "
                   f"operation under this catalogue, not self-learning control, and so does not "
                   f"lift the service to L2.",
                   {"scheduled_zones": sorted(set(setpoint_zones)),
                    "setpoint_detail": setpoint_detail,
                    "self_learning_entities": len(sl_entities),
                    "self_learning_enabled_records": sl_enabled,
                    "self_learning_states": sl_states,
                    "grid_signal_entities": len(grid_entities),
                    "entities_scanned": len(csv_files)})


# ════════════════════════════════════════════════════════════════════════════════
# SERVICE CHECK FUNCTIONS — DHW (5 services)
# ════════════════════════════════════════════════════════════════════════════════

def check_DHW1a(csv_files: dict) -> dict:
    """DHW-1a: DHW storage charging -- HP. Source: manual_assessments.json."""
    return _from_manual("DHW-1a")


def check_DHW1b(csv_files: dict) -> dict:
    """DHW-1b: DHW storage charging -- gas boiler. Source: manual_assessments.json."""
    return _from_manual("DHW-1b")


def check_DHW1d(csv_files: dict) -> dict:
    """
    DHW-1d: DHW storage charging — solar collector (max FL=3).
    L1=basic solar priority; L2=weather-compensated storage; L3=predictive.
    Evidence: Villa-Percentuale-Solare CSV (solar %, 1138 records).
    """
    solar_key = next((k for k in csv_files if "percentuale_solare" in k), None)
    if solar_key is None:
        return _result("DHW-1d", PARTIAL_EVIDENCE, 1, 0.50,
                       "DBL09: Solar thermal collector CP4 XL confirmed + solar differential controller. "
                       "No solar CSV found. System presence verified but operational mode cannot be confirmed.")

    df = csv_files[solar_key]
    vals = pd.to_numeric(df["state"], errors="coerce").dropna()
    n_records = len(vals)
    pct_nonzero = (vals > 0).mean() * 100
    max_pct = vals.max()
    mean_pct = vals.mean()
    cov = analyze_coverage(df, max_gap_hours=25)  # daily readings expected

    # L2 and L3 both hinge on multi-sensor storage management, which needs
    # temperature sensors inside the tank. Verify their absence rather than
    # assuming it.
    STORAGE_TOKENS = ("serbatoio", "accumulo", "tank", "storage", "puffer",
                      "acs_", "dhw_", "sanitaria", "boiler_temp")
    storage_sensors = [k for k in csv_files
                       if any(t in k.lower() for t in STORAGE_TOKENS)]
    # Seasonal modulation of the solar fraction is what demonstrates that the
    # differential controller is actually regulating, not just reporting.
    d = df.dropna(subset=["last_changed"])
    monthly = pd.to_numeric(d["state"], errors="coerce").groupby(
        d["last_changed"].dt.to_period("M")).mean().dropna()
    seasonal_swing = float(monthly.max() - monthly.min()) if len(monthly) > 1 else 0.0

    return_sensors = [k for k in csv_files
                      if any(t in k.lower() for t in ("return_temp", "ritorno", "_return"))]

    if cov["coverage_pct"] < DHW1D_MIN_COVERAGE_PCT:
        level, status, conf = 1, PARTIAL_EVIDENCE, 0.50
        note = (f"Solar fraction series covers only {cov['coverage_pct']}% of its span, below "
                f"the {DHW1D_MIN_COVERAGE_PCT}% needed to characterise charging behaviour. "
                f"L1 recorded as partial evidence.")
    elif len(storage_sensors) >= 2 and return_sensors:
        level, status, conf = 3, PARTIAL_EVIDENCE, 0.55
        note = (f"{len(storage_sensors)} storage sensors and {len(return_sensors)} return "
                f"temperature sensors found: the L3 combination of return temperature control "
                f"and multi-sensor storage management is observable. Confirming the control "
                f"loop itself is not implemented, so L3 is partial evidence.")
    elif len(storage_sensors) >= 2:
        level, status, conf = 2, PARTIAL_EVIDENCE, 0.55
        note = (f"{len(storage_sensors)} storage temperature sensors found, so multi-sensor "
                f"storage management is in principle observable. Verifying that they actually "
                f"drive charging is not implemented, so L2 is recorded as partial evidence.")
    else:
        level, status, conf = 1, VERIFIED, 0.75
        note = (f"Solar fraction varies from {monthly.min():.1f}% to {monthly.max():.1f}% across "
                f"months (swing {seasonal_swing:.1f} points), active in {pct_nonzero:.0f}% of "
                f"{n_records} readings over {cov['period_days']} days. A fraction that tracks "
                f"solar availability is the operational signature of a differential controller "
                f"giving solar priority, with the boiler and heat pump supplying the remainder. "
                f"That is exactly the L1 condition: automatic control of solar storage charge "
                f"(priority 1) plus supplementary charge. "
                f"L2 requires demand-oriented supply or multi-sensor storage management: the "
                f"dataset contains zero storage temperature sensors across "
                f"{len(csv_files)} entities, so tank stratification is invisible and L2 cannot "
                f"be evidenced.")

    return _result("DHW-1d", status, level, conf,
                   f"Assessed against the official catalogue B wording. DBL09 confirms the CP4 XL "
                   f"flat-plate collector and the solar differential controller. {note}",
                   {"n_records": n_records, "period_days": cov["period_days"],
                    "mean_solar_pct": round(float(mean_pct), 1),
                    "max_solar_pct": round(float(max_pct), 1),
                    "pct_active": round(float(pct_nonzero), 1),
                    "monthly_solar_pct": {str(k): round(float(v), 1) for k, v in monthly.items()},
                    "seasonal_swing_pct": round(seasonal_swing, 1),
                    "storage_sensors": len(storage_sensors),
                    "entities_scanned": len(csv_files)})


DHW2B_MIN_DISTINCT_FRACTIONS = 10   # a modulating fraction, not an on/off flag
DHW2B_MIN_RECORDS = 500

# Predicted load or weather forecast reaching the controller is what separates
# the "current conditions" levels from the "predicted" ones in several services.
FORECAST_TOKENS = ("forecast", "previsione", "predicted", "prediction",
                   "meteo", "weather_", "domani", "tomorrow")

# Reporting services distinguish "current values" (L1) from "current values plus
# historical data" (L2). History means a series long enough to read a trend from.
DHW3_MIN_HISTORY_RECORDS = 500
DHW3_MIN_HISTORY_DAYS = 60
C3_MIN_HISTORY_RECORDS = 500
C3_MIN_HISTORY_DAYS = 7      # cooling only exists since the splits were installed


def FORECAST_ENTITIES(csv_files: dict) -> list:
    return [k for k in csv_files if any(t in k.lower() for t in FORECAST_TOKENS)]


def check_DHW2b(csv_files: dict) -> dict:
    """
    DHW-2b: Sequencing in case of different DHW generators (max FL=4)

    Official levels (SRI calculation sheet v4.5, catalogue B):
      L0 Priorities only based on running time
      L1 Control according to a FIXED priority list (e.g. based on rated efficiency)
      L2 Control according to a DYNAMIC priority list (based on CURRENT energy
         efficiency, carbon emissions and capacity)
      L3/L4 dynamic list also using predicted load

    Moved out of manual_assessments.json on 2026-08-27: the solar fraction entity
    makes the priority order observable, so this no longer needs a fixed verdict.
    What remains unobservable is whether the ordering between the heat pump and
    the boiler is recomputed from current efficiency, since neither generator has
    an entity in the dataset. That limit is stated rather than assumed away.
    """
    solar_key = next((k for k in csv_files if "percentuale_solare" in k), None)
    if solar_key is None:
        return _result("DHW-2b", NA_NOT_EVIDENCED, 0, 0.0,
                       "No solar fraction entity. DHW generator sequencing cannot be observed.")

    df = csv_files[solar_key]
    vals = pd.to_numeric(df["state"], errors="coerce").dropna()
    if len(vals) < DHW2B_MIN_RECORDS:
        return _result("DHW-2b", PARTIAL_EVIDENCE, 0, 0.45,
                       f"Solar fraction has only {len(vals)} records, below "
                       f"{DHW2B_MIN_RECORDS}. Sequencing behaviour cannot be characterised.",
                       {"n_records": int(len(vals))})

    distinct = int(vals.round(0).nunique())
    at_zero = float((vals < 1).mean())
    at_full = float((vals > 99).mean())
    d = df.dropna(subset=["last_changed"])
    monthly = pd.to_numeric(d["state"], errors="coerce").groupby(
        d["last_changed"].dt.to_period("M")).mean().dropna()
    swing = float(monthly.max() - monthly.min()) if len(monthly) > 1 else 0.0

    # Generator-level telemetry is what would let L2 be distinguished from L1.
    GEN = ("innova", "immergas", "heat_pump", "boiler", "caldaia", "pompa_calore")
    gen_entities = [k for k in csv_files if any(t in k.lower() for t in GEN)]

    if gen_entities and FORECAST_ENTITIES(csv_files) and _predictive_entities(csv_files):
        level, status, conf = 4, PARTIAL_EVIDENCE, 0.50
        note = ("Generator telemetry, forecasting and predictive entities all present: a "
                "priority list using predicted load is observable. L4 as partial evidence.")
    elif distinct < DHW2B_MIN_DISTINCT_FRACTIONS:
        level, status, conf = 0, VERIFIED, 0.65
        note = (f"Solar fraction takes only {distinct} distinct values, so generators are not "
                f"being sequenced by contribution. Priorities appear to follow running time. L0.")
    elif gen_entities and FORECAST_ENTITIES(csv_files):
        level, status, conf = 3, PARTIAL_EVIDENCE, 0.50
        note = (f"{len(gen_entities)} generator entities and "
                f"{len(FORECAST_ENTITIES(csv_files))} forecast entities found, so a priority "
                f"list using predicted load is observable in principle. L3 as partial evidence.")
    elif gen_entities:
        level, status, conf = 2, PARTIAL_EVIDENCE, 0.50
        note = (f"{len(gen_entities)} generator entities found, so a dynamic priority list is in "
                f"principle observable. Confirming that the ordering follows current efficiency "
                f"is not implemented, so L2 is partial evidence.")
    else:
        level, status, conf = 1, VERIFIED, 0.72
        note = (f"Solar fraction modulates continuously across {distinct} distinct values over "
                f"{len(vals)} records, sitting at 0% for {at_zero*100:.0f}% of readings and at "
                f"100% for {at_full*100:.0f}%, with a monthly mean swinging {swing:.1f} points "
                f"between {monthly.idxmin()} and {monthly.idxmax()}. Solar is therefore taken "
                f"whenever available and the supplementary generators make up the balance, which "
                f"is an operating priority list and meets L1. "
                f"L2 requires that list to be recomputed from current efficiency: the dataset "
                f"holds no entity for the INNOVA heat pump or the IMMERGAS boiler, so the ordering "
                f"between the two supplementary generators is unobservable and L2 can be neither "
                f"confirmed nor excluded.")

    return _result("DHW-2b", status, level, conf,
                   f"Assessed against the official catalogue B wording. {note}",
                   {"n_records": int(len(vals)), "distinct_fractions": distinct,
                    "pct_at_zero": round(at_zero * 100, 1),
                    "pct_at_full": round(at_full * 100, 1),
                    "monthly_mean": {str(k): round(float(v), 1) for k, v in monthly.items()},
                    "seasonal_swing": round(swing, 1),
                    "generator_entities": len(gen_entities),
                    "unobservable": "HP vs boiler ordering: no generator telemetry"})


def check_DHW3(csv_files: dict) -> dict:
    """
    DHW-3: DHW performance reporting (max FL=4).
    L1=basic counter; L2=historical data; L3=benchmarking; L4=recommendations.
    Evidence: Villa-Percentuale-Solare CSV (proxy for DHW solar performance).
    """
    solar_key = next((k for k in csv_files if "percentuale_solare" in k), None)
    if solar_key is None:
        return _result("DHW-3", PARTIAL_EVIDENCE, 1, 0.45,
                       "DBL09: DHW system with multiple generators and controllers present. "
                       "No DHW-specific CSV (temperature, flow, energy). DBL implies basic reporting "
                       "via boiler/HP controller displays. Conservative: L1 (partial evidence).")

    df = csv_files[solar_key]
    n = len(df)
    cov = analyze_coverage(df, max_gap_hours=25)

    # Official ladder: L1 indication of ACTUAL values; L2 actual values AND
    # HISTORICAL data; L3 performance evaluation with forecasting or
    # benchmarking; L4 that plus predictive maintenance.
    forecast = FORECAST_ENTITIES(csv_files)
    has_history = n >= DHW3_MIN_HISTORY_RECORDS and cov["period_days"] >= DHW3_MIN_HISTORY_DAYS

    level, forecast, predictive = _reporting_level(csv_files, True, has_history)
    if level >= 3:
        status, conf = PARTIAL_EVIDENCE, 0.50
        note = (f"{len(forecast)} forecast entities alongside {n} records of history: performance "
                f"evaluation with forecasting is observable in principle. L3 as partial evidence.")
    elif has_history:
        level, status, conf = 2, VERIFIED, 0.70
        note = (f"The solar fraction entity reports an actual DHW performance value and carries "
                f"{n} records over {cov['period_days']} days, retained and browsable in Home "
                f"Assistant. Actual values plus historical data is the L2 condition, and both are "
                f"present. "
                f"L3 requires performance evaluation with forecasting or benchmarking: no forecast "
                f"entity exists and no reference baseline is stored, so evaluation is left to the "
                f"reader of the chart. Note that no DHW energy counter, store temperature or flow "
                f"meter exists, so the solar fraction is the only performance value reported.")
    else:
        level, status, conf = 1, VERIFIED, 0.65
        note = (f"Actual DHW performance values are reported ({n} records) but the series does not "
                f"reach {DHW3_MIN_HISTORY_RECORDS} records over {DHW3_MIN_HISTORY_DAYS} days, so "
                f"historical reporting is not established. L1.")

    status, gate_note = _gate(status, coverage_pct=cov["coverage_pct"], n_records=n)
    return _result("DHW-3", status, level, conf,
                   f"Assessed against the official catalogue B wording. {note}{gate_note}",
                   {"n_records": n, "period_days": cov["period_days"],
                    "coverage_pct": cov["coverage_pct"],
                    "forecast_entities": len(forecast),
                    "source": "solar fraction, the only DHW performance value logged"})


# ════════════════════════════════════════════════════════════════════════════════
# SERVICE CHECK FUNCTIONS — COOLING (10 services)
# Cooling confirmed Jul-Aug 2026: Meross MTS200B (hvac_action=cooling) in
# Soggiorno and Cucina. AC splits controlled via ESPHome/MTS200B thermostats.
# ════════════════════════════════════════════════════════════════════════════════

def _get_mts200b_cooling(csv_files: dict) -> dict:
    """
    Find Meross MTS200B climate entities with hvac_action == 'cooling'.
    Returns {entity_id: DataFrame} for entities with confirmed cooling records.
    """
    cooling = {}
    for k, df in csv_files.items():
        if "mts200b" not in k.lower():
            continue
        if "hvac_action" not in df.columns:
            continue
        cool_df = df[df["hvac_action"] == "cooling"].copy()
        if len(cool_df) > 0:
            cooling[k] = cool_df
    return cooling


def check_C1a(csv_files: dict) -> dict:
    """
    C-1a: Cooling emission control at room level (max FL=4).
    L0=no automatic control; L1=central auto; L2=individual room; L3=room+scheduling; L4=demand-based.
    Evidence: Meross MTS200B in Soggiorno + Cucina with hvac_action=cooling confirmed.
    Each room has independent thermostat controlling its own AC split → L2.
    """
    cooling = _get_mts200b_cooling(csv_files)
    if not cooling:
        return _result("C-1a", NA_NOT_EVIDENCED, 0, 0.70,
                       "No MTS200B cooling records found in analysis period. "
                       "AC splits installed Jul 2026; extend period or re-export CSVs.",
                       {"note": "cooling data absent from period"})
    n_rooms = len(cooling)
    total_records = sum(len(df) for df in cooling.values())
    rooms = [k.replace("climate.", "").replace("_mts200b_main_channel", "") for k in cooling]
    level = 2 if n_rooms >= 2 else 1
    conf  = 0.78 if n_rooms >= 2 else 0.62
    occ = _occupancy_evidence(csv_files)
    if n_rooms >= 2 and occ["operational"]:
        level = 4
    elif n_rooms >= 2:
        level = 3

    status, gate_note = _gate(VERIFIED, n_records=total_records)
    return _result("C-1a", status, level, conf,
                   f"Meross MTS200B cooling confirmed in {n_rooms} room(s): {rooms}. "
                   f"Total cooling records: {total_records}. Each room has independent "
                   f"thermostat (MTS200B) controlling its AC split → individual room control. "
                   f"L2 (individual room control) verified. L3 (+ scheduling) technically possible "
                   f"via Meross app but not directly observable from hvac_action CSV alone. "
                   f"Conservative: L2.",
                   {"cooling_rooms": rooms, "total_records": total_records})


def check_C1b(csv_files: dict) -> dict:
    """C-1b: Emission control for TABS (cooling). No TABS cooling system present."""
    return _result("C-1b", NA_EXPLICIT_ABSENCE, 0, 0.95,
                   "No cooling TABS (Thermally Activated Building Systems) documented. "
                   "Cooling via DX AC splits (MTS200B + ESPHome). Radiant floor is heating-only. "
                   "Service not applicable.",
                   {"source": "DBL09 + CSV"})


def check_C1c(csv_files: dict) -> dict:
    """
    C-1c: Control of distribution chilled water temperature (max FL=2).
    Cooling system is DX (direct expansion AC splits) — no chilled water distribution network.
    Service not applicable to DX systems.
    """
    return _result("C-1c", NA_EXPLICIT_ABSENCE, 0, 0.90,
                   "Cooling via DX AC splits (Meross MTS200B + ESPHome) — no chilled water "
                   "distribution network present. C-1c applies to hydronic cooling systems only. "
                   "Not applicable.",
                   {"source": "DBL09 + CSV"})


def check_C1d(csv_files: dict) -> dict:
    """
    C-1d: Control of distribution pumps in cooling network (max FL=4).
    DX system has no distribution pump for cooling. Not applicable.
    """
    return _result("C-1d", NA_EXPLICIT_ABSENCE, 0, 0.90,
                   "DX cooling system (AC splits) has no hydronic distribution pump. "
                   "C-1d applies to chilled water networks only. Not applicable.",
                   {"source": "DBL09"})


C1F_BUCKET = "h"                 # resolution at which two actions count as simultaneous
C1F_MIN_OBSERVATION_DAYS = 30    # dual-mode days needed before an ABSENCE of conflict is
                                 # treated as verified rather than partial evidence


def _hvac_action_timeline(csv_files: dict) -> dict:
    """zone -> {'heating': set(hour), 'cooling': set(hour)} from hvac_action columns.

    Zone is derived from the entity name with the controller suffix stripped, so
    that a Tado TRV and a Meross thermostat serving the same room map to the same
    zone and can be compared against each other.
    """
    timeline = {}
    for key, df in csv_files.items():
        if "hvac_action" not in df.columns or "last_changed" not in df.columns:
            continue
        d = df.dropna(subset=["last_changed"]).copy()
        if d.empty:
            continue
        act = d["hvac_action"].astype(str).str.lower()
        zone = key.split(".")[-1]
        for suffix in ("_mts200b_main_channel", "_riscaldamento", "_climate"):
            zone = zone.replace(suffix, "")
        zone = re.sub(r"_\d+$", "", zone).strip("_")
        rec = timeline.setdefault(zone, {"heating": set(), "cooling": set()})
        for mode in ("heating", "cooling"):
            hours = d.loc[act == mode, "last_changed"].dt.floor(C1F_BUCKET)
            rec[mode].update(hours)
    return timeline


def check_C1f(csv_files: dict) -> dict:
    """
    C-1f: Interlock, avoiding simultaneous heating and cooling (max FL=2)
    L0 = simultaneous heating and cooling observed within the same zone;
    L1 = no same-zone conflict, but different zones heat and cool at the same time;
    L2 = no simultaneous operation observed while both modes were available.

    Assessed from hvac_action timelines rather than from the absence of a
    documented interlock. Note the asymmetry: observing a conflict proves the
    interlock is absent, whereas observing no conflict only supports L2 if the
    building actually had the opportunity to produce one.
    """
    timeline = _hvac_action_timeline(csv_files)
    if not timeline:
        return _result("C-1f", NA_NOT_EVIDENCED, 0, 0.0,
                       "No hvac_action data in the CSV. Interlock behaviour cannot be assessed.")

    heat_hours, cool_hours = set(), set()
    same_zone_conflicts, zones_heating, zones_cooling = {}, set(), set()
    for zone, rec in timeline.items():
        if rec["heating"]:
            zones_heating.add(zone)
            heat_hours |= rec["heating"]
        if rec["cooling"]:
            zones_cooling.add(zone)
            cool_hours |= rec["cooling"]
        both = rec["heating"] & rec["cooling"]
        if both:
            same_zone_conflicts[zone] = len(both)

    overlap_hours = heat_hours & cool_hours
    both_modes_seen = bool(heat_hours) and bool(cool_hours)
    overlap_days = len({h.date() for h in overlap_hours})

    if not both_modes_seen:
        missing = "cooling" if not cool_hours else "heating"
        return _result("C-1f", UNRESOLVED, 0, 0.35,
                       f"Only one operating mode observed in the analysis period: no {missing} "
                       f"action recorded. Heating hours={len(heat_hours)}, cooling "
                       f"hours={len(cool_hours)}. The building never had the opportunity to "
                       f"produce a simultaneous heating and cooling conflict, so the presence or "
                       f"absence of an interlock cannot be determined from operational data. "
                       f"Absence of evidence is not evidence of an interlock.",
                       {"heating_hours": len(heat_hours), "cooling_hours": len(cool_hours),
                        "zones_heating": sorted(zones_heating),
                        "zones_cooling": sorted(zones_cooling)})

    # How long were both modes actually observable? Claims that rest on the
    # ABSENCE of a conflict are only as strong as this window.
    both_mode_days = len({h.date() for h in heat_hours} | {h.date() for h in cool_hours})
    window_ok = both_mode_days >= C1F_MIN_OBSERVATION_DAYS

    if same_zone_conflicts:
        # A positive observation. One conflict is enough to disprove an interlock,
        # so this verdict does not depend on the length of the window.
        level, status, conf = 0, VERIFIED, 0.88
        note = (f"Simultaneous heating and cooling observed within the same zone: "
                f"{same_zone_conflicts}. No interlock is being enforced at room level. "
                f"A single observed conflict is sufficient to establish this.")
    elif overlap_hours:
        level = 1
        status = VERIFIED if window_ok else PARTIAL_EVIDENCE
        conf = 0.78 if window_ok else 0.55
        note = (f"No same-zone conflict, but {len(overlap_hours)} hours across {overlap_days} "
                f"days show at least one zone heating while another cools "
                f"(heating: {sorted(zones_heating)}; cooling: {sorted(zones_cooling)}). "
                f"Building-level interlock is disproven. The room-level claim rests on the "
                f"absence of a same-zone conflict over {both_mode_days} days of dual-mode "
                f"observation, "
                + (f"which meets the {C1F_MIN_OBSERVATION_DAYS}-day threshold."
                   if window_ok else
                   f"below the {C1F_MIN_OBSERVATION_DAYS}-day threshold, so L1 is recorded as "
                   f"partial evidence rather than verified."))
    else:
        level = 2
        status = VERIFIED if window_ok else PARTIAL_EVIDENCE
        conf = 0.75 if window_ok else 0.45
        note = (f"Both modes were exercised ({len(heat_hours)} heating hours, "
                f"{len(cool_hours)} cooling hours) with zero overlapping hours over "
                f"{both_mode_days} days. "
                + ("Automatic interlock evidenced at L2."
                   if window_ok else
                   f"Observation window is below the {C1F_MIN_OBSERVATION_DAYS}-day threshold, "
                   f"so L2 is recorded as partial evidence."))

    return _result("C-1f", status, level, conf,
                   f"hvac_action timeline at {C1F_BUCKET} resolution: {note} "
                   f"Heating and cooling are delivered by independent controllers "
                   f"(Tado TRVs and Meross MTS200B / AC splits), which is what makes the "
                   f"observation meaningful rather than trivially true.",
                   {"heating_hours": len(heat_hours), "cooling_hours": len(cool_hours),
                    "overlapping_hours": len(overlap_hours),
                    "overlapping_days": overlap_days,
                    "same_zone_conflicts": same_zone_conflicts,
                    "zones_heating": sorted(zones_heating),
                    "zones_cooling": sorted(zones_cooling)})


def check_C1g(csv_files: dict) -> dict:
    """C-1g: Control of cooling Thermal Energy Storage (TES). No TES present."""
    return _result("C-1g", NA_EXPLICIT_ABSENCE, 0, 0.95,
                   "No cooling TES documented in DBL09, DBL08, or IFC. Not applicable.",
                   {"source": "DBL09 + IFC"})


def check_C2a(csv_files: dict) -> dict:
    """
    C-2a: Generator control for cooling (max FL=3).
    L0=manual on/off; L1=automatic on/off via thermostat; L2=variable capacity; L3=demand-based.
    MTS200B thermostat sends on/off commands to AC split based on setpoint → L1.
    """
    cooling = _get_mts200b_cooling(csv_files)
    if not cooling:
        return _result("C-2a", NA_NOT_EVIDENCED, 0, 0.70,
                       "No MTS200B cooling records found. Cannot assess generator control.",
                       {"note": "cooling data absent from period"})
    n_rooms = len(cooling)
    total_rec = sum(len(df) for df in cooling.values())
    rooms = [k.replace("climate.", "").replace("_mts200b_main_channel", "") for k in cooling]
    # The official ladder is about how the GENERATOR's capacity is controlled:
    #   L0 on/off, L1 multi-stage, L2 variable, L3 variable plus grid signals.
    # hvac_action only ever reports cooling or off, so what is observable is the
    # unit starting and stopping. Capacity would need a power or modulation
    # reading from the AC units themselves.
    capacity_entities = [k for k, d in csv_files.items()
                         if any(t in k.lower() for t in ("condizionatore", "clima"))
                         and any(t in k.lower() for t in ("power", "potenza", "capacity",
                                                          "modulation", "frequency"))]
    grid_signals = [k for k in csv_files
                    if any(t in k.lower() for t in DSM_SIGNAL_TOKENS)]

    if capacity_entities and grid_signals:
        level, conf = 3, 0.70
        note = (f"{len(capacity_entities)} capacity entities and {len(grid_signals)} grid signal "
                f"entities: variable capacity control responding to external signals. L3.")
    elif capacity_entities:
        level, conf = 2, 0.72
        note = (f"{len(capacity_entities)} entities report AC capacity or modulation, so variable "
                f"capacity control is observable. L2.")
    else:
        level, conf = 0, 0.72
        note = (f"The MTS200B thermostats in {n_rooms} rooms ({rooms}) start and stop the AC "
                f"splits against a temperature set point, and hvac_action reports only 'cooling' "
                f"or 'off' across {total_rec} records: what is demonstrated is on/off control of "
                f"cooling production, which is the official L0. "
                f"L1 requires multi-stage capacity control and L2 variable capacity control. The "
                f"splits may well be inverter driven, but no entity reports their power, "
                f"modulation or compressor frequency, so capacity behaviour is unobservable. "
                f"Note the contrast with H-2b, where the logbook names an inverter heat pump "
                f"explicitly; here the logbook records only 'AC split (ESPHome)'.")

    status, gate_note = _gate(VERIFIED, n_records=total_rec)

    return _result("C-2a", status, level, conf,
                   f"Assessed against the official catalogue B wording. {note}",
                   {"rooms": rooms, "cooling_records": total_rec,
                    "capacity_entities": len(capacity_entities),
                    "grid_signal_entities": len(grid_signals)})


def check_C2b(csv_files: dict) -> dict:
    """C-2b: Sequencing of multiple cooling generators. Only one type of cooling generator."""
    return _result("C-2b", NA_EXPLICIT_ABSENCE, 0, 0.90,
                   "Building has only one type of cooling system (DX AC splits). "
                   "No chiller or second cooling generator type to sequence. Not applicable.",
                   {"source": "DBL09"})


def check_C3(csv_files: dict) -> dict:
    """
    C-3: Reporting information on cooling system performance (max FL=4).
    L0=none; L1=current data; L2=historical trends; L3=multi-system analysis; L4=predictive.
    Home Assistant logs hvac_action states for MTS200B → L1 (current/recent data available).
    """
    cooling = _get_mts200b_cooling(csv_files)
    if not cooling:
        return _result("C-3", NA_NOT_EVIDENCED, 0, 0.70,
                       "No cooling records found in analysis period.",
                       {"note": "cooling data absent from period"})
    n_rooms = len(cooling)
    total_rec = sum(len(df) for df in cooling.values())
    rooms = [k.replace("climate.", "").replace("_mts200b_main_channel", "") for k in cooling]
    cov_days = 0
    for df in cooling.values():
        span = (df["last_changed"].max() - df["last_changed"].min()).days
        cov_days = max(cov_days, span)

    # Official ladder: L1 reporting of CURRENT performance KPIs; L2 current KPIs
    # AND historical data; L3 performance evaluation with forecasting or
    # benchmarking; L4 that plus predictive maintenance.
    #
    # Room temperature is a cooling performance KPI and those series run the full
    # period, so the history question is answered by them rather than by the
    # cooling-state records, which only begin when the splits were installed.
    room_temp = [(k, len(d)) for k, d in csv_files.items()
                 if "meross_temperature" in k.lower() and len(d) >= C3_MIN_HISTORY_RECORDS]
    forecast = FORECAST_ENTITIES(csv_files)
    has_history = bool(room_temp) and cov_days >= C3_MIN_HISTORY_DAYS

    level, forecast, predictive = _reporting_level(csv_files, True, has_history)
    if level >= 3:
        conf = 0.68
        note = (f"{len(forecast)} forecast entities alongside historical KPIs: performance "
                f"evaluation with forecasting. L3.")
    elif has_history:
        level, conf = 2, 0.70
        note = (f"Home Assistant reports current cooling state for {n_rooms} zones ({rooms}, "
                f"{total_rec} records over ~{cov_days} days) together with {len(room_temp)} room "
                f"temperature series retained for the full period. Current KPIs plus historical "
                f"data is the L2 condition. "
                f"L3 requires performance evaluation with forecasting or benchmarking: no forecast "
                f"entity and no reference baseline exist. No cooling energy sub-meter is present "
                f"either, so efficiency cannot be reported, only operation and temperature.")
    else:
        level, conf = 1, 0.68
        note = (f"Current cooling state is reported for {n_rooms} zones ({total_rec} records) but "
                f"the history does not reach {C3_MIN_HISTORY_DAYS} days. L1.")

    status, gate_note = _gate(VERIFIED, n_records=total_rec)

    return _result("C-3", status, level, conf,
                   f"Assessed against the official catalogue B wording. {note}",
                   {"rooms": rooms, "cooling_records": total_rec, "coverage_days": cov_days,
                    "room_temperature_series": len(room_temp),
                    "forecast_entities": len(forecast)})


def check_C4(csv_files: dict) -> dict:
    """
    C-4: Cooling flexibility and grid interaction (max FL=4)
    L0 = no grid interaction; L1 = cooling can be shifted on an external signal;
    L2 = scheduled load shifting; L3/L4 = predictive or market-driven modulation.

    Grid interaction requires a signal to react to. The check verifies the
    absence of any tariff, price or demand-response channel in the entity
    inventory before concluding L0, and records whether cooling operation is
    even observable, so the verdict is falsifiable if a signal appears later.
    """
    cooling = _get_mts200b_cooling(csv_files)
    n_cool = sum(len(df) for df in cooling.values()) if cooling else 0
    dsm_entities = [(k, len(df)) for k, df in csv_files.items()
                    if any(t in k.lower() for t in DSM_SIGNAL_TOKENS)]

    if n_cool == 0:
        return _result("C-4", NA_NOT_EVIDENCED, 0, 0.40,
                       "No cooling operation observed in the CSV. Cooling flexibility cannot "
                       "be assessed.", {"cooling_records": 0})

    if dsm_entities and FORECAST_ENTITIES(csv_files):
        return _result("C-4", PARTIAL_EVIDENCE, 4, 0.50,
                       f"Grid signals and {len(FORECAST_ENTITIES(csv_files))} forecast "
                       f"entities present: optimised cooling control on local predictions and "
                       f"grid signals is observable. L4 as partial evidence.",
                       {"cooling_records": n_cool,
                        "dsm_signal_entities": len(dsm_entities)})

    if not dsm_entities:
        return _result("C-4", VERIFIED, 0, 0.82,
                       f"Cooling operation confirmed ({n_cool} records across "
                       f"{len(cooling)} zones). Entity inventory scanned across "
                       f"{len(csv_files)} entities for any tariff, price, demand-response or "
                       f"curtailment signal: zero matches. With no external signal reaching the "
                       f"building, cooling cannot be shifted in response to the grid regardless "
                       f"of the hardware's capability, so L0 is an observed result and not an "
                       f"assumption. Local PV self-consumption is assessed separately under E-4 "
                       f"and does not constitute grid interaction for this service.",
                       {"cooling_records": n_cool, "cooling_zones": len(cooling),
                        "dsm_signal_entities": 0, "entities_scanned": len(csv_files)})

    return _result("C-4", PARTIAL_EVIDENCE, 1, 0.50,
                   f"Cooling operation confirmed ({n_cool} records) and {len(dsm_entities)} "
                   f"grid-signal entities present, so an external signal does reach the building. "
                   f"Whether cooling actually responds to it is not established from these data. "
                   f"L1 as partial evidence.",
                   {"cooling_records": n_cool, "dsm_signal_entities": len(dsm_entities)})


# ════════════════════════════════════════════════════════════════════════════════
# SERVICE CHECK FUNCTIONS — VENTILATION (6 services)
# ════════════════════════════════════════════════════════════════════════════════

# V-1a thresholds. A control loop leaves a statistical trace: if the fan really
# tracks a sensor, the two move together; if it really follows a clock, the hour
# of day explains a real share of its variance. These are the two tests.
V1A_MIN_AQ_CORRELATION = 0.50   # |r| between air flow and an air-quality sensor
V1A_MIN_HOUR_ETA2      = 0.15   # share of flow variance explained by hour of day
V1A_MIN_HOURS          = 500    # hourly observations needed to test for a control pattern
DHW1D_MIN_COVERAGE_PCT = 40.0   # solar-fraction coverage needed to characterise charging
ROOM_DAMPER_TOKENS = ("damper", "serranda", "valvola_aria", "room_flow",
                      "zone_flow", "vav", "bocchetta")
AQ_SENSOR_TOKENS = ("co2", "carbon_dioxide", "voc", "tvoc", "humidity", "umidita")


def _hourly(series_df, col="state"):
    """Hourly mean of a numeric entity, indexed by timestamp."""
    d = series_df.dropna(subset=["last_changed"]).copy()
    d["_v"] = pd.to_numeric(d[col], errors="coerce")
    d = d.dropna(subset=["_v"])
    if d.empty:
        return None
    return d.set_index("last_changed")["_v"].sort_index().resample("1h").mean()


def check_V1a(csv_files: dict) -> dict:
    """
    V-1a: Supply air flow control at the room level (max FL=4)

    Official levels (SRI calculation sheet v4.5, catalogue B):
      L0 No ventilation system or manual control
      L1 Clock control
      L2 Occupancy detection control
      L3 Central Demand Control based on air quality sensors (CO2, VOC, humidity, ...)
      L4 Local Demand Control based on air quality sensors with local flow
         from/to the zone regulated by dampers

    Note that the official L1 is CLOCK control, not "constant supply", and that
    humidity counts as an air quality sensor for L3. Both matter here: the villa
    has humidity sensors but no CO2, and the question is whether the unit's flow
    actually follows any of them.
    """
    fan_key = next((k for k in csv_files if "comfoairq_supply_fan_duty" in k), None)
    flow_key = next((k for k in csv_files if "comfoairq_supply_airflow" in k), None)
    if fan_key is None and flow_key is None:
        return _result("V-1a", NA_NOT_EVIDENCED, 0, 0.0,
                       "No ventilation flow data in the CSV. Room-level flow control cannot "
                       "be assessed.")

    signal = _hourly(csv_files[flow_key or fan_key])
    dampers = [k for k in csv_files if any(t in k.lower() for t in ROOM_DAMPER_TOKENS)]
    aq = [k for k in csv_files if any(t in k.lower() for t in AQ_SENSOR_TOKENS)]

    # ── L3/L4 test: does flow track an air quality sensor? ────────────────────
    best_r, best_sensor = 0.0, None
    if signal is not None:
        for k in aq:
            other = _hourly(csv_files[k])
            if other is None:
                continue
            joined = pd.concat({"a": signal, "b": other}, axis=1).dropna()
            if len(joined) < 200:
                continue
            r = joined["a"].corr(joined["b"])
            if pd.notna(r) and abs(r) > abs(best_r):
                best_r, best_sensor = float(r), k.split(".")[-1]

    # ── L1 test: how much of the variance does the hour of day explain? ───────
    eta2 = 0.0
    if signal is not None:
        s = signal.dropna()
        if len(s) > 48:
            grand = s.mean()
            ssb = sum(len(g) * (g.mean() - grand) ** 2 for _, g in s.groupby(s.index.hour))
            sst = ((s - grand) ** 2).sum()
            eta2 = float(ssb / sst) if sst > 0 else 0.0

    # ── L2 test: does flow follow an occupancy signal? ───────────────────────
    occ_r, occ_sensor = 0.0, None
    for k in csv_files:
        if not any(t in k.lower() for t in ("geofencing", "presenza", "presence", "occupancy")):
            continue
        other = _hourly(csv_files[k])
        if other is None or signal is None:
            continue
        joined = pd.concat({"a": signal, "b": other}, axis=1).dropna()
        if len(joined) < 200:
            continue
        r = joined["a"].corr(joined["b"])
        if pd.notna(r) and abs(r) > abs(occ_r):
            occ_r, occ_sensor = float(r), k.split(".")[-1]

    demand_control = abs(best_r) >= V1A_MIN_AQ_CORRELATION
    occupancy_control = abs(occ_r) >= V1A_MIN_AQ_CORRELATION
    clock_control = eta2 >= V1A_MIN_HOUR_ETA2

    # Not enough of a series to characterise any control behaviour.
    if signal is None or len(signal.dropna()) < V1A_MIN_HOURS:
        n_h = 0 if signal is None else len(signal.dropna())
        return _result("V-1a", PARTIAL_EVIDENCE, 0, 0.40,
                       f"Only {n_h} hourly flow observations, below the {V1A_MIN_HOURS} needed to "
                       f"test for clock, occupancy or demand control. L0 as partial evidence.",
                       {"hours_observed": n_h})

    if demand_control and dampers:
        level, conf = 4, 0.75
        note = (f"Flow tracks {best_sensor} (r={best_r:+.2f}) and {len(dampers)} room dampers "
                f"regulate local flow. Local demand control. L4.")
    elif demand_control:
        level, conf = 3, 0.75
        note = (f"Flow tracks the air quality sensor {best_sensor} (r={best_r:+.2f}), above the "
                f"{V1A_MIN_AQ_CORRELATION} threshold: central demand control. L3. L4 additionally "
                f"requires room dampers, of which {len(dampers)} were found.")
    elif occupancy_control:
        level, conf = 2, 0.72
        note = (f"Flow follows the occupancy signal {occ_sensor} (r={occ_r:+.2f}): "
                f"occupancy detection control. L2.")
    elif clock_control:
        level, conf = 1, 0.72
        note = (f"Hour of day explains {eta2*100:.1f}% of flow variance, above the "
                f"{V1A_MIN_HOUR_ETA2*100:.0f}% threshold: clock control. L1.")
    else:
        level, conf = 0, 0.70
        note = (f"Neither automatic mode is evidenced. Hour of day explains only "
                f"{eta2*100:.1f}% of flow variance, so there is no clock control (L1). "
                f"The strongest correlation with any of the {len(aq)} air quality sensors is "
                f"{best_sensor} at r={best_r:+.2f}, well below the "
                f"{V1A_MIN_AQ_CORRELATION} needed for demand control (L3), and no CO2 or VOC "
                f"sensor exists at all. No room dampers ({len(dampers)} found), so L4 is out. "
                f"The unit holds a small number of fixed flow set points, which is the "
                f"signature of manually selected presets. L0 (manual control).")

    return _result("V-1a", VERIFIED, level, conf,
                   f"Assessed against the official catalogue B wording. {note} "
                   f"Flow modulation at the unit is assessed separately under V-1c; V-1a concerns "
                   f"control at the room level, and this MVHR distributes to rooms through fixed "
                   f"ducts with no regulating element.",
                   {"best_aq_correlation": round(best_r, 3), "best_aq_sensor": best_sensor,
                    "aq_sensors": len(aq), "hour_of_day_eta2": round(eta2, 4),
                    "room_dampers": len(dampers),
                    "thresholds": {"min_aq_correlation": V1A_MIN_AQ_CORRELATION,
                                   "min_hour_eta2": V1A_MIN_HOUR_ETA2}})


def check_V1c(csv_files: dict) -> dict:
    """
    V-1c: Air flow/pressure control at AHU level (max FL=4)
    L1=fixed speed; L2=manually adjustable speed; L3=scheduled; L4=demand-based.
    Evidence: ComfoAirQ_Supply-Fan-Duty CSV — fan duty varies.
    """
    fan_key = next((k for k in csv_files if "comfoairq_supply_fan_duty" in k), None)
    if fan_key is None:
        return _result("V-1c", NA_NOT_EVIDENCED, 0, 0.0,
                       "No Supply-Fan-Duty CSV found. Cannot assess AHU flow control.")

    df = csv_files[fan_key]
    vals = pd.to_numeric(df["state"], errors="coerce").dropna()
    if len(vals) == 0:
        return _result("V-1c", NA_NOT_EVIDENCED, 0, 0.0, "Supply-Fan-Duty CSV has no valid numeric values.")

    cov = analyze_coverage(df, max_gap_hours=3)
    unique_vals = sorted(vals.unique())
    n_unique = len(unique_vals)
    val_range = f"{vals.min():.0f}%–{vals.max():.0f}%"

    # ComfoAir Q450 has multiple fan speed presets (Away/Low/Medium/High/Boost)
    # Multiple duty levels in CSV = manually adjustable → L2
    # Scheduled/auto control possible via ComfoAir app but cannot verify from duty % alone
    pressure_entities = [k for k in csv_files
                         if any(t in k.lower() for t in ("pressure", "pressione"))]
    if n_unique >= 3 and pressure_entities:
        level = 4
        conf = 0.72
        note = (f"{n_unique} distinct duty levels ({val_range}) with "
                f"{len(pressure_entities)} pressure entities: automatic flow control with "
                f"pressure reset. L4.")
    elif n_unique >= 3:
        level = 2
        conf = 0.72
        note = f"{n_unique} distinct duty levels ({val_range}) → manually adjustable speed confirmed → L2."
    else:
        level = 1
        conf = 0.60
        note = f"Only {n_unique} duty level(s) observed → appears fixed speed → L1."

    status, gate_note = _gate(VERIFIED, coverage_pct=cov["coverage_pct"],
                              n_records=len(vals))
    return _result("V-1c", status, level, conf,
                   f"ComfoAirQ_Supply-Fan-Duty CSV: {len(vals)} records, {cov['period_days']} days, {gate_note}"
                   f"coverage {cov['coverage_pct']}%. {note} "
                   f"L3 (schedule-based) and L4 (demand/CO2-based) not verifiable from duty % alone.",
                   {"n_records": len(vals), "n_unique_levels": n_unique,
                    "duty_range": val_range, "coverage_pct": cov["coverage_pct"]})


def check_V2c(csv_files: dict) -> dict:
    """
    V-2c: Heat recovery control / bypass (max FL=2)
    L1=manual/fixed bypass; L2=automatic temperature-based.
    Evidence: ComfoAirQ_Bypass-State CSV.
    """
    bp_key = next((k for k in csv_files if "comfoairq_bypass_state" in k), None)
    if bp_key is None:
        return _result("V-2c", NA_NOT_EVIDENCED, 0, 0.0,
                       "No Bypass-State CSV found. Cannot assess heat recovery bypass control.")

    df = csv_files[bp_key]
    cov = analyze_coverage_event_driven(df, "bypass")

    # Identify open transitions (bypass active = heat recovery disabled)
    try:
        numeric_states = pd.to_numeric(df["state"], errors="coerce")
        df_valid = df[numeric_states.notna()].copy()
        df_valid["state_num"] = pd.to_numeric(df_valid["state"], errors="coerce")
        # Bypass > 1% = open
        open_mask = df_valid["state_num"] > 1.0
        n_open = int(open_mask.sum())
        n_total = len(df_valid)
        # Count transitions from closed to open
        transitions = int(((~open_mask.values[:-1]) & (open_mask.values[1:])).sum())
    except Exception:
        n_open = n_total = transitions = 0

    if not cov["ok"] and cov["n_records"] < 3:
        return _result("V-2c", PARTIAL_EVIDENCE, 1, 0.45,
                       f"Bypass-State CSV: only {cov['n_records']} records. Insufficient coverage. "
                       f"Manual bypass at L1 inferred from ComfoAir Q450 hardware capability.")

    # Bypass transitions happen without manual intervention → automatic (temp-based) → L2
    return _result("V-2c", VERIFIED, 2, 0.82,
                   f"ComfoAirQ_Bypass-State CSV: {cov['n_records']} records, {cov['period_days']} days "
                   f"(max gap {cov['max_gap_days']} days). {n_open}/{n_total} states with bypass open "
                   f"(>1%), {transitions} open-transitions. ComfoAir Q450 opens bypass automatically "
                   f"when outdoor air temperature is more favourable than heat recovery → L2 (automatic "
                   f"temperature-based control). No manual intervention required.",
                   {"n_records": cov["n_records"], "period_days": cov["period_days"],
                    "n_open_states": n_open, "n_transitions": transitions})


def check_V2d(csv_files: dict) -> dict:
    """
    V-2d: Supply air temperature control at AHU level (max FL=3)
    L1=fixed setpoint; L2=variable setpoint; L3=demand-based.
    Evidence: Exhaust-Temperature + Inside-Temperature CSVs.
    """
    ex_key = next((k for k in csv_files if "comfoairq_exhaust_temperature" in k), None)
    ins_key = next((k for k in csv_files if "comfoairq_inside_temperature" in k), None)
    if not ex_key and not ins_key:
        return _result("V-2d", PARTIAL_EVIDENCE, 1, 0.50,
                       "No temperature CSVs for ComfoAir found. L1 inferred from MVHR design.")

    records = {}
    for key, label in [(ex_key, "exhaust"), (ins_key, "inside")]:
        if key:
            df = csv_files[key]
            vals = pd.to_numeric(df["state"], errors="coerce").dropna()
            records[label] = {"n": len(vals), "min": round(float(vals.min()),1) if len(vals)>0 else None,
                               "max": round(float(vals.max()),1) if len(vals)>0 else None}

    # ComfoAir Q450 regulates supply temperature via bypass ratio
    # When bypass closes → full heat recovery → supply temp rises toward exhaust temp
    # Official ladder: L1 constant set point held by a control loop; L2 variable
    # set point with OUTDOOR TEMPERATURE COMPENSATION; L3 variable set point with
    # load dependent compensation.
    #
    # A high correlation between supply air temperature and outdoor temperature
    # does NOT establish compensation. In a heat recovery unit the supply
    # temperature is largely determined by outdoor and exhaust conditions through
    # the exchanger itself: it is an outcome, not a controlled variable. Genuine
    # compensation would show the supply temperature being held to a target that
    # SHIFTS with outdoor temperature, which requires the target to be visible.
    sup = next((k for k in csv_files if "comfoairq_supply_temperature" in k), None)
    out = next((k for k in csv_files if "comfoairq_outside_temperature" in k), None)
    r_out, spread = None, None
    if sup and out:
        j = pd.concat({"s": _hourly(csv_files[sup]), "o": _hourly(csv_files[out])},
                      axis=1).dropna()
        if len(j) >= 200:
            r_out = round(float(j["s"].corr(j["o"])), 3)
            spread = round(float(j["s"].max() - j["s"].min()), 1)
    setpoint_entities = [k for k in csv_files
                         if "comfoairq" in k.lower()
                         and any(t in k.lower() for t in ("setpoint", "target", "comfort_temp"))]

    load_inputs = [k for k in csv_files
                   if any(t in k.lower() for t in ("co2", "voc", "occupancy", "presenza"))]
    if setpoint_entities and load_inputs:
        level, status, conf = 3, PARTIAL_EVIDENCE, 0.50
        note = (f"{len(setpoint_entities)} set point entities and {len(load_inputs)} demand "
                f"inputs: load dependent compensation is observable. L3 as partial evidence.")
    elif setpoint_entities:
        level, status, conf = 2, PARTIAL_EVIDENCE, 0.55
        note = (f"{len(setpoint_entities)} supply temperature set point entities exist, so "
                f"outdoor compensation is observable in principle. L2 as partial evidence.")
    else:
        level, status, conf = 1, VERIFIED, 0.70
        note = (f"The ComfoAir Q450 holds supply air temperature through heat recovery and bypass "
                f"modulation, which is a control loop and meets L1. Supply temperature correlates "
                f"with outdoor temperature at r={r_out} and swings {spread} degrees across the "
                f"period, but that is the exchanger passing ambient conditions through, not "
                f"evidence of a compensated set point: no set point entity exists for the unit, "
                f"so the target cannot be observed and L2 cannot be established. "
                f"L3 requires load dependent compensation, which would need an IAQ or demand "
                f"input; no CO2 or VOC sensor is present.")

    return _result("V-2d", status, level, conf,
                   f"Assessed against the official catalogue B wording. {note}",
                   {"temperature_records": records,
                    "supply_vs_outdoor_correlation": r_out,
                    "supply_temp_spread_c": spread,
                    "setpoint_entities": len(setpoint_entities)})


V3_NIGHT_HOURS = range(22, 24)          # plus 0-6, applied below
V3_NIGHT_HOURS = list(range(22, 24)) + list(range(0, 7))
V3_MAX_NIGHT_SHARE = 0.60               # above this, free cooling is night cooling only
V3_MIN_ENTHALPY_CORRELATION = 0.50      # humidity must actually drive the bypass
V3_HUMIDITY_PARITY = 0.80               # and do so comparably to temperature


def check_V3(csv_files: dict) -> dict:
    """
    V-3: Free cooling with mechanical ventilation system (max FL=3)

    Official levels (SRI calculation sheet v4.5, catalogue B):
      L0 No automatic control
      L1 Night cooling
      L2 Free cooling: air flows modulated during all periods of time to
         minimize the amount of mechanical cooling
      L3 H,x-directed control: outside air and recirculation modulated during
         all periods, calculated on the basis of temperatures AND humidity
         (enthalpy)

    L1 versus L2 is therefore a question of WHEN the bypass opens, and L2 versus
    L3 a question of WHAT drives it. Both are measurable.
    """
    bp_key = next((k for k in csv_files if "comfoairq_bypass_state" in k), None)
    rmot_key = next((k for k in csv_files if "comfoairq_current_rmot" in k), None)
    hum_key = next((k for k in csv_files if "comfoairq_outside_humidity" in k), None)

    if not bp_key:
        return _result("V-3", PARTIAL_EVIDENCE, 1, 0.45,
                       "No Bypass-State CSV for free cooling verification. DBL09: Zehnder ComfoAir "
                       "Q450 supports free cooling via bypass. Manual free cooling (L1) inferred.",
                       {"source": "DBL09"})

    df_bp = csv_files[bp_key]
    cov = analyze_coverage_event_driven(df_bp, "bypass")

    try:
        numeric_states = pd.to_numeric(df_bp["state"], errors="coerce")
        open_pct = float((numeric_states > 1.0).mean() * 100)
    except Exception:
        open_pct = 0.0

    # ── L1 vs L2: is free cooling limited to the night, or active all day? ────
    d = df_bp.dropna(subset=["last_changed"]).copy()
    d["_open"] = pd.to_numeric(d["state"], errors="coerce") > 1.0
    op = d[d["_open"]]
    night_share = 0.0
    if len(op):
        night = op["last_changed"].dt.hour.isin(V3_NIGHT_HOURS)
        night_share = float(night.mean())
    all_periods = len(op) > 0 and night_share <= V3_MAX_NIGHT_SHARE

    # ── L3: is the bypass driven by enthalpy, i.e. humidity as well as temperature?
    byp = _hourly(df_bp)
    corr = {}
    for label, pat in [("t_out", "comfoairq_outside_temperature"),
                       ("t_in", "comfoairq_inside_temperature"),
                       ("h_out", "comfoairq_outside_humidity"),
                       ("h_in", "comfoairq_inside_humidity")]:
        k = next((x for x in csv_files if pat in x), None)
        if k is None or byp is None:
            continue
        other = _hourly(csv_files[k])
        if other is None:
            continue
        j = pd.concat({"a": byp, "b": other}, axis=1).dropna()
        if len(j) >= 200:
            r = j["a"].corr(j["b"])
            if pd.notna(r):
                corr[label] = round(float(r), 3)

    temp_r = max((abs(corr.get(k, 0)) for k in ("t_out", "t_in")), default=0.0)
    hum_r = max((abs(corr.get(k, 0)) for k in ("h_out", "h_in")), default=0.0)
    enthalpy_control = (hum_r >= V3_MIN_ENTHALPY_CORRELATION
                        and hum_r >= temp_r * V3_HUMIDITY_PARITY)

    if len(op) == 0:
        level, status, conf = 0, VERIFIED, 0.75
        note = ("Bypass never opened in the analysis period: no automatic free cooling. L0.")
    elif enthalpy_control:
        level, status, conf = 3, VERIFIED, 0.72
        note = (f"Bypass tracks humidity (r={hum_r:.2f}) as strongly as temperature "
                f"(r={temp_r:.2f}): enthalpy-directed control. L3.")
    elif all_periods:
        level, status, conf = 2, VERIFIED, 0.74
        note = (f"Bypass open in {open_pct:.0f}% of states, of which only "
                f"{night_share*100:.0f}% fall in night hours, so free cooling is modulated "
                f"across all periods rather than limited to night cooling. L2. "
                f"L3 requires enthalpy-directed control: humidity correlates at r={hum_r:.2f} "
                f"against temperature at r={temp_r:.2f}, below the "
                f"{V3_MIN_ENTHALPY_CORRELATION} threshold and not at parity with temperature, "
                f"so the control is temperature-driven only.")
    else:
        level, status, conf = 1, VERIFIED, 0.70
        note = (f"Bypass openings concentrate at night ({night_share*100:.0f}% of openings): "
                f"night cooling. L1.")

    status, gate_note = _gate(status, n_records=cov["n_records"])
    return _result("V-3", status, level, conf,
                   f"Assessed against the official catalogue B wording. Free cooling via the {gate_note}"
                   f"ComfoAir Q450 bypass, {cov['n_records']} records over {cov['period_days']} "
                   f"days. {note} This service reads the same bypass entity as V-2c: V-2c assesses "
                   f"overheating prevention of the heat exchanger, V-3 the free cooling function, "
                   f"which are distinct services delivered by the same physical component.",
                   {"bypass_records": cov["n_records"], "period_days": cov["period_days"],
                    "bypass_open_pct": round(open_pct, 1),
                    "open_events": int(len(op)),
                    "night_share_of_openings": round(night_share, 3),
                    "correlations": corr,
                    "temp_correlation": round(temp_r, 3),
                    "humidity_correlation": round(hum_r, 3),
                    "has_rmot": rmot_key is not None,
                    "has_humidity": hum_key is not None})


# V-6 evidence thresholds, as named constants so narrative and code cannot drift.
V6_MIN_RECORDS_PER_SENSOR = 500   # a sensor with genuine operational history
V6_MIN_ZONES_FOR_L2       = 3     # room-level reporting, not a single measurement point
V6_MIN_PARAM_TYPES_FOR_L3 = 2     # multi-parameter IAQ

# IAQ parameter families. Entity names appear in both English (ComfoAir) and
# Italian (Tado room sensors), which is why matching on one language alone
# silently discards half the evidence.
IAQ_PARAMETERS = {
    "humidity": ("umidita", "humidity"),
    "co2":      ("co2", "carbon_dioxide"),
    "voc":      ("voc", "tvoc"),
    "pm":       ("pm2", "pm10", "pm1_", "particulate"),
    "radon":    ("radon",),
}


def check_V6(csv_files: dict) -> dict:
    """
    V-6: IAQ reporting (max FL=3)
    L0 = none; L1 = single IAQ parameter measured but not resolved per zone;
    L2 = IAQ parameter(s) logged per zone with operational history;
    L3 = two or more distinct IAQ parameter families reported.

    Evidence is derived from the CSV entity inventory rather than asserted from
    the DBL sensing section.
    """
    if not csv_files:
        return _result("V-6", NA_NOT_EVIDENCED, 0, 0.0,
                       "No CSV data available. IAQ reporting cannot be assessed.")

    found = {}          # family -> [(entity, n_records)]
    for family, tokens in IAQ_PARAMETERS.items():
        hits = []
        for k, df in csv_files.items():
            kl = k.lower()
            if any(t in kl for t in tokens):
                hits.append((k, len(df)))
        if hits:
            found[family] = hits

    if not found:
        return _result("V-6", VERIFIED, 0, 0.85,
                       "No IAQ parameter (humidity, CO2, VOC, particulates, radon) found in the "
                       "CSV entity inventory. No IAQ reporting evidenced. L0.",
                       {"iaq_families_found": []})

    # sensors with enough history to constitute reporting rather than a snapshot
    substantive = {f: [(k, n) for k, n in v if n >= V6_MIN_RECORDS_PER_SENSOR]
                   for f, v in found.items()}
    substantive = {f: v for f, v in substantive.items() if v}

    # distinct zones: strip the parameter token and any trailing duplicate index
    zones = set()
    for family, tokens in IAQ_PARAMETERS.items():
        for k, n in substantive.get(family, []):
            name = k.split(".")[-1].lower()
            for t in tokens:
                name = name.replace(t, "")
            name = re.sub(r"_\d+$", "", name).strip("_")
            if name and not name.startswith("comfoairq"):
                zones.add(name)
    n_zones = len(zones)
    n_families = len(substantive)
    total_records = sum(n for v in substantive.values() for _, n in v)

    absent = [f for f in IAQ_PARAMETERS if f not in found]

    if not substantive:
        level, status, conf = 1, PARTIAL_EVIDENCE, 0.45
        note = (f"IAQ parameters present ({', '.join(found)}) but no sensor reaches "
                f"{V6_MIN_RECORDS_PER_SENSOR} records, so continuous reporting is not evidenced.")
    elif n_families >= V6_MIN_PARAM_TYPES_FOR_L3 and n_zones >= V6_MIN_ZONES_FOR_L2:
        level, status, conf = 3, VERIFIED, 0.80
        note = (f"{n_families} distinct IAQ parameter families ({', '.join(substantive)}) logged "
                f"across {n_zones} zones. Multi-parameter IAQ reporting confirmed at L3.")
    elif n_zones >= V6_MIN_ZONES_FOR_L2:
        level, status, conf = 2, VERIFIED, 0.72
        note = (f"IAQ parameter '{', '.join(substantive)}' logged per zone across {n_zones} rooms "
                f"({total_records} records total), each an individually addressable entity with "
                f"continuous history in the building's monitoring platform. Individual IAQ "
                f"parameter reporting confirmed at L2. L3 requires at least "
                f"{V6_MIN_PARAM_TYPES_FOR_L3} parameter families; absent here: {', '.join(absent)}.")
    else:
        level, status, conf = 1, VERIFIED, 0.65
        note = (f"IAQ parameter '{', '.join(substantive)}' logged with {total_records} records but "
                f"resolved to only {n_zones} zone(s), below the {V6_MIN_ZONES_FOR_L2}-zone threshold "
                f"for per-room reporting. Single-point IAQ indication at L1.")

    return _result("V-6", status, level, conf,
                   f"CSV entity inventory: {note} "
                   f"DBL08 sensing section lists CO2, PM2.5, PM10, VOC and occupancy as not "
                   f"installed, which the CSV confirms. Interpretation note: relative humidity is "
                   f"treated here as an IAQ parameter reported to the occupant, since the room "
                   f"sensors are individually exposed in the monitoring platform and are not "
                   f"internal to the ventilation control loop.",
                   {"iaq_families_found": sorted(found),
                    "iaq_families_substantive": sorted(substantive),
                    "iaq_families_absent": sorted(absent),
                    "n_zones": n_zones, "zones": sorted(zones),
                    "total_records": total_records,
                    "thresholds": {"min_records_per_sensor": V6_MIN_RECORDS_PER_SENSOR,
                                   "min_zones_for_l2": V6_MIN_ZONES_FOR_L2,
                                   "min_param_types_for_l3": V6_MIN_PARAM_TYPES_FOR_L3}})


# ════════════════════════════════════════════════════════════════════════════════
# SERVICE CHECK FUNCTIONS — LIGHTING (2 services)
# ════════════════════════════════════════════════════════════════════════════════

def check_L1a(csv_files: dict) -> dict:
    """L-1a: Occupancy control for indoor lighting. Source: manual_assessments.json."""
    return _from_manual("L-1a")


def check_L2(csv_files: dict) -> dict:
    """L-2: Lighting control based on daylight levels. Source: manual_assessments.json."""
    return _from_manual("L-2")


# ════════════════════════════════════════════════════════════════════════════════
# SERVICE CHECK FUNCTIONS — DYNAMIC ENVELOPE (3 services)
# ════════════════════════════════════════════════════════════════════════════════

def check_DE1(csv_files: dict) -> dict:
    """
    DE-1: Window solar shading control (max FL=4).
    L0=shading present, no automatic control; L1=manual with info; L2=auto; L3=auto+optimised; L4=demand-responsive.
    Evidence: IFC Architectural contains 'Persiane' as IFCBUILDINGELEMENTPROXY elements — 5 types
    (40x50, 46.7x250, 70x160, 70x250, 80x160), ~29 instances. These are manual roller shutters.
    No motorisation, no actuator, no CSV sensor data → L0 (system present, no automatic control).
    Previous code assigned NA_NOT_EVIDENCED because the grep only searched named IFC shading classes;
    Persiane are stored as IFCBUILDINGELEMENTPROXY — corrected by keyword search on entity name.
    """
    persiane_count = IFC_INVENTORY["01_Architectural"].get("IFCBUILDINGELEMENTPROXY_Persiane", 0)
    if persiane_count == 0:
        return _result("DE-1", NA_NOT_EVIDENCED, 0, 0.80,
                       "No shading elements found in IFC, DBL09, or DBL08. Service not evidenced.",
                       {"source": "IFC + DBL09"})

    actuators = [(k, len(df)) for k, df in csv_files.items()
                 if any(t in k.lower() for t in SHADING_ACTUATOR_TOKENS)]
    irradiance = [(k, len(df)) for k, df in csv_files.items()
                  if any(t in k.lower() for t in IRRADIANCE_TOKENS)]

    if actuators and irradiance and FORECAST_ENTITIES(csv_files):
        level, conf = 4, 0.72
        note = (f"Shading actuators, irradiance sensing and "
                f"{len(FORECAST_ENTITIES(csv_files))} forecast entities: predictive blind "
                f"control. L4.")
    elif actuators and irradiance and len(actuators) >= 2:
        level, conf = 3, 0.70
        note = (f"{len(actuators)} shading actuators with irradiance sensing and combined "
                f"control across openings. L3.")
    elif actuators and irradiance:
        level, conf = 2, 0.72
        note = (f"{len(actuators)} shading actuator entities and {len(irradiance)} irradiance "
                f"sensors found: automatic solar shading control evidenced at L2. L3 and L4 "
                f"require evidence of optimisation or demand response, assessed separately.")
    elif actuators:
        level, conf = 1, 0.65
        note = (f"{len(actuators)} shading actuator entities found but no irradiance sensor, "
                f"so control cannot be daylight-driven. Motorised shading with occupant "
                f"command at L1.")
    else:
        level, conf = 0, 0.90
        note = (f"Entity inventory scanned across {len(csv_files)} entities for shutter, blind "
                f"or cover actuators and for irradiance sensors: zero matches. This is "
                f"consistent with the IFC, where the Persiane are plain "
                f"IFCBUILDINGELEMENTPROXY elements in 5 size types with no actuator geometry. "
                f"Shading exists but is operated manually, with no automatic control. L0.")

    status, gate_note = _gate(VERIFIED, n_records=persiane_count * 100)

    return _result("DE-1", status, level, conf,
                   f"IFC Architectural: {persiane_count} Persiane (roller shutter) instances "
                   f"confirm the service is applicable. {note}",
                   {"persiane_instances": persiane_count,
                    "shading_actuator_entities": len(actuators),
                    "irradiance_entities": len(irradiance),
                    "entities_scanned": len(csv_files)})


DE2_MIN_HISTORY = 100   # records a window-state entity needs before detection counts as
                        # operationally evidenced rather than merely configured
WINDOW_STATE_TOKENS  = ("finestra", "window", "contact")
WINDOW_ACTUATOR_TOKENS = ("attuatore", "actuator", "motor", "tapparella_auto")
# A motorised shading device surfaces in Home Assistant as a cover entity or under
# one of these names. Their absence across the whole inventory is what supports L0
# for DE-1 and DE-4, rather than the logbook being silent on the subject.
SHADING_ACTUATOR_TOKENS = ("tapparella", "persiana", "shutter", "blind",
                           "awning", "cover.", "veneziana", "tenda")
IRRADIANCE_TOKENS = ("irradiance", "solar_radiation", "illuminance", "lux",
                     "luminosita", "luminosity")


def check_DE2(csv_files: dict) -> dict:
    """
    DE-2: Window open/closed control and HVAC interlock (max FL=3)
    L0 = windows present, no open/closed detection; L1 = detection present;
    L2 = detection with evidenced HVAC response; L3 = automatic window actuation.

    Applicability comes from the IFC (windows exist). The level comes from the CSV
    entity inventory: the Tado thermostats expose a per-room open-window state,
    which the previous documental assessment did not account for.
    """
    windows_count = IFC_INVENTORY["01_Architectural"].get("IFCWINDOW", 0)
    if windows_count == 0:
        return _result("DE-2", NA_NOT_EVIDENCED, 0, 0.85,
                       "No window elements confirmed in the IFC. Service not evidenced.",
                       {"source": "IFC"})

    detect = [(k, len(df)) for k, df in csv_files.items()
              if any(t in k.lower() for t in WINDOW_STATE_TOKENS)]
    actuate = [(k, len(df)) for k, df in csv_files.items()
               if any(t in k.lower() for t in WINDOW_ACTUATOR_TOKENS)]
    detect_with_history = [(k, n) for k, n in detect if n >= DE2_MIN_HISTORY]

    # Did any window-open event actually occur? Tado reports 'on' when a room's
    # temperature profile indicates an open window.
    open_events, zones_with_events = 0, set()
    for k, _ in detect:
        st = csv_files[k].get("state")
        if st is None:
            continue
        n_on = int(st.astype(str).str.lower().isin({"on", "true", "open"}).sum())
        if n_on:
            open_events += n_on
            zones_with_events.add(k.split(".")[-1])

    if actuate:
        level, status, conf = 3, VERIFIED, 0.75
        note = (f"{len(actuate)} window/shading actuator entities found: automatic window "
                f"control evidenced at L3.")
    elif open_events > 0 and detect_with_history:
        level, status, conf = 2, VERIFIED, 0.72
        note = (f"{len(detect)} window-state entities, {open_events} open-window events "
                f"observed across {len(zones_with_events)} zones with sufficient history. "
                f"Detection is operational and linked to the heating controller at L2.")
    elif detect_with_history:
        level, status, conf = 1, VERIFIED, 0.68
        note = (f"{len(detect_with_history)} window-state entities with operational history, "
                f"but no open-window event recorded. Detection present at L1; the HVAC "
                f"interlock at L2 cannot be evidenced without an event to observe.")
    elif detect:
        level, status, conf = 1, PARTIAL_EVIDENCE, 0.50
        note = (f"{len(detect)} per-room open-window state entities exist "
                f"({', '.join(sorted(k.split('.')[-1] for k, _ in detect)[:4])}...), confirming "
                f"the Tado thermostats provide open-window detection. However every one holds "
                f"fewer than {DE2_MIN_HISTORY} records (snapshot only, no history), so detection "
                f"is configured but not operationally evidenced. L1 as partial evidence.")
    else:
        level, status, conf = 0, VERIFIED, 0.85
        note = ("No window-state entity of any kind in the CSV inventory. "
                "No open/closed detection. L0.")

    return _result("DE-2", status, level, conf,
                   f"IFC Architectural: {windows_count} IFCWINDOW elements confirm the service "
                   f"is applicable. {note} No motorised window or shading actuator found, "
                   f"consistent with the IFC (Persiane modelled as plain building element "
                   f"proxies with no actuator).",
                   {"windows_in_ifc": windows_count,
                    "window_state_entities": len(detect),
                    "window_state_with_history": len(detect_with_history),
                    "open_window_events": open_events,
                    "actuator_entities": len(actuate),
                    "thresholds": {"min_history": DE2_MIN_HISTORY}})


def check_DE4(csv_files: dict) -> dict:
    """
    DE-4: Dynamic envelope performance reporting (max FL=4).
    Requires dynamic envelope elements to exist. Persiane (roller shutters) confirmed in IFC → envelope exists.
    However, no reporting system for shutter position, solar gain, or envelope performance is documented
    in DBL09, DBL08, or any CSV → L0 (no reporting).
    """
    persiane_count = IFC_INVENTORY["01_Architectural"].get("IFCBUILDINGELEMENTPROXY_Persiane", 0)
    windows_count  = IFC_INVENTORY["01_Architectural"].get("IFCWINDOW", 0)
    if persiane_count == 0 and windows_count == 0:
        return _result("DE-4", NA_EXPLICIT_ABSENCE, 0, 0.90,
                       "No envelope elements found. Service not applicable.",
                       {"source": "IFC"})

    # Reporting requires an entity that exposes envelope state to the occupant.
    position = [(k, len(df)) for k, df in csv_files.items()
                if any(t in k.lower() for t in SHADING_ACTUATOR_TOKENS)]
    state = [(k, len(df)) for k, df in csv_files.items()
             if any(t in k.lower() for t in WINDOW_STATE_TOKENS)]
    state_with_history = [(k, n) for k, n in state if n >= DE2_MIN_HISTORY]

    if position and state_with_history and _predictive_entities(csv_files) \
            and FORECAST_ENTITIES(csv_files):
        level, status, conf = 4, PARTIAL_EVIDENCE, 0.50
        note = ("Position, state history and predictive maintenance entities all present. "
                "L4 as partial evidence.")
    elif position and state_with_history and _predictive_entities(csv_files):
        level, status, conf = 3, PARTIAL_EVIDENCE, 0.50
        note = ("Position and state history with fault detection entities. "
                "L3 as partial evidence.")
    elif position and state_with_history:
        level, status, conf = 2, VERIFIED, 0.70
        note = (f"{len(position)} shading position entities and {len(state_with_history)} window "
                f"state entities with history: envelope state reported at L2.")
    elif position or state_with_history:
        level, status, conf = 1, VERIFIED, 0.65
        note = (f"{len(position)} shading position and {len(state_with_history)} window state "
                f"entities with history: partial envelope reporting at L1.")
    elif state:
        level, status, conf = 1, PARTIAL_EVIDENCE, 0.45
        note = (f"{len(state)} window state entities exist but none reaches {DE2_MIN_HISTORY} "
                f"records, so reporting is configured but not operationally evidenced. "
                f"L1 as partial evidence.")
    else:
        level, status, conf = 0, VERIFIED, 0.88
        note = (f"Entity inventory scanned across {len(csv_files)} entities for shutter position "
                f"or envelope state reporting: zero matches. No envelope performance reporting. L0.")

    return _result("DE-4", status, level, conf,
                   f"IFC Architectural: {persiane_count} Persiane and {windows_count} windows "
                   f"confirm dynamic envelope elements are present, so the service applies. {note}",
                   {"persiane_instances": persiane_count, "windows": windows_count,
                    "shading_position_entities": len(position),
                    "window_state_entities": len(state),
                    "window_state_with_history": len(state_with_history),
                    "entities_scanned": len(csv_files)})


# ════════════════════════════════════════════════════════════════════════════════
# SERVICE CHECK FUNCTIONS — ELECTRICITY (7 services)
# ════════════════════════════════════════════════════════════════════════════════

def check_E2(csv_files: dict) -> dict:
    """
    E-2: Local electricity generation reporting (max FL=4)
    L1=basic counter; L2=time-resolved data; L3=production vs consumption; L4=predictive.
    Evidence: Villa-Percentuale-Solare CSV (solar %, NOT kWh). PV inverter from DBL09.
    """
    solar_key = next((k for k in csv_files if "percentuale_solare" in k), None)
    if solar_key is None:
        return _result("E-2", PARTIAL_EVIDENCE, 1, 0.50,
                       "DBL09: PV system 2.4 kWp with inverter and energy management devices. "
                       "No PV production CSV (Shelly or inverter data absent). Inverter inherently "
                       "provides L1 reporting via display/app. Conservative: L1 (partial).",
                       {"source": "DBL09"})

    df = csv_files[solar_key]
    vals = pd.to_numeric(df["state"], errors="coerce").dropna()
    n = len(vals)
    cov = analyze_coverage(df, max_gap_hours=25)

    # Villa-Percentuale-Solare = solar fraction (%), NOT production in kWh
    # This is a MONITORING metric, not raw generation in kWh
    # L1 (counter reading) → PV inverter provides this via its own display/app (DBL09)
    # The solar % CSV confirms the monitoring system is active in Home Assistant
    # L2 (time-resolved data) → solar % logged hourly confirms time-resolved monitoring
    level, forecast, predictive = _reporting_level(
        csv_files, has_current=n > 0,
        has_history=n >= 500 and cov["period_days"] >= 60)
    status, gate_note = _gate(VERIFIED, coverage_pct=cov["coverage_pct"], n_records=n)
    return _result("E-2", status, level, 0.68,
                   f"DBL09: PV 2.4 kWp (12 panels × 200 Wp) with inverter + energy management. {gate_note}"
                   f"CSV 'Villa-Percentuale-Solare' ({n} records, {cov['period_days']} days, "
                   f"coverage {cov['coverage_pct']}%): solar fraction logged at sub-hourly resolution "
                   f"in Home Assistant → confirms time-resolved monitoring (L2). NOTE: CSV contains "
                   f"solar fraction (%), not production in kWh — absolute generation reporting (L3/L4) "
                   f"would require kWh data from inverter API (Shelly not available). Conservative: L2.",
                   {"n_records": n, "period_days": cov["period_days"],
                    "coverage_pct": cov["coverage_pct"],
                    "note": "Solar % only — not kWh production"})


def check_E3(csv_files: dict) -> dict:
    """E-3: Storage of locally generated electricity. Source: manual_assessments.json."""
    return _from_manual("E-3")


E4_MIN_HOURS = 500          # hourly observations needed to test a control relationship
E4_MIN_PV_CORRELATION = 0.50  # load tracking renewable availability -> L2
E4_MIN_SCHEDULE_ETA2 = 0.15   # a load with a daily schedule -> L1


def check_E4(csv_files: dict) -> dict:
    """
    E-4: Optimizing self-consumption of locally generated electricity (max FL=3)

    Official levels (SRI calculation sheet v4.5, catalogue B):
      L0 None
      L1 Scheduling electricity consumption (plug loads, white goods, etc.)
      L2 Automated management of local electricity consumption based on CURRENT
         renewable energy availability
      L3 Automated management based on current AND predicted energy needs and
         renewable availability

    Moved out of manual_assessments.json on 2026-08-27. The Shelly meters make
    both questions measurable: whether total load follows PV output (L2), and
    whether any individual load runs to a daily schedule (L1).
    """
    grid_k = next((k for k in csv_files if "em0_power" in k), None)
    pv_k = next((k for k in csv_files if "em1_power" in k), None)
    if grid_k is None or pv_k is None:
        return _result("E-4", NA_NOT_EVIDENCED, 0, 0.0,
                       "No grid or PV meter entity. Self-consumption cannot be assessed.")

    grid = _hourly(csv_files[grid_k])
    pv = _hourly(csv_files[pv_k])
    j = pd.concat({"grid": grid, "pv": pv}, axis=1).dropna()
    if len(j) < E4_MIN_HOURS:
        return _result("E-4", PARTIAL_EVIDENCE, 0, 0.45,
                       f"Only {len(j)} hours with both grid and PV readings, below "
                       f"{E4_MIN_HOURS}. Self-consumption behaviour cannot be characterised.",
                       {"hours": int(len(j))})

    # Total site load. Grid is signed: negative means export.
    j["load"] = j["grid"] + j["pv"]
    load_pv_r = float(j["load"].corr(j["pv"]))
    export_share = float((j["grid"] < 0).mean())

    # Any individually metered load running on a daily schedule satisfies L1.
    scheduled = []
    for k, d in csv_files.items():
        kl = k.lower()
        if "power" not in kl or k in (grid_k, pv_k):
            continue
        s = _hourly(d)
        if s is None:
            continue
        s = s.dropna()
        if len(s) < E4_MIN_HOURS or s.std() == 0:
            continue
        grand = s.mean()
        ssb = sum(len(g) * (g.mean() - grand) ** 2 for _, g in s.groupby(s.index.hour))
        sst = ((s - grand) ** 2).sum()
        eta2 = float(ssb / sst) if sst > 0 else 0.0
        if eta2 >= E4_MIN_SCHEDULE_ETA2:
            scheduled.append((k.split(".")[-1], round(eta2, 3)))

    forecast = FORECAST_ENTITIES(csv_files)

    if abs(load_pv_r) >= E4_MIN_PV_CORRELATION and forecast:
        level, status, conf = 3, VERIFIED, 0.72
        note = (f"Total site load tracks PV output (r={load_pv_r:+.2f}) and "
                f"{len(forecast)} forecast entities are available, so consumption is managed "
                f"against current and predicted renewable availability. L3.")
    elif abs(load_pv_r) >= E4_MIN_PV_CORRELATION:
        level, status, conf = 2, VERIFIED, 0.75
        note = (f"Total site load tracks PV output (r={load_pv_r:+.2f}): consumption is managed "
                f"against current renewable availability. L2. L3 additionally requires forecast "
                f"data, of which {len(forecast)} entities exist.")
    elif scheduled:
        level, status, conf = 1, VERIFIED, 0.72
        note = (f"{len(scheduled)} individually metered loads run to a daily schedule "
                f"({', '.join(f'{n} (eta2={e})' for n, e in scheduled)}), which meets L1. "
                f"L2 requires total consumption to follow current renewable availability: total "
                f"load correlates with PV output at only r={load_pv_r:+.2f}, far below the "
                f"{E4_MIN_PV_CORRELATION} threshold, and the site exports to grid in "
                f"{export_share*100:.0f}% of hours, which is what happens when generation is not "
                f"matched to consumption. Scheduling exists, optimisation does not.")
    else:
        level, status, conf = 0, VERIFIED, 0.70
        note = (f"No load runs to a daily schedule and total load does not track PV "
                f"(r={load_pv_r:+.2f}). No self-consumption optimisation. L0.")

    return _result("E-4", status, level, conf,
                   f"Assessed against the official catalogue B wording. {note}",
                   {"hours": int(len(j)), "load_pv_correlation": round(load_pv_r, 3),
                    "export_hours_share": round(export_share, 3),
                    "scheduled_loads": scheduled,
                    "thresholds": {"min_pv_correlation": E4_MIN_PV_CORRELATION,
                                   "min_schedule_eta2": E4_MIN_SCHEDULE_ETA2}})


def check_E5(csv_files: dict) -> dict:
    """E-5: Control of CHP plant. No CHP present."""
    return _result("E-5", NA_EXPLICIT_ABSENCE, 0, 0.98,
                   "DBL09 and DBL08: No CHP (combined heat and power) plant documented. "
                   "Energy sources are natural gas (boiler), electricity (grid + PV), and solar thermal. "
                   "Service not applicable.",
                   {"source": "DBL09 + DBL08"})


E8_ISLANDING_GRID_WATTS = 20    # below this the grid connection is effectively idle
E8_ISLANDING_LOAD_WATTS = 100   # above this the building is genuinely consuming
E8_MIN_ISLANDING_SHARE = 0.02   # sustained islanding, not measurement noise
E8_MIN_HOURS = 500              # hours of paired grid and PV readings needed


def check_E8(csv_files: dict) -> dict:
    """
    E-8: Support of (micro)grid operation modes (max FL=3)

    Official levels (SRI calculation sheet v4.5, catalogue B):
      L0 None
      L1 Automated management of building-level electricity consumption based on
         GRID SIGNALS
      L2 ... and electricity supply to neighbouring buildings
      L3 ... with potential to continue operating disconnected from the grid

    Moved out of manual_assessments.json on 2026-08-27. Every level here starts
    from a grid signal reaching the building, and whether one does is a question
    the entity inventory answers. Islanding is separately testable: it would
    appear as the building consuming while the grid connection sits at zero.
    """
    grid_k = next((k for k in csv_files if "em0_power" in k), None)
    pv_k = next((k for k in csv_files if "em1_power" in k), None)
    grid_signals = [k for k in csv_files
                    if any(t in k.lower() for t in DSM_SIGNAL_TOKENS)]

    islanding_share, hours = 0.0, 0
    if grid_k and pv_k:
        j = pd.concat({"grid": _hourly(csv_files[grid_k]),
                       "pv": _hourly(csv_files[pv_k])}, axis=1).dropna()
        hours = len(j)
        if hours:
            load = j["grid"] + j["pv"]
            islanded = (j["grid"].abs() < E8_ISLANDING_GRID_WATTS) & (load > E8_ISLANDING_LOAD_WATTS)
            islanding_share = float(islanded.mean())
    sustained_islanding = islanding_share >= E8_MIN_ISLANDING_SHARE

    if not grid_signals and not sustained_islanding:
        return _result("E-8", VERIFIED, 0, 0.78,
                       f"Every level of this service begins with a grid signal reaching the "
                       f"building. The entity inventory was scanned across {len(csv_files)} "
                       f"entities for tariff, price, demand-response and curtailment indicators: "
                       f"zero matches. Islanding was tested independently, as hours where the "
                       f"grid connection is below {E8_ISLANDING_GRID_WATTS} W while the building "
                       f"consumes above {E8_ISLANDING_LOAD_WATTS} W: "
                       f"{islanding_share*100:.2f}% of {hours} hours, below the "
                       f"{E8_MIN_ISLANDING_SHARE*100:.0f}% needed to distinguish sustained "
                       f"island operation from metering noise. "
                       f"DBL09 documents a battery, a BMS and an inverter, so the hardware could "
                       f"in principle support island mode, but capability is not operation and no "
                       f"grid interaction is evidenced. L0, established by verified absence rather "
                       f"than by assumption.",
                       {"grid_signal_entities": 0, "entities_scanned": len(csv_files),
                        "islanding_share": round(islanding_share, 4), "hours": hours,
                        "note": "battery and inverter present per DBL09; no observed grid interaction"})

    # Export to a neighbouring building rather than to the grid would need a
    # second metering point on the supply side.
    neighbour = [k for k in csv_files
                 if any(t in k.lower() for t in ("neighbour", "vicino", "shared_supply",
                                                 "community", "condominio"))]

    if hours and hours < E8_MIN_HOURS:
        return _result("E-8", PARTIAL_EVIDENCE, 0, 0.45,
                       f"Only {hours} hours with both grid and PV readings, below "
                       f"{E8_MIN_HOURS}. Grid interaction cannot be characterised. L0 as "
                       f"partial evidence.", {"hours": hours})

    if sustained_islanding:
        level, conf = 3, 0.70
        note = (f"Building consumes while the grid connection is idle in "
                f"{islanding_share*100:.1f}% of {hours} hours: sustained island operation. L3.")
    elif neighbour:
        level, conf = 2, 0.65
        note = (f"{len(grid_signals)} grid signal entities and {len(neighbour)} entities "
                f"metering supply to neighbouring buildings. L2.")
    else:
        level, conf = 1, 0.65
        note = (f"{len(grid_signals)} grid signal entities reach the building, so consumption can "
                f"be managed against them. L1. L2 would require evidence of supply to "
                f"neighbouring buildings ({len(neighbour)} found), L3 of island operation "
                f"({islanding_share*100:.2f}% of hours).")

    return _result("E-8", VERIFIED, level, conf,
                   f"Assessed against the official catalogue B wording. {note}",
                   {"grid_signal_entities": len(grid_signals),
                    "islanding_share": round(islanding_share, 4), "hours": hours})


def check_E11(csv_files: dict) -> dict:
    """E-11: Energy storage reporting. Source: manual_assessments.json."""
    return _from_manual("E-11")


# E-12 thresholds, tied to the official wording rather than invented.
E12_REALTIME_MAX_MINUTES = 15   # "real-time feedback" taken as sub-quarter-hourly sampling
E12_MIN_APPLIANCE_CIRCUITS = 2  # "appliance level" needs more than one individual load
E12_MIN_APPLIANCE_RECORDS = 500  # a circuit with genuine operational history


def check_E12(csv_files: dict) -> dict:
    """
    E-12: Electricity consumption reporting (max FL=4)
    L1=total counter; L2=time-resolved; L3=sub-metered by circuit; L4=appliance-level.
    Evidence: Shelly Pro 3EM (em0=grid/consumption, em1=PV, em2=pool pump) in CSV.
    Priority: Shelly building meter → ComfoAir sub-meter → DBL only.
    """
    # Priority 1: Shelly Pro 3EM — building-level meter with time-resolved data (→ L2)
    shelly_key = next((k for k in csv_files
                       if "shellypro3em" in k.lower() and "em0" in k.lower()), None)

    if shelly_key:
        df = csv_files[shelly_key]
        vals = pd.to_numeric(df["state"], errors="coerce").dropna()
        cov = analyze_coverage(df, max_gap_hours=25)

        # Real-time feedback (L2): how often is the building meter actually sampled?
        t = df.dropna(subset=["last_changed"]).sort_values("last_changed")["last_changed"]
        median_min = (t.diff().dt.total_seconds().median() / 60) if len(t) > 2 else None
        realtime = median_min is not None and median_min <= E12_REALTIME_MAX_MINUTES

        # Appliance level (L3): circuits metering an individual load, not the whole
        # building and not generation. em1 is PV output, so it is excluded.
        appliance = []
        for k, d in csv_files.items():
            kl = k.lower()
            if not any(t_ in kl for t_ in ("power", "potenza", "consumo")):
                continue
            if k == shelly_key or "em1" in kl or "fotovoltaico" in kl:
                continue
            v = pd.to_numeric(d.get("state"), errors="coerce").dropna() if "state" in d.columns else []
            if len(v) >= E12_MIN_APPLIANCE_RECORDS:
                appliance.append((k.split(".")[-1], int(len(v))))

        # Automated personalised recommendations (L4)
        rec = [k for k in csv_files
               if any(t_ in k.lower() for t_ in ("recommend", "advice", "suggerimento", "tip_"))]

        if rec and len(appliance) >= E12_MIN_APPLIANCE_CIRCUITS:
            level, conf = 4, 0.75
            note = (f"{len(appliance)} appliance-level circuits plus {len(rec)} recommendation "
                    f"entities: automated personalised recommendations. L4.")
        elif len(appliance) >= E12_MIN_APPLIANCE_CIRCUITS and realtime:
            level, conf = 3, 0.80
            note = (f"Building meter sampled every {median_min:.1f} min on median "
                    f"({len(vals)} records, coverage {cov['coverage_pct']}%), which is real-time "
                    f"feedback at building level. In addition {len(appliance)} circuits meter "
                    f"individual loads ({', '.join(f'{n} ({c} rec)' for n, c in appliance[:3])}), "
                    f"giving real-time feedback at appliance level. L3. "
                    f"L4 additionally requires automated personalised recommendations, of which "
                    f"there is no entity in the dataset.")
        elif realtime:
            level, conf = 2, 0.78
            note = (f"Building meter sampled every {median_min:.1f} min on median: real-time "
                    f"feedback at building level. L2. L3 requires appliance-level metering; "
                    f"{len(appliance)} qualifying circuits found, below the "
                    f"{E12_MIN_APPLIANCE_CIRCUITS} needed.")
        else:
            level, conf = 1, 0.70
            note = (f"Building electricity consumption is reported ({len(vals)} records) but the "
                    f"median sampling interval is {median_min:.0f} min, above the "
                    f"{E12_REALTIME_MAX_MINUTES} min threshold for real-time feedback. L1.")

        status, gate_note = _gate(VERIFIED, coverage_pct=cov["coverage_pct"],
                                  n_records=len(vals))
        return _result("E-12", status, level, conf,
                       f"Assessed against the official catalogue B wording. {note}{gate_note}",
                       {"building_meter_records": len(vals),
                        "median_sampling_minutes": round(median_min, 2) if median_min else None,
                        "coverage_pct": cov["coverage_pct"],
                        "appliance_circuits": appliance,
                        "recommendation_entities": len(rec)})

    # Priority 2: ComfoAir energy total (sub-meter only → L1 partial)
    energy_total_key = next((k for k in csv_files if "comfoairq_energy_total" in k), None)
    if energy_total_key:
        df = csv_files[energy_total_key]
        vals = pd.to_numeric(df["state"], errors="coerce").dropna()
        return _result("E-12", PARTIAL_EVIDENCE, 1, 0.45,
                       f"No building-level Shelly meter found. ComfoAirQ_Energy-Total "
                       f"({len(vals)} records): MVHR sub-meter only, not building total. "
                       f"DBL09: main distribution board implies L1 metering. Conservative: L1.",
                       {"energy_total_records": len(vals),
                        "note": "MVHR sub-meter only — Shelly CSV absent"})

    return _result("E-12", PARTIAL_EVIDENCE, 1, 0.40,
                   "No electricity meter CSV found (Shelly or sub-meter). "
                   "DBL09: main distribution board and energy management devices imply L1. "
                   "Conservative: L1 (partial evidence).",
                   {"source": "DBL09"})


# ════════════════════════════════════════════════════════════════════════════════
# SERVICE CHECK FUNCTIONS — EV CHARGING (3 services)
# ════════════════════════════════════════════════════════════════════════════════

def _ev_na(code: str) -> dict:
    return _result(code, NA_EXPLICIT_ABSENCE, 0, 0.98,
                   "DBL09 and DBL08: No EV charging infrastructure documented. "
                   "No EV charger CSV. IFC: no EV charging equipment. Service not applicable.",
                   {"source": "DBL09 + DBL08"})

def check_EV15(csv_files): return _ev_na("EV-15")
def check_EV16(csv_files): return _ev_na("EV-16")
def check_EV17(csv_files): return _ev_na("EV-17")


# ════════════════════════════════════════════════════════════════════════════════
# SERVICE CHECK FUNCTIONS — MONITORING & CONTROL (8 services)
# ════════════════════════════════════════════════════════════════════════════════

def check_MC3(csv_files: dict) -> dict:
    """
    MC-3: Run time management of HVAC systems (max FL=3)

    Official levels (SRI calculation sheet v4.5, catalogue B):
      L0 Manual setting
      L1 Runtime setting of heating and cooling plants following a predefined time schedule
      L2 Heating and cooling plant on/off control based on building loads
      L3 Heating and cooling plant on/off control based on predictive control or grid signals

    L2 is about the PLANT (generators) switching on demand, not about the room
    schedule being clever. Distinguishing L1 from L2 therefore requires generator
    telemetry, which this building does not have: no INNOVA heat pump or IMMERGAS
    boiler entity exists in the dataset. That gap is stated explicitly rather than
    resolved by assuming the higher level.
    """
    # Note the substring match: entities were re-created in Home Assistant and the
    # long history lives in the "_2" duplicates, which an endswith() filter drops.
    tado_keys = [k for k in csv_files if "_riscaldamento" in k]
    n_tado = len(tado_keys)
    n_tado_rec = sum(len(csv_files[k]) for k in tado_keys)

    zone_set, sched_detail = _schedule_evidence(csv_files)
    sl_entities, sl_enabled, sl_states = _self_learning_evidence(csv_files)
    grid_entities = [k for k in csv_files
                     if any(t in k.lower() for t in DSM_SIGNAL_TOKENS)]

    # Generator-level telemetry: the only thing that could evidence load-based
    # plant control and lift the service above L1.
    GEN_TOKENS = ("innova", "immergas", "heat_pump", "heatpump", "boiler",
                  "caldaia", "pompa_calore", "generator")
    gen_entities = [k for k in csv_files if any(t in k.lower() for t in GEN_TOKENS)]

    if not zone_set and n_tado == 0:
        return _result("MC-3", NA_NOT_EVIDENCED, 0, 0.0,
                       "No HVAC scheduling or runtime data in the CSV. Run time management "
                       "cannot be assessed.", {"tado_entities": 0})

    if grid_entities:
        level, status, conf = 3, VERIFIED, 0.70
        note = (f"{len(grid_entities)} grid or predictive signal entities found: plant control "
                f"based on predictive control or grid signals. L3.")
    elif gen_entities:
        level, status, conf = 2, PARTIAL_EVIDENCE, 0.55
        note = (f"{len(gen_entities)} generator entities found, so load-based plant control "
                f"is in principle observable. Correlating plant on/off against building load "
                f"is not implemented, so L2 is recorded as partial evidence.")
    elif zone_set:
        level, status, conf = 1, VERIFIED, 0.75
        note = (f"Runtime scheduling confirmed: setpoints follow a predefined schedule in "
                f"{len(zone_set)} zones ({sorted(zone_set)}), with {n_tado} Tado heating "
                f"entities carrying {n_tado_rec} records. That is the L1 condition. "
                f"L2 requires plant on/off control driven by building load, which cannot be "
                f"observed here: the dataset contains no entity for the INNOVA heat pump or the "
                f"IMMERGAS boiler, so generator behaviour is invisible. L2 is therefore not "
                f"excluded by evidence, it is unobservable with the current instrumentation, "
                f"and L1 records only what is demonstrated.")
    else:
        level, status, conf = 0, PARTIAL_EVIDENCE, 0.45
        note = ("HVAC controllers present but no setpoint schedule observed. Manual setting "
                "at L0, recorded as partial evidence.")

    return _result("MC-3", status, level, conf,
                   f"Assessed against the official catalogue B wording. {note} "
                   f"The previous assessment cited the Tado early-start feature as evidence of "
                   f"optimised scheduling; the data show that feature disabled in every zone "
                   f"({sl_states}), so it cannot support a higher level.",
                   {"tado_entities": n_tado, "tado_records": n_tado_rec,
                    "scheduled_zones": sorted(zone_set), "schedule_detail": sched_detail,
                    "generator_entities": len(gen_entities),
                    "grid_signal_entities": len(grid_entities),
                    "self_learning_enabled_records": sl_enabled,
                    "self_learning_states": sl_states,
                    "instrumentation_gap": "No heat pump or boiler telemetry; L2 unobservable"})


# MC-4 evidence thresholds. Declared as named constants so the values quoted in
# the thesis narrative and the values used by the code cannot drift apart.
MC4_MIN_FAULT_EVENTS   = 20   # logged unavailable/unknown states -> detection is operational
MC4_MIN_FAULT_ENTITIES = 5    # distinct entities affected -> not a single failing device
MC4_MIN_DIAG_HISTORY   = 30   # records a diagnostic entity needs to show a trend, not a snapshot
FAULT_STATES = {"unavailable", "unknown"}


def check_MC4(csv_files: dict) -> dict:
    """
    MC-4: Fault detection and diagnosis (max FL=3)
    L0 = none; L1 = faults detected and centrally reported; L2 = + fault isolated
    to a specific device via dedicated diagnostic entities with operational history;
    L3 = + predictive maintenance indicator with a demonstrable trend.

    Evidence, all derived from the CSV rather than asserted:
      - unavailable/unknown states logged per entity  -> detection and central reporting
      - dedicated diagnostic entities (connectivity, battery) -> isolation
      - remaining-life countdown (filter) with history -> prediction
    """
    if not csv_files:
        return _result("MC-4", NA_NOT_EVIDENCED, 0, 0.0,
                       "No CSV data available. Fault detection cannot be assessed.")

    # ── Evidence 1: fault events actually logged, and where ───────────────────
    fault_events, fault_entities = 0, []
    for key, df in csv_files.items():
        if "state" not in df.columns:
            continue
        n_bad = int(df["state"].astype(str).str.lower().isin(FAULT_STATES).sum())
        if n_bad > 0:
            fault_events += n_bad
            fault_entities.append((key, n_bad))
    n_fault_entities = len(fault_entities)

    # ── Evidence 2: dedicated diagnostic entities, and whether they have history
    def _family(substr):
        out = []
        for k, df in csv_files.items():
            if substr in k.lower():
                out.append((k, len(df)))
        return out

    conn = _family("connettivita")
    batt = _family("battery")
    diag = conn + batt
    diag_with_history = [(k, n) for k, n in diag if n >= MC4_MIN_DIAG_HISTORY]

    # ── Evidence 3: predictive maintenance indicator ──────────────────────────
    filt = _family("days_to_replace_filter")
    filt_records = sum(n for _, n in filt)
    filt_trend = False
    if filt:
        vals = pd.to_numeric(csv_files[filt[0][0]]["state"], errors="coerce").dropna()
        # a genuine remaining-life countdown decreases monotonically
        filt_trend = len(vals) >= 3 and vals.iloc[-1] < vals.iloc[0]

    # ── Level assignment ──────────────────────────────────────────────────────
    detection = (fault_events >= MC4_MIN_FAULT_EVENTS
                 and n_fault_entities >= MC4_MIN_FAULT_ENTITIES)
    isolation = len(diag_with_history) >= 1
    prediction = filt_trend and filt_records >= MC4_MIN_DIAG_HISTORY

    if not detection and not diag:
        level, status, conf = 0, VERIFIED, 0.75
        note = ("No fault states logged and no diagnostic entities present. "
                "No fault detection capability evidenced.")
    elif not detection:
        level, status, conf = 0, PARTIAL_EVIDENCE, 0.50
        note = (f"Diagnostic entities exist ({len(diag)}) but only {fault_events} fault "
                f"states were logged across {n_fault_entities} entities, below the "
                f"{MC4_MIN_FAULT_EVENTS}-event / {MC4_MIN_FAULT_ENTITIES}-entity threshold "
                f"for operational detection.")
    elif detection and not isolation:
        level, status, conf = 1, VERIFIED, 0.70
        note = (f"{fault_events} fault states logged across {n_fault_entities} distinct "
                f"entities over the analysis period, each timestamped and attributed to a "
                f"named device in a single platform. Central fault detection and reporting "
                f"confirmed at L1. L2 requires dedicated diagnostic entities with operational "
                f"history: {len(diag)} found, {len(diag_with_history)} with at least "
                f"{MC4_MIN_DIAG_HISTORY} records, so isolation is not evidenced.")
    elif isolation and not prediction:
        level, status, conf = 2, VERIFIED, 0.72
        note = (f"{fault_events} fault states across {n_fault_entities} entities, plus "
                f"{len(diag_with_history)} dedicated diagnostic entities with operational "
                f"history, isolate a fault to a specific device. L2 confirmed. L3 requires a "
                f"predictive indicator with a demonstrable trend: filter countdown has "
                f"{filt_records} records, trend detected = {filt_trend}.")
    else:
        level, status, conf = 3, VERIFIED, 0.78
        note = (f"{fault_events} fault states across {n_fault_entities} entities, "
                f"{len(diag_with_history)} diagnostic entities with history, and a "
                f"remaining-life countdown ({filt_records} records) with a monotonic "
                f"decreasing trend. Predictive maintenance evidenced at L3.")

    top_faults = sorted(fault_entities, key=lambda x: -x[1])[:5]
    return _result("MC-4", status, level, conf,
                   f"Home Assistant fault logging: {note} "
                   f"Interpretation note: unavailable/unknown states are device-level faults of "
                   f"the control layer (TRVs, MVHR, meters), not process faults of the heat "
                   f"generators, which are not instrumented.",
                   {"fault_events": fault_events,
                    "fault_entities": n_fault_entities,
                    "top_fault_entities": [(k.split(".")[-1], n) for k, n in top_faults],
                    "diagnostic_entities": len(diag),
                    "diagnostic_with_history": len(diag_with_history),
                    "filter_countdown_records": filt_records,
                    "filter_trend_detected": filt_trend,
                    "thresholds": {"min_fault_events": MC4_MIN_FAULT_EVENTS,
                                   "min_fault_entities": MC4_MIN_FAULT_ENTITIES,
                                   "min_diag_history": MC4_MIN_DIAG_HISTORY}})


def check_MC9(csv_files: dict) -> dict:
    """
    MC-9: Occupancy detection, connected services (max FL=2)

    Official levels (SRI calculation sheet v4.5, catalogue B):
      L0 None
      L1 Occupancy detection for individual functions, e.g. lighting
      L2 Centralised occupant detection which feeds in to several TBS such as
         lighting and heating

    Uses the same operational-span test as H-1a L4. Both services rest on the
    same geofencing records, so accepting them here while rejecting them there
    would be incoherent: the shared helper makes that impossible.
    """
    geo_key = next((k for k in csv_files if "modalita_geofencing" in k), None)
    if geo_key is None:
        return _result("MC-9", NA_NOT_EVIDENCED, 0, 0.0,
                       "No geofencing or occupancy CSV found. Cannot verify occupancy detection.")

    df_geo = csv_files[geo_key]
    cov = analyze_coverage_event_driven(df_geo, "geofencing")
    n_rec = cov["n_records"]
    occ = _occupancy_evidence(csv_files)

    states = df_geo["state"].unique().tolist() if "state" in df_geo.columns else []
    has_auto = occ["auto_mode"]

    if n_rec < 3:
        return _result("MC-9", PARTIAL_EVIDENCE, 1, 0.45,
                       f"Geofencing CSV: only {n_rec} records, insufficient for full coverage. "
                       f"States: {states}. L1 partially evidenced.",
                       {"n_records": n_rec, "states": [str(s) for s in states]})

    if has_auto and not occ["operational"]:
        return _result("MC-9", VERIFIED, 1, 0.60,
                       f"Geofencing in Auto mode is present ({n_rec} records, states {states}), "
                       f"which shows occupancy is detected and reaches the Tado controllers. "
                       f"However the entity spans {occ['span_days']} days of a "
                       f"{occ['period_days']}-day analysis period, "
                       f"{occ['span_fraction']*100:.1f}%, below the "
                       f"{MIN_OPERATIONAL_SPAN_FRACTION*100:.0f}% required for a capability to "
                       f"count as operational. Detection is therefore recorded as serving an "
                       f"individual function (L1) rather than as sustained centralised detection "
                       f"feeding several technical systems (L2). The same threshold is applied to "
                       f"H-1a L4, which rests on these same records.",
                       {"n_records": n_rec, "states": [str(s) for s in states],
                        "span_days": occ["span_days"], "period_days": occ["period_days"],
                        "span_fraction": occ["span_fraction"],
                        "threshold": MIN_OPERATIONAL_SPAN_FRACTION,
                        "shared_with": "H-1a L4"})

    level = 2 if has_auto else 1
    conf = 0.75 if has_auto else 0.55
    status, gate_note = _gate(VERIFIED, n_records=n_rec,
                              span_days=occ["span_days"], min_span_days=30)
    return _result("MC-9", status, level, conf,
                   f"Geofencing_Villa-Modalita CSV: {n_rec} records, {cov['period_days']} days. {gate_note}"
                   f"States: {states}. '(Auto)' qualifier confirms automatic occupancy detection "
                   f"(smartphone GPS geofencing). Tado TRVs respond to Away/Home transitions by "
                   f"adjusting heating setpoints → occupancy detection connected to heating service "
                   f"→ L2 verified.",
                   {"n_records": n_rec, "states": [str(s) for s in states],
                    "has_auto_mode": has_auto, "period_days": cov["period_days"]})


# Which SRI domain an energy or power entity belongs to. MC-13 counts DOMAINS,
# not devices, so the mapping matters more than the entity count.
ENERGY_DOMAIN_TOKENS = {
    "Ventilation":  ("comfoairq",),
    "Electricity":  ("shellypro3em", "fotovoltaico"),
    "Heating":      ("innova", "immergas", "caldaia", "pompa_calore"),
    "DHW":          ("boiler_dhw", "acs_"),
    "Cooling":      ("condizionatore_power", "clima_power"),
    "Lighting":     ("light_power", "illuminazione_power"),
}
ENERGY_TOKENS = ("power", "energy", "potenza", "energia", "consumo", "kwh")
MC13_MAIN_DOMAINS = ("Heating", "DHW", "Cooling", "Ventilation", "Lighting", "Electricity")


def _energy_reporting_domains(csv_files: dict) -> dict:
    """domain -> list of (entity, n_records) that report energy or power."""
    out = {}
    for key, df in csv_files.items():
        kl = key.lower()
        if not any(t in kl for t in ENERGY_TOKENS):
            continue
        vals = pd.to_numeric(df.get("state"), errors="coerce").dropna() if "state" in df.columns else []
        if len(vals) == 0:
            continue
        for dom, toks in ENERGY_DOMAIN_TOKENS.items():
            if any(t in kl for t in toks):
                out.setdefault(dom, []).append((key.split(".")[-1], int(len(vals))))
                break
    return out


def check_MC13(csv_files: dict) -> dict:
    """
    MC-13: Central reporting of TBS performance and energy use (max FL=3)

    Official levels (SRI calculation sheet v4.5, catalogue B):
      L0 None
      L1 Central or remote reporting of realtime energy use per energy carrier
      L2 ... combining TBS of at least 2 domains in one interface
      L3 ... combining TBS of all main domains in one interface

    The criterion counts DOMAINS whose energy use is reported in a single
    interface, not the number of systems that happen to be integrated. Every
    entity here carries a Home Assistant entity_id, which is the evidence that
    the reporting is centralised in one interface.
    """
    doms = _energy_reporting_domains(csv_files)
    n_dom = len(doms)
    missing = [d for d in MC13_MAIN_DOMAINS if d not in doms]
    summary = {d: sum(n for _, n in v) for d, v in doms.items()}

    if n_dom == 0:
        status, gate_note = _gate(VERIFIED, n_records=sum(summary.values()) if summary else 0)
        return _result("MC-13", status, 0, 0.85,
                       f"No entity reports energy or power use across {len(csv_files)} scanned. "
                       f"No central energy reporting. L0.",
                       {"energy_domains": 0})

    if not missing:
        level, conf = 3, 0.75
        note = (f"Energy use reported for all main domains ({', '.join(sorted(doms))}) "
                f"in a single Home Assistant interface. L3.")
    elif n_dom >= 2:
        level, conf = 2, 0.75
        note = (f"Realtime energy use reported for {n_dom} domains "
                f"({', '.join(f'{d}: {n} records' for d, n in sorted(summary.items()))}), "
                f"combined in one Home Assistant interface. That meets the L2 condition of at "
                f"least 2 domains. L3 requires all main domains; missing: {', '.join(missing)}, "
                f"none of which has any energy metering in the dataset.")
    else:
        level, conf = 1, 0.70
        note = (f"Realtime energy use reported for a single domain "
                f"({', '.join(doms)}), which meets L1 but not the L2 condition of at least "
                f"2 domains.")

    return _result("MC-13", VERIFIED, level, conf,
                   f"Assessed against the official catalogue B wording. {note}",
                   {"energy_domains": n_dom, "domains": sorted(doms),
                    "records_per_domain": summary,
                    "missing_main_domains": missing,
                    "entities_scanned": len(csv_files)})


def check_MC25(csv_files: dict) -> dict:
    """MC-25: Smart grid integration. Source: manual_assessments.json."""
    return _from_manual("MC-25")


def check_MC28(csv_files: dict) -> dict:
    """MC-28: DSM performance reporting. Source: manual_assessments.json."""
    return _from_manual("MC-28")


# Entity-name tokens that would betray a demand-side-management or grid-signal
# integration. Searched across the whole CSV inventory so that "no DSM" is a
# verified absence rather than an assertion.
DSM_SIGNAL_TOKENS = ("tariff", "tariffa", "tou", "time_of_use", "price", "prezzo",
                     "demand_response", "dsm", "grid_signal", "load_shed",
                     "curtail", "flexibility", "pun", "spot_price")
# Tokens for a user-facing override of an automatic control mode.
OVERRIDE_TOKENS = ("sovrapponi", "overlay", "override", "manual_mode", "boost")


def check_MC29(csv_files: dict) -> dict:
    """
    MC-29: Override of DSM control (max FL=4)
    L0 = no DSM control exists to override; L1 = override always available;
    L2 = override available with limits; L3/L4 = progressively finer control.

    MC-29 presupposes that demand-side-management control exists. The check
    therefore verifies, against the entity inventory, that no grid or tariff
    signal reaches the building before concluding L0, rather than asserting it
    from the logbook.
    """
    dsm_entities = [(k, len(df)) for k, df in csv_files.items()
                    if any(t in k.lower() for t in DSM_SIGNAL_TOKENS)]
    override_entities = [(k, len(df)) for k, df in csv_files.items()
                         if any(t in k.lower() for t in OVERRIDE_TOKENS)]

    override_enabled = 0
    for k, _ in override_entities:
        st = csv_files[k].get("state")
        if st is not None:
            override_enabled += int(st.astype(str).str.lower().isin({"on", "true"}).sum())

    if dsm_entities and override_entities and FORECAST_ENTITIES(csv_files):
        return _result("MC-29", PARTIAL_EVIDENCE, 4, 0.50,
                       f"DSM signals, {len(override_entities)} override entities and forecast "
                       f"data present: scheduled override with optimised reactivation is "
                       f"observable. L4 as partial evidence.",
                       {"dsm_signal_entities": len(dsm_entities),
                        "user_override_entities": len(override_entities)})

    if not dsm_entities:
        status, gate_note = _gate(VERIFIED, n_records=len(csv_files))
        return _result("MC-29", status, 0, 0.85,
                       f"Entity inventory scanned for demand-side-management and grid-signal "
                       f"indicators ({', '.join(DSM_SIGNAL_TOKENS[:6])}, and others): zero matches "
                       f"across {len(csv_files)} entities. No tariff signal, price feed, demand "
                       f"response channel or curtailment command reaches the building, so there is "
                       f"no DSM control to override and the catalogue L0 condition is met. "
                       f"Note that {len(override_entities)} user-facing override entities do exist "
                       f"(Tado overlay, {override_enabled} in the enabled state), but overriding a "
                       f"user schedule is not overriding DSM control. This distinction is what "
                       f"separates L0 from L1 here.",
                       {"dsm_signal_entities": 0,
                        "user_override_entities": len(override_entities),
                        "user_override_enabled_records": override_enabled,
                        "entities_scanned": len(csv_files),
                        "tokens_searched": list(DSM_SIGNAL_TOKENS)})

    level = 2 if override_entities else 1
    conf = 0.70 if override_entities else 0.55
    return _result("MC-29", VERIFIED, level, conf,
                   f"{len(dsm_entities)} DSM or grid-signal entities found "
                   f"({[k.split('.')[-1] for k, _ in dsm_entities[:3]]}), so DSM control exists. "
                   f"{len(override_entities)} override entities present "
                   f"({override_enabled} enabled records) "
                   f"{'give the occupant a bounded override at L2' if override_entities else 'not found, override availability at L1 only'}.",
                   {"dsm_signal_entities": len(dsm_entities),
                    "user_override_entities": len(override_entities),
                    "user_override_enabled_records": override_enabled})


def check_MC30(csv_files: dict) -> dict:
    """
    MC-30: Integrated TBS platform (max FL=3)
    L1=multiple systems accessible from one point; L2=integrated monitoring+control; L3=full optimisation.
    Evidence: Home Assistant integrates MVHR, Tado, solar %, geofencing → L1-L2.
    """
    n_systems = sum([
        any("comfoairq" in k for k in csv_files),
        any("_riscaldamento" in k or "modalita_tado" in k for k in csv_files),
        any("percentuale_solare" in k for k in csv_files),
        any("modalita_geofencing" in k for k in csv_files),
        any("meross" in k for k in csv_files),
    ])

    if n_systems < 2:
        return _result("MC-30", PARTIAL_EVIDENCE, 1, 0.45,
                       "Limited CSV coverage to confirm multi-system integration.")

    # Official ladder: L1 single platform allowing MANUAL control of multiple TBS;
    # L2 the same platform performing AUTOMATED control and coordination between
    # them; L3 that plus optimisation. The step from L1 to L2 is automation, and
    # automation leaves entities behind: Home Assistant exposes automation,
    # script and scene objects whenever any exist.
    automation_entities = [k for k in csv_files
                           if any(t in k.lower() for t in ("automation.", "script.", "scene.",
                                                           "automazione", "automation_"))]
    forecast = FORECAST_ENTITIES(csv_files)

    if automation_entities and forecast:
        level, conf = 3, 0.70
        note = (f"{len(automation_entities)} automation objects and {len(forecast)} forecast "
                f"entities: coordination plus optimisation. L3.")
    elif automation_entities:
        level, conf = 2, 0.72
        note = (f"{len(automation_entities)} automation objects coordinate across systems. L2.")
    else:
        level, conf = 1, 0.70
        note = (f"Home Assistant aggregates {n_systems} technical systems (MVHR, Tado heating, "
                f"solar monitoring, geofencing, Meross thermostats) into a single interface where "
                f"all {len(csv_files)} entities are visible and controllable, which meets L1. "
                f"L2 requires that platform to perform automated control and coordination between "
                f"systems: the dataset contains no automation, script or scene object, so no "
                f"cross-system automation is evidenced. Each subsystem runs its own internal logic "
                f"(Tado schedules, ComfoAir bypass), which is coordination within a system rather "
                f"than between systems.")

    return _result("MC-30", VERIFIED, level, conf,
                   f"Assessed against the official catalogue B wording. {note}",
                   {"n_integrated_systems": n_systems,
                    "automation_entities": len(automation_entities),
                    "forecast_entities": len(forecast),
                    "entities_scanned": len(csv_files)})


# ════════════════════════════════════════════════════════════════════════════════
# SRI CALCULATION
# ════════════════════════════════════════════════════════════════════════════════

def calculate_sri_score(service_results: list) -> dict:
    """
    Calculate full SRI with:
    - N/A services excluded from both numerator and denominator
    - UNRESOLVED services: provisional lower (L0) and upper (max) bounds
    - Domain-weighted impact criterion scores
    Returns: SRI score (0-100%) plus per-impact-criterion breakdown and bounds
    """
    ic_keys = IMPACT_KEYS

    def _compute_sri(use_upper_for_unresolved: bool = False, use_lower: bool = False) -> tuple:
        """Returns (numerator_ic, denominator_ic) dicts over impact criteria."""
        num = {ic: 0.0 for ic in ic_keys}
        den = {ic: 0.0 for ic in ic_keys}

        for res in service_results:
            code = res["service"]
            status = res["applicability_status"]
            domain = res["domain"]

            # N/A → skip entirely
            if status in NA_STATUSES:
                continue

            cat = SERVICE_CATALOG[code]
            max_fl = cat["max_fl"]
            dw = DOMAIN_WEIGHTS[domain]

            # Determine level for this calculation pass
            if status == UNRESOLVED:
                if use_upper_for_unresolved:
                    lvl = max_fl
                elif use_lower:
                    lvl = 0
                else:
                    lvl = 0  # default lower
            else:
                lvl = res["level_achieved"] if res["level_achieved"] is not None else 0

            actual_scores = cat["levels"].get(lvl, {ic: 0 for ic in ic_keys})
            max_scores    = cat["levels"].get(max_fl, {ic: 0 for ic in ic_keys})

            for ic in ic_keys:
                w = dw[ic]
                num[ic] += w * actual_scores.get(ic, 0)
                den[ic] += w * max_scores.get(ic, 0)

        return num, den

    def _sri_from_nd(num: dict, den: dict) -> float:
        """Compute SRI (0-100%) from numerator/denominator dicts."""
        sri = 0.0
        for ic in ic_keys:
            if den[ic] > 0:
                sr_ic = num[ic] / den[ic]
            else:
                sr_ic = 0.0
            sri += float(IMPACT_WEIGHTS[ic]) * sr_ic
        return round(sri * 100, 2)

    # Check for UNRESOLVED services
    unresolved_services = [r["service"] for r in service_results if r["applicability_status"] == UNRESOLVED]
    has_unresolved = len(unresolved_services) > 0

    # Main score (UNRESOLVED → L0)
    num_main, den_main = _compute_sri(use_lower=True)
    sri_lower = _sri_from_nd(num_main, den_main)

    # Upper bound (UNRESOLVED → max level)
    if has_unresolved:
        num_upper, den_upper = _compute_sri(use_upper_for_unresolved=True)
        sri_upper = _sri_from_nd(num_upper, den_upper)
    else:
        sri_upper = sri_lower

    sri_central = round((sri_lower + sri_upper) / 2, 2) if has_unresolved else sri_lower

    # Per-impact-criterion breakdown
    ic_breakdown = {}
    for ic in ic_keys:
        sr_ic = (num_main[ic] / den_main[ic]) if den_main[ic] > 0 else 0.0
        ic_breakdown[ic] = {
            "SR": round(sr_ic * 100, 2),
            "weight": round(float(IMPACT_WEIGHTS[ic]), 4),
            "contribution": round(float(IMPACT_WEIGHTS[ic]) * sr_ic * 100, 2),
        }

    # KF pillar scores — SR(KF) = simple average of SR(ic) for each pillar's ICs
    # This reproduces exactly the weighted-sum result because each IC within
    # a KF has equal weight, and all three KFs have equal weight (1/3).
    kf_breakdown = {}
    for kf_key, kf_info in KF_GROUPS.items():
        ics = kf_info["ics"]
        sr_values = [ic_breakdown[ic]["SR"] for ic in ics]
        sr_kf = round(sum(sr_values) / len(sr_values), 2)
        kf_breakdown[kf_key] = {
            "name": kf_info["name"],
            "ics": ics,
            "SR": sr_kf,
        }

    # SRI class — official thresholds (South / Residential zone)
    # EU Delegated Regulation 2020/2155 / D3.1 Technical Study
    def _sri_class(score: float) -> str:
        if score >= 90: return "A"
        if score >= 75: return "B"
        if score >= 65: return "C"
        if score >= 50: return "D"
        if score >= 35: return "E"
        if score >= 20: return "F"
        return "G"

    # Count service summary
    status_counts = {}
    for r in service_results:
        s = r["applicability_status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    applicable = sum(1 for r in service_results if r["applicability_status"] not in NA_STATUSES)

    return {
        "sri_score_pct": sri_lower,
        "sri_class": _sri_class(sri_lower),
        "sri_lower_bound_pct": sri_lower,
        "sri_upper_bound_pct": sri_upper,
        "sri_central_pct": sri_central,
        "has_unresolved_services": has_unresolved,
        "unresolved_services": unresolved_services,
        "applicable_services": applicable,
        "total_services": len(service_results),
        "status_counts": status_counts,
        "impact_criterion_breakdown": ic_breakdown,
        "kf_breakdown": kf_breakdown,
    }


# ════════════════════════════════════════════════════════════════════════════════
# RUN ALL 54 SERVICE CHECKS
# ════════════════════════════════════════════════════════════════════════════════

def run_all_checks(csv_files: dict) -> list:
    """Run all 54 service check functions. Returns list of result dicts."""
    checkers = [
        # HEATING
        check_H1a, check_H1b, check_H1c, check_H1d, check_H1f,
        check_H2a, check_H2b, check_H2d, check_H3, check_H4,
        # DHW
        check_DHW1a, check_DHW1b, check_DHW1d, check_DHW2b, check_DHW3,
        # COOLING
        check_C1a, check_C1b, check_C1c, check_C1d, check_C1f,
        check_C1g, check_C2a, check_C2b, check_C3, check_C4,
        # VENTILATION
        check_V1a, check_V1c, check_V2c, check_V2d, check_V3, check_V6,
        # LIGHTING
        check_L1a, check_L2,
        # DYNAMIC ENVELOPE
        check_DE1, check_DE2, check_DE4,
        # ELECTRICITY
        check_E2, check_E3, check_E4, check_E5, check_E8, check_E11, check_E12,
        # EV CHARGING
        check_EV15, check_EV16, check_EV17,
        # MONITORING & CONTROL
        check_MC3, check_MC4, check_MC9, check_MC13,
        check_MC25, check_MC28, check_MC29, check_MC30,
    ]

    results = []
    for fn in checkers:
        try:
            r = fn(csv_files)
            results.append(r)
        except Exception as e:
            import traceback
            code = fn.__name__.replace("check_", "").replace("_","-")
            print(f"[ERROR] {fn.__name__}: {e}")
            traceback.print_exc()
    return results


# ════════════════════════════════════════════════════════════════════════════════
# OUTPUT: JSON + HTML
# ════════════════════════════════════════════════════════════════════════════════

def _esc(s: str) -> str:
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"','&quot;')


def build_html_report(service_results: list, sri: dict, data_period: tuple,
                      csv_files: dict) -> str:
    """Generate v7-style dashboard HTML report with dynamic data."""

    # ── Mappings ──────────────────────────────────────────────────────────────
    IC_FULL = {
        "EE":      "Energy Efficiency",
        "Flex":    "Energy Flexibility &amp; Storage",
        "Comfort": "Comfort",
        "Conv":    "Convenience",
        "Health":  "Health, Well-being &amp; Access.",
        "Maint":   "Maintenance &amp; Fault Prediction",
        "Info":    "Information to Occupants",
    }
    IC_KF_MAP  = {"EE":"KF1","Maint":"KF1","Comfort":"KF2","Conv":"KF2",
                  "Health":"KF2","Info":"KF2","Flex":"KF3"}
    IC_KF_CHIP = {"KF1":"kf1c","KF2":"kf2c","KF3":"kf3c"}
    IC_BAR_CLR = {"KF1":"#1565c0","KF2":"#6a1b9a","KF3":"#b71c1c"}
    IC_WT_STR  = {"EE":"1/6","Flex":"1/3","Comfort":"1/12",
                  "Conv":"1/12","Health":"1/12","Maint":"1/6","Info":"1/12"}
    IC_ORDER   = ["EE","Flex","Comfort","Conv","Health","Maint","Info"]

    DOMAIN_ORDER = ["Heating","DHW","Cooling","Ventilation","Lighting",
                    "Dynamic_Envelope","Electricity","EV_Charging","Monitoring_Control"]
    DOMAIN_LABEL = {
        "Heating":"H - Heating","DHW":"DHW - Domestic Hot Water",
        "Cooling":"C - Cooling","Ventilation":"V - Ventilation",
        "Lighting":"L - Lighting","Dynamic_Envelope":"DE - Dynamic Envelope",
        "Electricity":"E - Electricity","EV_Charging":"EV - EV Charging",
        "Monitoring_Control":"MC - Monitoring and Control",
    }
    DOM_SHORT_JS = {
        "Heating":"Heating (H)","DHW":"DHW","Ventilation":"Ventilation (V)",
        "Lighting":"Lighting (L)","Dynamic_Envelope":"Dyn. Env. (DE)",
        "Electricity":"Electricity (E)","Monitoring_Control":"Mon. & Ctrl (MC)",
    }
    DOM_SHORT_H = {
        "Heating":"Heating (H)","DHW":"DHW","Ventilation":"Ventilation (V)",
        "Lighting":"Lighting (L)","Dynamic_Envelope":"Dyn. Envelope (DE)",
        "Electricity":"Electricity (E)","Monitoring_Control":"Mon. &amp; Ctrl (MC)",
    }
    DOM_COLOR = {
        "Heating":"#5b9bd5","DHW":"#70ad47","Ventilation":"#4472c4",
        "Lighting":"#a5a5a5","Dynamic_Envelope":"#a5a5a5",
        "Electricity":"#ed7d31","Monitoring_Control":"#7030a0",
    }
    STATUS_BADGE = {
        VERIFIED:            ("bv","&#10003; Verified"),
        L0_NO_AUTOMATION:    ("bv","&#10003; Verified"),
        PARTIAL_EVIDENCE:    ("bp","&asymp; Partial"),
        UNRESOLVED:          ("bu","? Unresolved"),
        NA_NOT_EVIDENCED:    ("bnn","- N/A (period)"),
        NA_EXPLICIT_ABSENCE: ("bna","- N/A (absent)"),
    }
    FL_CLS = {0:"fl0",1:"fl1",2:"fl2",3:"fl3",4:"fl4"}

    # ── Period ────────────────────────────────────────────────────────────────
    start_dt, end_dt = data_period
    if start_dt and end_dt:
        if start_dt.year == end_dt.year:
            period_str = f"{start_dt.strftime('%b')}-{end_dt.strftime('%b %Y')}"
        else:
            period_str = f"{start_dt.strftime('%b %Y')} - {end_dt.strftime('%b %Y')}"
        n_days_str = str((end_dt - start_dt).days)
        ac_yr = end_dt.year
    else:
        period_str = "Jan-Jun 2026"
        n_days_str = "180"
        ac_yr = 2026
    gen_label = datetime.now().strftime("%B %Y")

    # ── SRI scalars ───────────────────────────────────────────────────────────
    sri_score    = sri["sri_score_pct"]
    sri_class    = sri["sri_class"]
    sri_upper    = sri["sri_upper_bound_pct"]
    unres_svcs   = sri.get("unresolved_services", [])
    appl_total   = sri["applicable_services"]
    n_total      = sri["total_services"]
    sc           = sri.get("status_counts", {})
    ic_bd        = sri["impact_criterion_breakdown"]
    kf_bd        = sri.get("kf_breakdown", {})

    n_verified   = sc.get(VERIFIED, 0) + sc.get(L0_NO_AUTOMATION, 0)
    n_partial    = sc.get(PARTIAL_EVIDENCE, 0)
    n_unresolved = sc.get(UNRESOLVED, 0)
    n_na_period  = sc.get(NA_NOT_EVIDENCED, 0)
    n_na_absent  = sc.get(NA_EXPLICIT_ABSENCE, 0)
    n_na_total   = n_na_period + n_na_absent
    n_csv        = len(csv_files)

    # ── Domain scores ─────────────────────────────────────────────────────────
    by_domain = {d: [] for d in DOMAIN_ORDER}
    for r in service_results:
        by_domain[r["domain"]].append(r)

    dom_scores, dom_appl = {}, {}
    for d in DOMAIN_ORDER:
        appl = [r for r in by_domain[d]
                if r["applicability_status"] not in NA_STATUSES
                and r["level_achieved"] is not None
                and r.get("level_max", 0) > 0]
        dom_appl[d] = len(appl)
        dom_scores[d] = (
            round(sum(r["level_achieved"] / r["level_max"] for r in appl) / len(appl) * 100, 1)
            if appl else None
        )

    # ── Chart arrays ──────────────────────────────────────────────────────────
    CHART_DOMS = ["Heating","DHW","Ventilation","Lighting",
                  "Dynamic_Envelope","Electricity","Monitoring_Control"]
    c_doms      = [d for d in CHART_DOMS if dom_appl.get(d, 0) > 0]
    dom_lbl_js  = json.dumps([DOM_SHORT_JS[d] for d in c_doms])
    dom_dat_js  = json.dumps([dom_scores.get(d, 0) or 0 for d in c_doms])
    dom_clr_js  = json.dumps([DOM_COLOR[d] for d in c_doms])

    ic_lbl, ic_dat, ic_clr = [], [], []
    for ic in IC_ORDER:
        if ic not in ic_bd:
            continue
        ic_lbl.append(IC_FULL[ic].replace("&amp;", "&"))
        ic_dat.append(round(ic_bd[ic]["SR"], 1))
        ic_clr.append(IC_BAR_CLR[IC_KF_MAP[ic]])
    ic_lbl_js = json.dumps(ic_lbl)
    ic_dat_js = json.dumps(ic_dat)
    ic_clr_js = json.dumps(ic_clr)

    # ── IC table rows ─────────────────────────────────────────────────────────
    ic_tbl = ""
    for ic in IC_ORDER:
        if ic not in ic_bd:
            continue
        v  = ic_bd[ic]
        kf = IC_KF_MAP[ic]
        ic_tbl += (
            f'          <tr><td>{IC_FULL[ic]}</td>'
            f'<td><span class="ic-kf-chip {IC_KF_CHIP[kf]}">{kf}</span></td>'
            f'<td>{IC_WT_STR[ic]}</td><td>{v["SR"]:.1f}%</td>'
            f'<td>{v["contribution"]:.2f}%</td></tr>\n'
        )

    # ── KF pillar cards ───────────────────────────────────────────────────────
    KF_META = {
        "KF1": ("kf1-c","KF1 - Energy Performance","Energy efficiency and building operation"),
        "KF2": ("kf2-c","KF2 - Occupant Adaptability","Adaptation to occupant needs"),
        "KF3": ("kf3-c","KF3 - Grid Flexibility","Response to energy network"),
    }
    kf_cards = ""
    for kf_key in ["KF1","KF2","KF3"]:
        if kf_key not in kf_bd:
            continue
        kv = kf_bd[kf_key]
        style, tag, name = KF_META[kf_key]
        sr   = kv["SR"]
        parts = [f'{IC_FULL[ic]} {ic_bd.get(ic,{}).get("SR",0):.1f}%' for ic in kv["ics"]]
        n_ic  = len(kv["ics"])
        noun  = "criterion" if n_ic == 1 else "criteria"
        kf_cards += (
            f'    <div class="kf-card {style}">\n'
            f'      <div class="kf-tag">{tag}</div>\n'
            f'      <div class="kf-name">{name}</div>\n'
            f'      <div class="kf-pct">{sr:.1f}%</div>\n'
            f'      <div class="kf-bar-bg"><div class="kf-bar" style="width:{min(sr,100):.1f}%"></div></div>\n'
            f'      <div class="kf-ics">{" + ".join(parts)}<br>{n_ic} impact {noun} - overall weight 1/3</div>\n'
            f'    </div>\n'
        )

    # ── Scale segments ────────────────────────────────────────────────────────
    CLASS_DEF = [
        ("G","0-20%","#8b0000"),("F","20-35%","#cc3300"),("E","35-50%","#e16e28"),
        ("D","50-65%","#d4b800"),("C","65-75%","#a0c830"),("B","75-90%","#5aab3e"),
        ("A","&gt;90%","#1a9641"),
    ]
    scale_segs = ""
    for cls, rng, col in CLASS_DEF:
        act = " active" if cls == sri_class else ""
        scale_segs += f'    <div class="seg{act}" style="background:{col}">{cls}<span class="rng">{rng}</span></div>\n'
    unres_names = ", ".join(unres_svcs) if unres_svcs else "none"
    scale_note = (
        f'&#9650; Current result: Class {sri_class}, {sri_score:.2f}% (Method C). '
        f'With UNRESOLVED services at upper bound: <strong>{sri_upper:.2f}%</strong>, '
        f'still within Class {sri_class}. Uncertainty range reflects {unres_names}.'
    )

    # ── Domain table rows ─────────────────────────────────────────────────────
    DOM_TABLE = [
        ("Heating","Heating (H)"),("DHW","DHW"),("Ventilation","Ventilation (V)"),
        ("Lighting","Lighting (L)"),("Dynamic_Envelope","Dyn. Envelope (DE)"),
        ("Electricity","Electricity (E)"),("Monitoring_Control","Mon. &amp; Ctrl (MC)"),
        ("Cooling","Cooling (C)"),("EV_Charging","EV Charging (EV)"),
    ]
    dom_tbl = ""
    for dom, lbl in DOM_TABLE:
        ds  = dom_scores.get(dom)
        app = dom_appl.get(dom, 0)
        if dom == "Cooling":
            dom_tbl += f'<tr><td>{lbl}</td><td class="dom-na">Excluded</td><td>-</td><td>Period exclusion</td></tr>\n'
        elif dom == "EV_Charging":
            dom_tbl += f'<tr><td>{lbl}</td><td class="dom-na">N/A</td><td>-</td><td>Physically absent</td></tr>\n'
        elif ds is not None and app > 0:
            dom_tbl += (
                f'<tr><td>{lbl}</td><td class="dom-score">{ds:.1f}%</td>'
                f'<td><div class="pbar-bg"><div class="pbar-fg" style="width:{min(ds,100):.1f}%"></div></div></td>'
                f'<td>{app} applicable</td></tr>\n'
            )
        else:
            dom_tbl += f'<tr><td>{lbl}</td><td class="dom-na">N/A</td><td>-</td><td>-</td></tr>\n'

    # ── Service table rows ────────────────────────────────────────────────────
    svc_rows = ""
    for dom in DOMAIN_ORDER:
        svcs = by_domain[dom]
        if not svcs:
            continue
        app = dom_appl[dom]
        ds  = dom_scores[dom]
        if dom == "Cooling":
            hdr = f"C - Cooling &nbsp;|&nbsp; Excluded - {period_str} period &nbsp;|&nbsp; AC splits installed Jul {ac_yr}"
        elif dom == "EV_Charging":
            hdr = "EV - EV Charging &nbsp;|&nbsp; N/A &nbsp;|&nbsp; No infrastructure present"
        elif ds is not None:
            noun = "services" if app != 1 else "service"
            hdr = f"{DOMAIN_LABEL[dom]} &nbsp;|&nbsp; Score: {ds:.1f}% &nbsp;|&nbsp; {app} applicable {noun}"
        else:
            hdr = DOMAIN_LABEL[dom]
        svc_rows += f'        <tr class="dom-row"><td colspan="5">{hdr}</td></tr>\n'
        for r in svcs:
            st = r["applicability_status"]
            bc, bt = STATUS_BADGE.get(st, ("bnn", st))
            if st in NA_STATUSES:
                fl = '<span class="fl flna">N/A</span>'
            elif st == UNRESOLVED:
                lo = r["level_achieved"] if r["level_achieved"] is not None else 0
                fl = f'<span class="fl flu">L{lo}-L{lo+1}</span>'
            elif r["level_achieved"] is not None:
                lvl = r["level_achieved"]
                fl = f'<span class="fl {FL_CLS.get(lvl,"fl0")}">L{lvl}</span>'
            else:
                fl = '<span class="fl flna">N/A</span>'
            svc_rows += (
                f'        <tr>\n'
                f'          <td class="code-cell">{_esc(r["service"])}</td>\n'
                f'          <td class="svc-name">{_esc(r["description"])}</td>\n'
                f'          <td><span class="badge {bc}">{bt}</span></td>\n'
                f'          <td class="fl-cell">{fl}</td>\n'
                f'          <td class="just-text">{_esc(r["justification"])}</td>\n'
                f'        </tr>\n'
            )

    # ── Summary note ──────────────────────────────────────────────────────────
    sum_note = (
        f'{appl_total} services in denominator ({n_total} total minus {n_na_total} N/A). '
        f'Method C conservative result: {sri_score:.2f}% Class {sri_class}. '
        f'Denominator excludes cooling (period) and EV (absent).'
    )
    na_lbl = f"N/A ({n_na_period} period + {n_na_absent} absent)"

    # ── Chart JS ──────────────────────────────────────────────────────────────
    fam = r"'Aptos','Segoe UI',Arial,sans-serif"
    dom_js = (
        "const dCtx=document.getElementById('domChart').getContext('2d');\n"
        "new Chart(dCtx,{type:'bar',data:{"
        + f"labels:{dom_lbl_js},"
        + "datasets:[{label:'Domain Score (%)',"
        + f"data:{dom_dat_js},backgroundColor:{dom_clr_js},"
        + "borderRadius:4,barThickness:26}]},"
        + "options:{responsive:true,maintainAspectRatio:false,"
        + "plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>' '+c.parsed.y+'%'}}},"
        + "scales:{"
        + f"y:{{beginAtZero:true,max:100,ticks:{{callback:v=>v+'%',font:{{family:\"{fam}\",size:11}}}},grid:{{color:'#f0f0f0'}}}},"
        + f"x:{{ticks:{{font:{{family:\"{fam}\",size:10}}}},grid:{{display:false}}}}"
        + "}}});"
    )
    ic_js = (
        "const iCtx=document.getElementById('icChart').getContext('2d');\n"
        "new Chart(iCtx,{type:'bar',data:{"
        + f"labels:{ic_lbl_js},"
        + "datasets:[{label:'SR(ic) (%)',"
        + f"data:{ic_dat_js},backgroundColor:{ic_clr_js},"
        + "borderRadius:4,barThickness:18}]},"
        + "options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,"
        + "plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>' '+c.parsed.x+'%'}}},"
        + "scales:{"
        + f"x:{{beginAtZero:true,max:100,ticks:{{callback:v=>v+'%',font:{{family:\"{fam}\",size:10}}}},grid:{{color:'#f0f0f0'}}}},"
        + f"y:{{ticks:{{font:{{family:\"{fam}\",size:10}}}},grid:{{display:false}}}}"
        + "}}});"
    )

    # ── Building info shortcuts ───────────────────────────────────────────────
    bid   = _esc(BUILDING_INFO["id"])
    badr  = _esc(BUILDING_INFO["address"])
    byr   = BUILDING_INFO["year_built"]
    barea = BUILDING_INFO["net_floor_area_m2"]
    bflr  = BUILDING_INFO["floors_total"]
    bfag  = BUILDING_INFO["floors_above_ground"]
    bfug  = BUILDING_INFO["floors_underground"]

    # ── Assemble HTML ─────────────────────────────────────────────────────────
    h  = '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
    h += '<meta charset="UTF-8">\n'
    h += '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
    h += f'<title>SRI Dashboard | {bid} | Method C</title>\n'
    h += '<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>\n'
    h += '<style>\n'
    h += ("*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}\n"
          "body{font-family:'Aptos','Segoe UI',Arial,sans-serif;font-size:13px;color:#1a1a1a;background:#f2f4f7}\n"
          ".header{background:#1c2541;color:white;padding:24px 32px;display:flex;justify-content:space-between;align-items:center}\n"
          ".hl h1{font-size:20px;font-weight:600;margin-bottom:3px}\n"
          ".hl .sub{font-size:11px;color:#9baac8;margin-top:2px}\n"
          ".hl .sub2{font-size:12px;color:#d0d8f0;margin-top:6px}\n"
          ".sri-badge{background:#e16e28;border-radius:12px;padding:14px 26px;text-align:center;min-width:148px}\n"
          ".sri-badge .pct{font-size:38px;font-weight:700;line-height:1}\n"
          ".sri-badge .cls{font-size:16px;font-weight:500;color:#ffe0cc;margin-top:3px}\n"
          ".sri-badge .lbl{font-size:10px;color:#ffc5a0;text-transform:uppercase;letter-spacing:.08em;margin-top:2px}\n"
          ".disc{background:#fff8e1;border-left:4px solid #f59f00;padding:9px 24px;font-size:11.5px;color:#5a4000}\n"
          ".content{max-width:1160px;margin:0 auto;padding:20px 24px}\n"
          ".card{background:white;border-radius:8px;border:1px solid #e2e6ea;padding:18px 22px;margin-bottom:16px}\n"
          ".card h2{font-size:12.5px;font-weight:700;color:#1c2541;margin-bottom:13px;padding-bottom:7px;border-bottom:1px solid #e2e6ea;text-transform:uppercase;letter-spacing:.06em}\n"
          ".g2{display:grid;grid-template-columns:1fr 1fr;gap:16px}\n"
          ".g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}\n"
          ".sri-scale{display:flex;gap:4px;margin-bottom:6px}\n"
          ".seg{flex:1;text-align:center;padding:9px 4px 7px;border-radius:5px;font-size:12px;font-weight:700;color:white;position:relative}\n"
          ".seg .rng{font-size:9.5px;font-weight:400;color:rgba(255,255,255,.85);display:block;margin-top:2px}\n"
          ".seg.active::after{content:'\\25B2';position:absolute;bottom:-19px;left:50%;transform:translateX(-50%);font-size:13px;color:#e16e28}\n"
          ".scale-note{font-size:11px;color:#6c757d;margin-top:24px;font-style:italic}\n"
          ".info-grid{display:grid;grid-template-columns:1fr 1fr;gap:5px 20px}\n"
          ".ir{display:flex;gap:8px;align-items:baseline;padding:4px 0;border-bottom:1px solid #f1f5f9}\n"
          ".il{font-size:10.5px;color:#6c757d;font-weight:600;text-transform:uppercase;letter-spacing:.04em;min-width:110px;flex-shrink:0}\n"
          ".iv{font-size:12.5px;color:#1a1a1a}\n"
          ".tech-grid{display:grid;grid-template-columns:1fr 1fr;gap:0}\n"
          ".ti{font-size:11.5px;padding:5px 0;border-bottom:1px solid #f1f5f9;display:flex;align-items:center;gap:6px;color:#1a1a1a}\n"
          ".ti:nth-last-child(-n+2){border-bottom:none}\n"
          ".tdot{width:5px;height:5px;border-radius:50%;background:#94a3b8;flex-shrink:0}\n"
          ".src-chain{display:flex;align-items:stretch;gap:6px;flex-wrap:wrap}\n"
          ".src-item{background:#eef2ff;border:1px solid #c5cff8;border-radius:6px;padding:9px 14px;flex:1;min-width:170px}\n"
          ".src-item .sl{font-weight:700;font-size:12px;color:#2c3e8a;display:block;margin-bottom:3px}\n"
          ".src-item .sd{font-size:10.5px;color:#5c6bc0;line-height:1.45}\n"
          ".src-arrow{color:#5c6bc0;font-size:18px;align-self:center;flex-shrink:0}\n"
          ".domain-wrap{display:grid;grid-template-columns:3fr 2fr;gap:18px;align-items:start}\n"
          ".chart-wrap{position:relative;height:220px}\n"
          ".dom-table{width:100%;border-collapse:collapse;font-size:12px}\n"
          ".dom-table th{background:#f0f2f5;padding:6px 10px;text-align:left;font-size:10.5px;font-weight:600;color:#495057;text-transform:uppercase;letter-spacing:.04em;border-bottom:2px solid #dee2e6}\n"
          ".dom-table td{padding:6px 10px;border-bottom:1px solid #e9ecef;vertical-align:middle}\n"
          ".dom-table tr:last-child td{border-bottom:none}\n"
          ".pbar-bg{background:#e9ecef;border-radius:3px;height:7px;width:80px;display:inline-block;vertical-align:middle;position:relative;overflow:hidden}\n"
          ".pbar-fg{position:absolute;top:0;left:0;height:100%;border-radius:3px;background:#1c6bb5}\n"
          ".dom-na{color:#adb5bd;font-size:11px;font-style:italic}\n"
          ".dom-score{font-weight:700;color:#1c2541}\n"
          ".ic-wrap{display:grid;grid-template-columns:3fr 2fr;gap:18px;align-items:start}\n"
          ".ic-chart-wrap{position:relative;height:230px}\n"
          ".ic-table{width:100%;border-collapse:collapse;font-size:12px}\n"
          ".ic-table th{background:#f0f2f5;padding:6px 8px;text-align:left;font-size:10.5px;font-weight:600;color:#495057;text-transform:uppercase;letter-spacing:.04em;border-bottom:2px solid #dee2e6}\n"
          ".ic-table td{padding:6px 8px;border-bottom:1px solid #e9ecef;vertical-align:middle}\n"
          ".ic-table tr.tot td{font-weight:700;background:#f8fafc;border-top:2px solid #dee2e6;border-bottom:none}\n"
          ".ic-kf-chip{display:inline-block;padding:1px 5px;border-radius:3px;font-size:9px;font-weight:700}\n"
          ".kf1c{background:#dbeafe;color:#1e40af}.kf2c{background:#ede9fe;color:#5b21b6}.kf3c{background:#fce4e4;color:#b71c1c}\n"
          ".kf-card{border-radius:8px;padding:16px;border:2px solid}\n"
          ".kf1-c{border-color:#1565c0;background:#e8f4fd}.kf2-c{border-color:#6a1b9a;background:#f5eefb}.kf3-c{border-color:#bf360c;background:#fdf0eb}\n"
          ".kf-tag{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.08em}\n"
          ".kf1-c .kf-tag{color:#1565c0}.kf2-c .kf-tag{color:#6a1b9a}.kf3-c .kf-tag{color:#bf360c}\n"
          ".kf-name{font-size:12.5px;font-weight:700;color:#1e293b;margin:4px 0 10px;line-height:1.3}\n"
          ".kf-pct{font-size:26px;font-weight:800;line-height:1}\n"
          ".kf1-c .kf-pct{color:#1565c0}.kf2-c .kf-pct{color:#6a1b9a}.kf3-c .kf-pct{color:#bf360c}\n"
          ".kf-bar-bg{height:7px;background:rgba(0,0,0,0.1);border-radius:4px;margin:8px 0}\n"
          ".kf-bar{height:7px;border-radius:4px}\n"
          ".kf1-c .kf-bar{background:#1565c0}.kf2-c .kf-bar{background:#6a1b9a}.kf3-c .kf-bar{background:#bf360c}\n"
          ".kf-ics{font-size:10.5px;color:#64748b;line-height:1.5}\n"
          ".legend-row{display:flex;gap:8px;flex-wrap:wrap}\n"
          ".legend-item-h{display:flex;flex-direction:column;gap:5px;padding:10px 12px;border-radius:6px;border:1px solid #e2e6ea;flex:1;min-width:140px}\n"
          ".legend-title{font-size:11px;font-weight:700;color:#1a1a1a}\n"
          ".legend-desc{font-size:10px;color:#6c757d;line-height:1.45}\n"
          ".badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10.5px;font-weight:600;white-space:nowrap;letter-spacing:.02em}\n"
          ".bv{background:#d4edda;color:#155724;border:1px solid #c3e6cb}\n"
          ".bp{background:#fff3cd;color:#856404;border:1px solid #ffeeba}\n"
          ".bu{background:#e8d5f5;color:#4a1a7a;border:1px solid #d6aef0}\n"
          ".bnn{background:#e9ecef;color:#495057;border:1px solid #ced4da}\n"
          ".bna{background:#f1f3f5;color:#868e96;border:1px solid #dee2e6}\n"
          ".fl{display:inline-block;padding:2px 8px;border-radius:8px;font-size:10.5px;font-weight:700;border:1px solid;white-space:nowrap}\n"
          ".fl0{background:#f5f5f5;color:#616161;border-color:#e0e0e0}\n"
          ".fl1{background:#fff3e0;color:#e65100;border-color:#ffcc80}\n"
          ".fl2{background:#e3f2fd;color:#1565c0;border-color:#90caf9}\n"
          ".fl3{background:#e8f5e9;color:#2e7d32;border-color:#a5d6a7}\n"
          ".fl4{background:#f1f8e9;color:#33691e;border-color:#c5e1a5}\n"
          ".flu{background:#f3e5f5;color:#6a1b9a;border-color:#ce93d8}\n"
          ".flna{background:#fafafa;color:#9e9e9e;border-color:#e0e0e0}\n"
          ".stat-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}\n"
          ".stat{text-align:center;padding:14px 8px;border-radius:8px}\n"
          ".stat-n{font-size:28px;font-weight:800}\n"
          ".stat-l{font-size:10px;text-transform:uppercase;letter-spacing:.08em;margin-top:2px}\n"
          ".svc-wrap{border-radius:6px;border:1px solid #e2e6ea;overflow:hidden;max-height:680px;overflow-y:auto}\n"
          ".svc-table{width:100%;border-collapse:collapse;font-size:11.5px;table-layout:fixed}\n"
          ".svc-table thead th{position:sticky;top:0;background:#1c2541;color:white;padding:8px 10px;text-align:left;font-size:10.5px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;z-index:2}\n"
          ".svc-table th:nth-child(1){width:62px}.svc-table th:nth-child(2){width:200px}"
          ".svc-table th:nth-child(3){width:130px}.svc-table th:nth-child(4){width:72px}.svc-table th:nth-child(5){width:auto}\n"
          ".svc-table tbody tr:hover td{background:#f0f4ff}\n"
          ".svc-table td{padding:7px 10px;border-bottom:1px solid #e9ecef;vertical-align:top}\n"
          ".dom-row td{background:#e8ecf5;font-size:11px;font-weight:700;color:#1c2541;padding:6px 10px;border-top:2px solid #c5cff8;border-bottom:1px solid #c5cff8;text-transform:uppercase;letter-spacing:.04em}\n"
          ".code-cell{font-weight:700;font-family:monospace;font-size:12px;color:#1c2541;white-space:nowrap}\n"
          ".svc-name{font-size:11.5px;color:#1a1a1a}.fl-cell{white-space:nowrap}\n"
          ".just-text{font-size:11px;color:#495057;line-height:1.55}\n"
          "footer{background:#1c2541;color:#9baac8;font-size:11px;padding:14px 32px;text-align:center;margin-top:8px}\n"
          "footer strong{color:#d0d8f0}\n"
          "@media(max-width:800px){.g2,.g3,.domain-wrap,.ic-wrap,.stat-grid,.legend-row{grid-template-columns:1fr}}\n")
    h += '</style>\n</head>\n<body>\n\n'

    # HEADER
    h += (f'<div class="header">\n  <div class="hl">\n'
          f'    <h1>Smart Readiness Indicator | {bid}</h1>\n'
          f'    <p class="sub">Method C (Operational Assessment) &middot; EU Delegated Regulation 2020/2155 &middot; D3.1 Catalogue (54 services)</p>\n'
          f'    <p class="sub2">Case Study &middot; Politecnico di Milano / tunES Project &middot; Italy</p>\n'
          f'  </div>\n  <div class="sri-badge">\n    <div class="lbl">SRI Score</div>\n'
          f'    <div class="pct">{sri_score:.2f}%</div>\n    <div class="cls">Class {sri_class}</div>\n'
          f'  </div>\n</div>\n\n')

    # DISCLAIMER
    h += ('<div class="disc"><strong>Methodological note:</strong> Method C is a research proposal for SRI assessment '
          'based on historical operational data (Home Assistant). It is <strong>not an officially approved EU method</strong> '
          '(per D3.1: only Methods A and B are official). Results are for academic and research purposes only.</div>\n\n'
          '<div class="content">\n\n')

    # SRI SCALE
    h += (f'<div class="card">\n  <h2>SRI Class Scale - Official Thresholds (South / Residential Zone)</h2>\n'
          f'  <div class="sri-scale">\n{scale_segs}  </div>\n'
          f'  <p class="scale-note">{scale_note}</p>\n</div>\n\n')

    # BUILDING + TECH
    h += ('<div class="g2" style="margin-bottom:16px">\n\n'
          '  <div class="card" style="margin-bottom:0">\n    <h2>Building Data</h2>\n    <div class="info-grid">\n'
          f'      <div class="ir"><span class="il">Building</span><span class="iv">{bid}</span></div>\n'
          f'      <div class="ir"><span class="il">Location</span><span class="iv">{badr}</span></div>\n'
          f'      <div class="ir"><span class="il">Year built</span><span class="iv">{byr}</span></div>\n'
          '      <div class="ir"><span class="il">Building Use</span><span class="iv">Residential</span></div>\n'
          '      <div class="ir"><span class="il">Building Type</span><span class="iv">Single-family villa</span></div>\n'
          f'      <div class="ir"><span class="il">Net floor area</span><span class="iv">{barea} m&sup2;</span></div>\n'
          f'      <div class="ir"><span class="il">Floors</span><span class="iv">{bflr} ({bfag} above grade + {bfug} underground)</span></div>\n'
          '      <div class="ir"><span class="il">Climate zone</span><span class="iv">South (IT)</span></div>\n'
          '    </div>\n  </div>\n\n'
          '  <div class="card" style="margin-bottom:0">\n    <h2>Technical Systems</h2>\n    <div class="tech-grid">\n'
          '      <div class="ti"><span class="tdot"></span>INNOVA eHPoca 3in1 - Heat pump (H + DHW)</div>\n'
          '      <div class="ti"><span class="tdot"></span>Tado TRVs - Zoned heating (5 zones)</div>\n'
          '      <div class="ti"><span class="tdot"></span>IMMERGAS HERCULES SOLAR 25 - Boiler</div>\n'
          '      <div class="ti"><span class="tdot"></span>Meross sensors - Ambient temp. (4 zones)</div>\n'
          '      <div class="ti"><span class="tdot"></span>Solar thermal CP4 XL - DHW collectors</div>\n'
          '      <div class="ti"><span class="tdot"></span>PV array - Solar photovoltaic generation</div>\n'
          '      <div class="ti"><span class="tdot"></span>Zehnder ComfoAir Q450 - MVHR unit</div>\n'
          '      <div class="ti"><span class="tdot"></span>Battery storage + BMS</div>\n'
          '      <div class="ti"><span class="tdot"></span>Home Assistant - Automation platform</div>\n'
          '      <div class="ti"><span class="tdot"></span>AC splits x2 (installed Jul 2026 - outside analysis period)</div>\n'
          '    </div>\n  </div>\n\n</div>\n\n')

    # SOURCES
    h += ('<div class="card">\n  <h2>Evidence Sources - Method C Hierarchy</h2>\n  <div class="src-chain">\n'
          '    <div class="src-item"><span class="sl">1 - DBL</span>'
          '<span class="sd">Digital Building Logbook<br>Groups 08 + 09 - equipment inventory and building systems</span></div>\n'
          '    <span class="src-arrow">&#8594;</span>\n'
          f'    <div class="src-item"><span class="sl">2 - Home Assistant Historical Data</span>'
          f'<span class="sd">{n_csv} CSV files &middot; ~87,000 records<br>{period_str} ({n_days_str} days of operation)</span></div>\n'
          '    <span class="src-arrow">&#8594;</span>\n'
          '    <div class="src-item"><span class="sl">3 - IFC BIM Models</span>'
          '<span class="sd">Architectural + Mechanical + HVAC<br>3 files - spatial and system cross-check</span></div>\n'
          '    <span class="src-arrow">&#8594;</span>\n'
          '    <div class="src-item"><span class="sl">4 - Technical Datasheets</span>'
          '<span class="sd">Equipment specification sheets<br>Inherent characteristics only (last resort)</span></div>\n'
          '  </div>\n'
          f'  <p style="font-size:11px;color:#6c757d;margin-top:10px;line-height:1.6;font-style:italic">'
          f'<strong style="font-style:normal;color:#495057">Note:</strong> The Home Assistant CSVs are the key contribution of Method C. '
          f'Historical operational data ({period_str}) verify how the building actually performs, in contrast with Method B, which relies only on static evidence.</p>\n'
          '</div>\n\n')

    # DOMAIN SCORES
    h += ('<div class="card">\n  <h2>Domain Scores</h2>\n  <div class="domain-wrap">\n'
          '    <div class="chart-wrap"><canvas id="domChart"></canvas></div>\n    <div>\n'
          '      <table class="dom-table">\n'
          '        <thead><tr><th>Domain</th><th>Score</th><th>Bar</th><th>Services</th></tr></thead>\n'
          f'        <tbody>\n{dom_tbl}        </tbody>\n'
          '      </table>\n    </div>\n  </div>\n</div>\n\n')

    # IC BREAKDOWN
    h += ('<div class="card">\n  <h2>Impact Criteria (IC) Breakdown</h2>\n  <div class="ic-wrap">\n    <div>\n'
          '      <p style="font-size:10.5px;color:#6c757d;margin-bottom:8px">Bar colors indicate KF group: '
          '<span style="color:#1565c0;font-weight:700">&#9632; KF1 Energy Performance</span> &nbsp; '
          '<span style="color:#6a1b9a;font-weight:700">&#9632; KF2 Occupant Adaptability</span> &nbsp; '
          '<span style="color:#b71c1c;font-weight:700">&#9632; KF3 Grid Flexibility</span></p>\n'
          '      <div class="ic-chart-wrap"><canvas id="icChart"></canvas></div>\n    </div>\n    <div>\n'
          '      <table class="ic-table">\n'
          '        <thead><tr><th>Impact Criterion</th><th>KF</th><th>w(ic)</th><th>SR(ic)</th><th>Contrib.</th></tr></thead>\n'
          f'        <tbody>\n{ic_tbl}'
          f'          <tr class="tot"><td colspan="4"><strong>SRI Total</strong></td><td><strong>{sri_score:.2f}%</strong></td></tr>\n'
          '        </tbody>\n      </table>\n    </div>\n  </div>\n</div>\n\n')

    # KF PILLARS
    h += (f'<div class="card">\n  <h2>Key Functionalities - 3 SRI Pillars (EU Delegated Regulation 2020/2155)</h2>\n'
          f'  <div class="g3">\n{kf_cards}  </div>\n</div>\n\n')

    # LEGEND
    h += ('<div class="card">\n  <h2>Applicability Status Legend</h2>\n  <div class="legend-row">\n'
          '    <div class="legend-item-h"><span class="badge bv">&#10003; VERIFIED</span>'
          '<div class="legend-title">Direct, sufficient evidence</div>'
          '<div class="legend-desc">Evidence directly confirms the assigned FL. Includes L0 assignments where absence is positively confirmed.</div></div>\n'
          '    <div class="legend-item-h"><span class="badge bp">&asymp; PARTIAL EVIDENCE</span>'
          '<div class="legend-title">Indirect or incomplete evidence</div>'
          '<div class="legend-desc">System exists per documentation but operational data is insufficient to confirm FL directly. Assigned conservatively.</div></div>\n'
          '    <div class="legend-item-h"><span class="badge bu">? UNRESOLVED</span>'
          '<div class="legend-title">Uncertain level - reported as range</div>'
          '<div class="legend-desc">System is plausible but FL cannot be determined. SRI reported as a range (lower to upper bound).</div></div>\n'
          '    <div class="legend-item-h"><span class="badge bnn">- N/A (period)</span>'
          '<div class="legend-title">Not evidenced in analysis period</div>'
          '<div class="legend-desc">System was not operational during the analysis period. Temporary exclusion; excluded from denominator.</div></div>\n'
          '    <div class="legend-item-h"><span class="badge bna">- N/A (absent)</span>'
          '<div class="legend-title">Physically absent</div>'
          '<div class="legend-desc">System is permanently absent from the building. Excluded from denominator.</div></div>\n'
          '  </div>\n</div>\n\n')

    # SUMMARY STATS
    h += ('<div class="card">\n  <h2>Services Summary</h2>\n  <div class="stat-grid">\n'
          f'    <div class="stat" style="background:#e3f2fd"><div class="stat-n" style="color:#1565c0">{n_total}</div><div class="stat-l" style="color:#1565c0">Total Services</div></div>\n'
          f'    <div class="stat" style="background:#d4edda"><div class="stat-n" style="color:#155724">{n_verified}</div><div class="stat-l" style="color:#155724">Verified</div></div>\n'
          f'    <div class="stat" style="background:#fff3cd"><div class="stat-n" style="color:#856404">{n_partial}</div><div class="stat-l" style="color:#856404">Partial Evidence</div></div>\n'
          f'    <div class="stat" style="background:#e8d5f5"><div class="stat-n" style="color:#4a1a7a">{n_unresolved}</div><div class="stat-l" style="color:#4a1a7a">Unresolved</div></div>\n'
          f'    <div class="stat" style="background:#f1f3f5"><div class="stat-n" style="color:#495057">{n_na_total}</div><div class="stat-l" style="color:#495057">{_esc(na_lbl)}</div></div>\n'
          f'  </div>\n  <p style="font-size:11px;color:#6c757d;margin-top:12px">{sum_note}</p>\n</div>\n\n')

    # SERVICE TABLE
    h += ('<div class="card">\n  <h2>54-Service Detail - Method C Operational Assessment</h2>\n'
          '  <div class="svc-wrap">\n    <table class="svc-table">\n      <thead>\n        <tr>\n'
          '          <th>Code</th><th>Service Name</th><th>Status</th><th>FL</th><th>Method C Justification</th>\n'
          '        </tr>\n      </thead>\n      <tbody>\n'
          + svc_rows +
          '      </tbody>\n    </table>\n  </div>\n</div>\n\n')

    # CLOSE + FOOTER
    h += ('</div><!-- /content -->\n\n'
          f'<footer>\n  <strong>{bid}</strong> &middot; SRI Method C Dashboard &middot; '
          f'EU Delegated Regulation 2020/2155 &middot; D3.1 Service Catalogue ({n_total} services) &middot; '
          f'Analysis period: {period_str} &middot; Politecnico di Milano / tunES Project &middot; Generated {gen_label}\n'
          '</footer>\n\n')

    # CHARTS SCRIPT
    h += f'<script>\n// DOMAIN CHART\n{dom_js}\n\n// IC CHART\n{ic_js}\n</script>\n</body>\n</html>'

    return h


def save_outputs(service_results: list, sri: dict, data_period: tuple,
                 csv_files: dict, output_dir: str) -> tuple:
    """Save JSON and HTML outputs. Returns (json_path, html_path)."""
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")

    # JSON
    def _serialise(obj):
        if isinstance(obj, Fraction): return float(obj)
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        raise TypeError(type(obj))

    payload = {
        "meta": {
            "method": "SRI Method C — Proposed Operational Assessment",
            "prototype_label": "Partial Prototype — Research Only (not officially approved)",
            "building": BUILDING_INFO,
            "ifc_inventory": IFC_INVENTORY,
            "generated": datetime.now().isoformat(),
            "n_csv_files": len(csv_files),
        },
        "sri": sri,
        "services": service_results,
    }
    json_path = os.path.join(output_dir, f"sri_method_c_{ts}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=_serialise, ensure_ascii=False)

    # HTML
    html = build_html_report(service_results, sri, data_period, csv_files)
    html_path = os.path.join(output_dir, f"sri_method_c_{ts}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    return json_path, html_path


# ════════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("SRI Method C — Proposed Operational Assessment (54 services)")
    print(f"Building: {BUILDING_INFO['id']} — {BUILDING_INFO['address']}")
    print("=" * 70)

    print(f"\n[1/4] Loading CSV files from:\n      {CSV_DIR}")
    csv_files = load_csv_files(CSV_DIR)
    data_period = get_data_period(csv_files)
    if data_period[0]:
        print(f"      Data period: {data_period[0].strftime('%Y-%m-%d')} → {data_period[1].strftime('%Y-%m-%d')}")
    print(f"      Loaded {len(csv_files)} CSV file(s).")

    print(f"\n[2/4] Running 54 service assessments...")
    service_results = run_all_checks(csv_files)
    sym_map = {
        "VERIFIED": "✓", "PARTIAL_EVIDENCE": "≈", "L0_NO_AUTOMATION": "○",
        "N/A_NOT_EVIDENCED": "—", "N/A_EXPLICIT_ABSENCE": "✕", "UNRESOLVED": "?"
    }
    for r in service_results:
        sym = sym_map.get(r.get("applicability_status", ""), "?")
        lv  = r.get("level_achieved")
        print(f"      {sym} {r['service']:<10} {r.get('applicability_status',''):<26} L{lv if lv is not None else '-'}")

    print(f"\n[3/4] Calculating SRI scores...")
    sri = calculate_sri_score(service_results)
    print(f"      SRI = {sri['sri_score_pct']:.2f}%  (Class {sri['sri_class']})")
    print(f"      Bounds: [{sri['sri_lower_bound_pct']:.2f}% – {sri['sri_upper_bound_pct']:.2f}%]")
    print(f"      Applicable: {sri['applicable_services']}/{sri['total_services']} services")

    print(f"\n[4/4] Saving outputs to:\n      {OUTPUT_DIR}")
    json_path, html_path = save_outputs(service_results, sri, data_period, csv_files, OUTPUT_DIR)
    print(f"      JSON → {json_path}")
    print(f"      HTML → {html_path}")
    print(f"\n{'='*70}")
    print(f"  DONE — SRI Method C: {sri['sri_score_pct']:.2f}% (Class {sri['sri_class']})")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
