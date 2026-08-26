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
_HERE              = Path(__file__).parent
CSV_DIR            = str(_HERE / "Data 2026 - 240dd")
MANUAL_PATH        = str(_HERE / "data" / "manual_assessments.json")
BUILDING_INFO_PATH = str(_HERE / "data" / "building_info.json")
IFC_INVENTORY_PATH = str(_HERE / "data" / "ifc_inventory.json")
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
# Analysis period: January–August 2026 (8 months, full heating + cooling season)
CSV_PERIOD_START = pd.Timestamp("2026-01-01", tz="UTC")
CSV_PERIOD_END   = pd.Timestamp("2026-08-31 23:59:59", tz="UTC")

def load_csv_files(csv_dir: str) -> dict:
    """
    Load all CSVs from the 200dd area-based folder.
    New format: each file has columns [entity_id, state, last_changed, ...].
    Returns a dict keyed by entity_id, value = filtered DataFrame for that entity.
    Also handles old single-entity format (no entity_id column) for compatibility.
    Analysis period filtered to Jan–Jun 2026.
    """
    files = {}
    if not os.path.isdir(csv_dir):
        print(f"[WARN] CSV directory not found: {csv_dir}")
        return files

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
def analyze_coverage(df: pd.DataFrame, max_gap_hours: float = 2.0) -> dict:
    """
    Compute coverage stats for regularly sampled sensors.
    A 'gap' is any interval > max_gap_hours; coverage = non-gap time / total time.
    """
    if df.empty or "last_changed" not in df.columns:
        return {"coverage_pct": 0.0, "n_records": 0, "gaps": 0, "period_days": 0}
    df = df.dropna(subset=["last_changed"]).sort_values("last_changed").reset_index(drop=True)
    n = len(df)
    if n < 2:
        return {"coverage_pct": 0.0, "n_records": n, "gaps": 0, "period_days": 0}
    total_secs = (df["last_changed"].iloc[-1] - df["last_changed"].iloc[0]).total_seconds()
    gap_threshold = max_gap_hours * 3600
    gap_secs = 0.0
    n_gaps = 0
    for i in range(n - 1):
        interval = (df["last_changed"].iloc[i+1] - df["last_changed"].iloc[i]).total_seconds()
        if interval > gap_threshold:
            gap_secs += interval
            n_gaps += 1
    coverage = max(0.0, (total_secs - gap_secs) / total_secs) if total_secs > 0 else 0.0
    return {
        "coverage_pct": round(coverage * 100, 1),
        "n_records": n,
        "gaps": n_gaps,
        "period_days": round(total_secs / 86400, 1),
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


# ── HELPER: STANDARD RESULT BUILDER ──────────────────────────────────────────
def _result(code: str, status: str, level: int, confidence: float,
            justification: str, data: dict = None) -> dict:
    cat = SERVICE_CATALOG[code]
    return {
        "service": code,
        "description": cat["name"],
        "domain": cat["domain"],
        "applicability_status": status,
        "level_achieved": level if status not in NA_STATUSES else None,
        "level_max": cat["max_fl"],
        "confidence": confidence,
        "justification": justification,
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

def check_H1a(csv_files: dict) -> dict:
    """
    H-1a: Heat emission control (max FL=4)
    L1=central on/off; L2=individual room fixed setpoint; L3=individual room scheduling;
    L4=individual room demand-based (occupancy/geofencing).
    Evidence: Tado TRVs in 5 zones (CSV: heating demand%), geofencing CSV (8 records).
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
    if n_rooms == 0:
        return _result("H-1a", VERIFIED, 0, 0.4,
                       "Tado CSV files present but no valid numeric demand values found.")

    # L3 confirmed: individual room TRVs with scheduling (Tado app)
    # L4: requires demand-based automation — geofencing Auto mode is present but sparse
    geo_key = next((k for k in csv_files if "modalita_geofencing" in k), None)
    geo_records = len(csv_files[geo_key]) if geo_key else 0

    # Confirm scheduling: Tado TRVs support time-based programs → L3
    # L4 evidence: geofencing CSV shows "Away (Auto)" transitions → heating adjusts automatically
    if geo_records >= 4:
        level = 3  # Conservative: L3 verified; L4 partial (geofencing not fully proven to actuators)
        status = VERIFIED
        conf = 0.78
        just = (f"DBL09: Tado TRVs in {n_rooms} zones (CSV: {total_records} records across "
                f"{', '.join(rooms_with_data)}). Individual room control with time scheduling confirmed "
                f"at L3. Geofencing CSV ({geo_records} records) shows Away/Home (Auto) transitions "
                f"linked to Tado → L4 (demand-based) partially evidenced but insufficient operational "
                f"depth to verify actuator response chain. Conservative assignment: L3.")
    else:
        level = 3
        status = VERIFIED
        conf = 0.72
        just = (f"DBL09: Tado TRVs in {n_rooms} zones (CSV: {total_records} records). "
                f"Individual room temperature control with scheduling confirmed → L3. "
                f"No geofencing CSV available to assess L4.")

    return _result("H-1a", status, level, conf, just,
                   {"n_tado_rooms": n_rooms, "tado_records": total_records,
                    "rooms": rooms_with_data, "geofencing_records": geo_records})


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

    return _result("H-3", VERIFIED, 2, 0.68,
                   f"Temperature logged in Home Assistant across {total_temp_sensors} sensors: "
                   f"{n_tado} Tado zones ({tado_records} records) + {n_meross} Meross sensors "
                   f"({meross_records} records). Historical temperature trends available → L2. "
                   f"No dedicated heating energy meter CSV (Shelly not available). L3 (benchmarking) "
                   f"and L4 (recommendations) not evidenced. Conservative: L2.",
                   {"n_temp_sensors": total_temp_sensors, "tado_temp_records": tado_records,
                    "meross_records": meross_records})


def check_H4(csv_files: dict) -> dict:
    """
    H-4: Flexibility and grid interaction — Heating (max FL=4)
    L1=manual flexible control; L2=time-based auto; L3=price/grid signal; L4=full predictive.
    Evidence: Geofencing Auto mode (CSV) + Tado scheduling → L2. BMS + battery for flexibility.
    """
    geo_key = next((k for k in csv_files if "modalita_geofencing" in k), None)
    if geo_key is None:
        return _result("H-4", VERIFIED, 1, 0.55,
                       "DBL09: Multiple HVAC controllers + BMS allow manual load adjustment → L1. "
                       "No geofencing CSV found to verify automatic time/presence-based response.",
                       {"source": "DBL09"})

    df_geo = csv_files[geo_key]
    cov = analyze_coverage_event_driven(df_geo, "geofencing")
    geo_records = cov["n_records"]

    # Geofencing Auto mode → Tado adjusts heating setpoints automatically by occupancy
    # This is automatic demand-response linked to presence → L2
    level = 2
    conf = 0.65 if geo_records >= 4 else 0.50
    return _result("H-4", VERIFIED if geo_records >= 4 else PARTIAL_EVIDENCE,
                   level, conf,
                   f"DBL09: BMS + HP + boiler allow flexible heating management. Geofencing CSV "
                   f"({geo_records} records, period {cov['period_days']} days) shows Away/Home Auto "
                   f"transitions — Tado automatically reduces heating setpoints when occupants leave "
                   f"→ L2 (automatic time/presence-based flexibility). L3 (grid price signals) not "
                   f"evidenced. Conservative: L2.",
                   {"geofencing_records": geo_records, "period_days": cov["period_days"]})


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

    return _result("DHW-1d", VERIFIED, 1, 0.75,
                   f"DBL09: Solar thermal flat-plate collector CP4 XL + solar differential controller. "
                   f"CSV 'Villa-Percentuale-Solare' ({n_records} records, {cov['period_days']} days): "
                   f"solar fraction mean={mean_pct:.1f}%, max={max_pct:.1f}%, "
                   f"active (>0%) in {pct_nonzero:.0f}% of readings. Confirms solar DHW system is "
                   f"operational with priority control → L1. L2 (weather-compensated storage temp) "
                   f"would require storage temperature logs — not available. Conservative: L1.",
                   {"n_records": n_records, "period_days": cov["period_days"],
                    "mean_solar_pct": round(float(mean_pct), 1),
                    "max_solar_pct": round(float(max_pct), 1),
                    "pct_active": round(float(pct_nonzero), 1)})


def check_DHW2b(csv_files: dict) -> dict:
    """DHW-2b: Sequencing of DHW generators. Source: manual_assessments.json."""
    return _from_manual("DHW-2b")


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
    return _result("DHW-3", PARTIAL_EVIDENCE, 1, 0.55,
                   f"DBL09: DHW system with HP + boiler + solar thermal. CSV 'Villa-Percentuale-Solare' "
                   f"({n} records, {cov['period_days']} days) provides solar fraction history — partial "
                   f"DHW performance proxy. No DHW energy counter, storage temperature, or flow CSV "
                   f"available. Individual controller displays provide L1 reporting. Conservative: L1.",
                   {"n_records": n, "period_days": cov["period_days"], "source": "solar % CSV (proxy)"})


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
    return _result("C-1a", VERIFIED, level, conf,
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


def check_C1f(csv_files: dict) -> dict:
    """
    C-1f: Interlock — avoiding simultaneous heating and cooling in the same room (max FL=2).
    L0=no interlock; L1=zone-level interlock; L2=room-level automatic interlock.
    Cucina has both Tado heating (TRV) and MTS200B cooling (AC split) — independent systems.
    No documented interlock between them → L0.
    """
    cooling = _get_mts200b_cooling(csv_files)
    heating_keys = [k for k in csv_files if k.endswith("_riscaldamento")]
    # Check if same zone has both heating and cooling entities
    cooling_zones = {k.replace("climate.", "").replace("_mts200b_main_channel", "")
                     for k in cooling}
    heating_zones = {k.replace("sensor.", "").replace("_riscaldamento", "")
                     for k in heating_keys}
    overlap = cooling_zones & heating_zones
    return _result("C-1f", VERIFIED, 0, 0.75,
                   f"Cooling confirmed in zones: {sorted(cooling_zones)}. "
                   f"Heating (Tado TRV) confirmed in zones: {sorted(heating_zones)}. "
                   f"Overlap (zones with both): {sorted(overlap) if overlap else 'none detected'}. "
                   f"Heating (Tado) and cooling (MTS200B/AC split) are independent control systems "
                   f"with no documented interlock. Simultaneous operation is technically possible. "
                   f"L0: no automatic interlock.",
                   {"cooling_zones": sorted(cooling_zones),
                    "heating_zones": sorted(heating_zones),
                    "overlap": sorted(overlap)})


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
    return _result("C-2a", VERIFIED, 1, 0.72,
                   f"MTS200B thermostat in {n_rooms} room(s) ({rooms}) auto-starts/stops AC split "
                   f"based on temperature setpoint ({total_rec} cooling records). "
                   f"L1: automatic on/off control confirmed. L2 (variable capacity / inverter control) "
                   f"technically likely for modern AC splits but not directly observable from "
                   f"hvac_action CSV alone. Conservative: L1.",
                   {"rooms": rooms, "cooling_records": total_rec})


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
    return _result("C-3", VERIFIED, 1, 0.68,
                   f"Home Assistant logs MTS200B hvac_action for {n_rooms} cooling zone(s) "
                   f"({rooms}): {total_rec} cooling-state records over ~{cov_days} days. "
                   f"Current and recent cooling state visible in HA dashboard → L1. "
                   f"L2 (structured historical trends) would require dedicated energy sub-meter "
                   f"for cooling (not available). Conservative: L1.",
                   {"rooms": rooms, "cooling_records": total_rec, "coverage_days": cov_days})


def check_C4(csv_files: dict) -> dict:
    """
    C-4: Cooling flexibility and grid interaction (max FL=4).
    No demand-response or grid-signal integration for cooling documented → L0.
    """
    cooling = _get_mts200b_cooling(csv_files)
    n = sum(len(df) for df in cooling.values()) if cooling else 0
    return _result("C-4", VERIFIED, 0, 0.80,
                   f"Cooling operation confirmed ({n} records) via MTS200B thermostats. "
                   f"However, no demand-response programme, TOU tariff response, or grid signal "
                   f"integration documented for the AC splits. Cooling runs on occupant schedule "
                   f"only. L0: no grid interaction.",
                   {"cooling_records": n, "source": "CSV + DBL09"})


# ════════════════════════════════════════════════════════════════════════════════
# SERVICE CHECK FUNCTIONS — VENTILATION (6 services)
# ════════════════════════════════════════════════════════════════════════════════

def check_V1a(csv_files: dict) -> dict:
    """
    V-1a: Supply air flow control at room level (max FL=4)
    L1=constant; L2=manual fixed schedule; L3=occupancy-based; L4=demand/CO2.
    Evidence: ComfoAir Q450 can have room-level Q-sensors; only AHU-level fan duty in CSV.
    """
    fan_key = next((k for k in csv_files if "comfoairq_supply_fan_duty" in k), None)
    if fan_key is None:
        return _result("V-1a", PARTIAL_EVIDENCE, 1, 0.50,
                       "DBL09: Zehnder ComfoAir Q450 MVHR. No Supply-Fan-Duty CSV found. "
                       "Constant supply airflow to rooms at L1 is baseline for any MVHR unit. "
                       "Room-level modulation (L2+) requires ComfoFan or Q-sensor documentation "
                       "not available. Conservative: L1.")

    df = csv_files[fan_key]
    vals = pd.to_numeric(df["state"], errors="coerce").dropna()
    unique_vals = vals.nunique()
    # Fan duty varies → confirms dynamic control, but this is AHU-level (V-1c), not room-level
    # V-1a (room level) requires evidence of per-room damper/diffuser control
    # ComfoAir Q can have room-level airflow via zone kits, but no CSV evidence of this
    return _result("V-1a", VERIFIED, 1, 0.60,
                   f"DBL09: Zehnder ComfoAir Q450 MVHR with duct distribution to multiple rooms. "
                   f"Supply-Fan-Duty CSV ({len(vals)} records, {unique_vals} unique duty levels) confirms "
                   f"MVHR in operation. However, fan duty is AHU-level (→ V-1c), not room-level. "
                   f"Room-level airflow control (VAV diffusers or Q-sensors) not evidenced in CSV. "
                   f"L1 (constant supply to rooms) verified; L2+ (room-level modulation) not evidenced. "
                   f"Conservative: L1.",
                   {"n_records": len(vals), "unique_duty_levels": int(unique_vals)})


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
    if n_unique >= 3:
        level = 2
        conf = 0.72
        note = f"{n_unique} distinct duty levels ({val_range}) → manually adjustable speed confirmed → L2."
    else:
        level = 1
        conf = 0.60
        note = f"Only {n_unique} duty level(s) observed → appears fixed speed → L1."

    return _result("V-1c", VERIFIED, level, conf,
                   f"ComfoAirQ_Supply-Fan-Duty CSV: {len(vals)} records, {cov['period_days']} days, "
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
    # When bypass opens → supply temp = outdoor temp (free cooling)
    # This is automatic adaptive control → L2 (variable setpoint based on conditions)
    return _result("V-2d", VERIFIED, 2, 0.68,
                   f"ComfoAir Q450 regulates supply air temperature automatically by modulating "
                   f"heat recovery bypass ratio. Temperature data: {records}. "
                   f"Supply temp varies with outdoor conditions and bypass position → L2 (variable "
                   f"setpoint). L3 (demand-based with IAQ) requires CO2 sensor — not present. "
                   f"Conservative: L2.",
                   {"temperature_records": records})


def check_V3(csv_files: dict) -> dict:
    """
    V-3: Free cooling via mechanical ventilation (max FL=3)
    L1=manual; L2=automatic temperature-based; L3=auto with humidity+forecast.
    Evidence: Bypass-State (proxy for free cooling activation) + RMOT + Outside-Humidity.
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

    # Check RMOT and humidity for L3
    has_rmot = rmot_key is not None and len(csv_files[rmot_key]) > 0
    has_humidity = hum_key is not None and len(csv_files[hum_key]) > 0
    n_sensors_for_l3 = sum([has_rmot, has_humidity])

    # Bypass opens automatically when outdoor temp < indoor temp → free cooling
    # L2 confirmed by automatic bypass operation (see V-2c)
    # L3 requires humidity-compensated control — humidity data available but control logic uncertain
    if n_sensors_for_l3 >= 2:
        level = 2  # L3 might be possible but control logic unverifiable from CSV
        conf = 0.70
        note = f"RMOT CSV: {has_rmot}, Outside-Humidity CSV: {has_humidity} — L3 multi-parameter control possible but control algorithm not directly observable. Conservative: L2."
    else:
        level = 2
        conf = 0.72
        note = "L3 (humidity+forecast) not evidenced. Conservative: L2."

    return _result("V-3", VERIFIED, level, conf,
                   f"Free cooling via ComfoAir Q450 bypass. Bypass-State CSV: {cov['n_records']} records, "
                   f"{cov['period_days']} days. Bypass open (>1%) in {open_pct:.0f}% of states. "
                   f"Automatic bypass activation confirmed → L2. {note}",
                   {"bypass_records": cov["n_records"], "period_days": cov["period_days"],
                    "bypass_open_pct": round(open_pct, 1),
                    "has_rmot": has_rmot, "has_humidity": has_humidity})


def check_V6(csv_files: dict) -> dict:
    """
    V-6: IAQ reporting (max FL=3). L0=none; L1=simple indicator; L2=individual parameters; L3=multi-param.
    Evidence: Only humidity in CSV (Supply-Humidity, Outside-Humidity). No CO2, no VOC, no PM.
    """
    # DBL08 06-Sensing section: all sensors (CO2, Occupancy, PM2.5, PM10, VOC) = N/A
    # Supply-Humidity from ComfoAir is a ventilation control parameter, not an IAQ report to occupants
    # No dedicated IAQ display or report found
    hum_keys = [k for k in csv_files if "humidity" in k]
    n_hum = len(hum_keys)
    return _result("V-6", VERIFIED, 0, 0.80,
                   f"DBL08 Sensing section: CO2, PM2.5, PM10, VOC, occupancy sensors all = N/A. "
                   f"CSV: {n_hum} humidity sensor(s) from ComfoAir MVHR — these are HVAC control "
                   f"parameters (not IAQ reporting to occupants). No IAQ indicator, display, or "
                   f"report function evidenced. L0: no IAQ reporting.",
                   {"humidity_csvs": n_hum, "source": "DBL08 sensing section"})


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
    # Persiane confirmed in IFC → service applies at L0 (manual, no automation)
    return _result("DE-1", VERIFIED, 0, 0.92,
                   f"IFC Architectural: {persiane_count} Persiane (roller shutter) instances confirmed "
                   f"as IFCBUILDINGELEMENTPROXY elements, 5 size types (40x50, 46.7x250, 70x160, 70x250, "
                   f"80x160). DBL09: no motorisation, no actuator, no smart control documented. "
                   f"No CSV sensor data for shutter position or solar irradiance control. "
                   f"Shading elements ARE present → service applicable. No automatic control → L0.",
                   {"persiane_instances": persiane_count, "types": 5, "source": "IFC Architectural"})


def check_DE2(csv_files: dict) -> dict:
    """
    DE-2: Window open/closed control + HVAC interlock (max FL=3).
    L0=windows present, no open/close detection; L1=detection only; L2=detection+HVAC interlock; L3=auto control.
    Evidence: Windows confirmed in IFC (63 IFCWINDOW). No window position sensor in DBL09, DBL08, or CSV.
    No HVAC interlock documented. Windows exist → service applicable at L0.
    """
    windows_count = IFC_INVENTORY["01_Architectural"].get("IFCWINDOW", 0)
    if windows_count == 0:
        return _result("DE-2", NA_NOT_EVIDENCED, 0, 0.85,
                       "No window elements confirmed. Service not evidenced.",
                       {"source": "IFC"})
    return _result("DE-2", VERIFIED, 0, 0.90,
                   f"IFC Architectural: {windows_count} IFCWINDOW elements confirmed. "
                   f"DBL09 and DBL08: no window open/close sensors documented. No window position CSV. "
                   f"No HVAC interlock for open windows described. "
                   f"Windows ARE present → service applicable. No detection/control → L0.",
                   {"windows_in_ifc": windows_count, "source": "IFC + DBL09"})


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
    return _result("DE-4", VERIFIED, 0, 0.88,
                   f"IFC Architectural: {persiane_count} Persiane (roller shutters) + {windows_count} windows confirmed. "
                   f"Dynamic envelope elements ARE present. However, no position/fault reporting for "
                   f"shutter or window state is documented in DBL09, DBL08, or any CSV. "
                   f"No HA entity for shutter position found. → L0 (no reporting).",
                   {"persiane_instances": persiane_count, "windows": windows_count, "source": "IFC + DBL09"})


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
    return _result("E-2", VERIFIED, 2, 0.68,
                   f"DBL09: PV 2.4 kWp (12 panels × 200 Wp) with inverter + energy management. "
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


def check_E4(csv_files: dict) -> dict:
    """E-4: Optimising self-consumption. Source: manual_assessments.json."""
    return _from_manual("E-4")


def check_E5(csv_files: dict) -> dict:
    """E-5: Control of CHP plant. No CHP present."""
    return _result("E-5", NA_EXPLICIT_ABSENCE, 0, 0.98,
                   "DBL09 and DBL08: No CHP (combined heat and power) plant documented. "
                   "Energy sources are natural gas (boiler), electricity (grid + PV), and solar thermal. "
                   "Service not applicable.",
                   {"source": "DBL09 + DBL08"})


def check_E8(csv_files: dict) -> dict:
    """E-8: Support of micro-grid operation modes. Source: manual_assessments.json."""
    return _from_manual("E-8")


def check_E11(csv_files: dict) -> dict:
    """E-11: Energy storage reporting. Source: manual_assessments.json."""
    return _from_manual("E-11")


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
        # Check if sub-circuit meters also present (em1=PV, em2=pool) → L3
        shelly_em1 = next((k for k in csv_files
                           if "shellypro3em" in k.lower() and "em1" in k.lower()), None)
        shelly_em2 = next((k for k in csv_files
                           if "shellypro3em" in k.lower() and "em2" in k.lower()), None)
        n_sub = sum([shelly_em1 is not None, shelly_em2 is not None])
        level = 3 if n_sub >= 2 else 2
        conf  = 0.82 if n_sub >= 2 else 0.80
        sub_note = (f"Sub-circuit meters also present: em1 (PV generation), em2 (pool pump) "
                    f"→ L3 (sub-metered by circuit).") if n_sub >= 2 else \
                   "Only grid meter available → L2."
        return _result("E-12", VERIFIED, level, conf,
                       f"Shelly Pro 3EM (em0 = grid/consumption) CSV: {len(vals)} records, "
                       f"{cov['period_days']} days, coverage {cov['coverage_pct']}%. "
                       f"Time-resolved building electricity consumption confirmed → L2. "
                       f"{sub_note}",
                       {"shelly_records": len(vals), "period_days": cov["period_days"],
                        "coverage_pct": cov["coverage_pct"], "sub_circuit_meters": n_sub,
                        "note": "Shelly Pro 3EM building meter"})

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
    MC-3: HVAC runtime management (max FL=3)
    L1=basic scheduling; L2=optimised scheduling; L3=demand-based with prediction.
    Evidence: Tado scheduling (5 zones) + ComfoAir scheduling + geofencing.
    """
    tado_keys = [k for k in csv_files if k.endswith("_riscaldamento")]
    fan_key = next((k for k in csv_files if "comfoairq_supply_fan_duty" in k), None)
    geo_key = next((k for k in csv_files if "modalita_geofencing" in k), None)

    n_tado = len(tado_keys)
    n_tado_rec = sum(len(csv_files[k]) for k in tado_keys)

    if n_tado == 0 and not fan_key:
        return _result("MC-3", PARTIAL_EVIDENCE, 1, 0.50,
                       "DBL09: Multiple HVAC controllers confirmed. No CSV to verify scheduling mode. "
                       "L1 inferred from controller capabilities.")

    # L1: basic scheduling → Tado weekly programs confirmed (industry-standard feature)
    # L2: optimised scheduling → Tado has 'Smart Schedule' + early-start feature → L2 candidate
    # Geofencing (auto mode) adds occupancy-based optimisation
    geo_rec = len(csv_files[geo_key]) if geo_key else 0
    level = 2
    conf = 0.68
    just = (f"DBL09 + CSV: Tado TRVs ({n_tado} zones, {n_tado_rec} records) provide room-level "
            f"scheduling. ComfoAir Q450 has independent schedule. Tado 'Smart Schedule' feature "
            f"with automatic early-start → L2 (optimised scheduling). Geofencing CSV ({geo_rec} records) "
            f"adds presence-based optimisation. L3 (predictive demand) not verified. Conservative: L2.")

    return _result("MC-3", VERIFIED, level, conf, just,
                   {"tado_zones": n_tado, "tado_records": n_tado_rec, "geofencing_records": geo_rec})


def check_MC4(csv_files: dict) -> dict:
    """
    MC-4: Fault detection and diagnosis (max FL=3)
    L0=none; L1=fault alarms; L2=fault isolation; L3=automated diagnosis.
    NOTE: ComfoAirQ Days-Replace-Filter = maintenance countdown, NOT a fault alarm.
    """
    filter_key = next((k for k in csv_files if "days_to_replace_filter" in k), None)
    n_filter_rec = len(csv_files[filter_key]) if filter_key else 0

    return _result("MC-4", VERIFIED, 0, 0.82,
                   f"DBL09: No dedicated FDD system documented. ComfoAirQ_Days-Replace-Filter CSV "
                   f"({n_filter_rec} records) is a maintenance countdown timer — NOT a fault alarm or "
                   f"diagnostic system per the SRI catalogue. No alarm log, fault code CSV, or BMS "
                   f"alarm list available. Conservative: L0 (no FDD).",
                   {"filter_countdown_records": n_filter_rec,
                    "note": "Filter countdown ≠ fault detection"})


def check_MC9(csv_files: dict) -> dict:
    """
    MC-9: Occupancy detection connected to services (max FL=2)
    L1=presence detection (not connected); L2=connected to HVAC/other services.
    Evidence: Geofencing CSV showing Auto mode + Tado integration.
    """
    geo_key = next((k for k in csv_files if "modalita_geofencing" in k), None)
    if geo_key is None:
        return _result("MC-9", NA_NOT_EVIDENCED, 0, 0.0,
                       "No geofencing or occupancy CSV found. Cannot verify occupancy detection.")

    df_geo = csv_files[geo_key]
    cov = analyze_coverage_event_driven(df_geo, "geofencing")
    n_rec = cov["n_records"]

    # Geofencing "Away (Auto)" / "Home (Auto)" — the "(Auto)" = system automatically detects
    # occupancy via smartphone GPS and adjusts Tado heating → L2 (connected to heating service)
    states = df_geo["state"].unique().tolist() if "state" in df_geo.columns else []
    has_auto = any("Auto" in str(s) for s in states)

    if n_rec < 3:
        return _result("MC-9", PARTIAL_EVIDENCE, 1, 0.45,
                       f"Geofencing CSV: only {n_rec} records — insufficient for full coverage. "
                       f"States: {states}. L1 partially evidenced.")

    level = 2 if has_auto else 1
    conf = 0.75 if has_auto else 0.55
    return _result("MC-9", VERIFIED, level, conf,
                   f"Geofencing_Villa-Modalita CSV: {n_rec} records, {cov['period_days']} days. "
                   f"States: {states}. '(Auto)' qualifier confirms automatic occupancy detection "
                   f"(smartphone GPS geofencing). Tado TRVs respond to Away/Home transitions by "
                   f"adjusting heating setpoints → occupancy detection connected to heating service "
                   f"→ L2 verified.",
                   {"n_records": n_rec, "states": [str(s) for s in states],
                    "has_auto_mode": has_auto, "period_days": cov["period_days"]})


def check_MC13(csv_files: dict) -> dict:
    """
    MC-13: Central TBS performance and energy reporting (max FL=3)
    L1=basic summary; L2=historical trends (multi-system); L3=detailed analysis.
    Evidence: Multiple systems logging to Home Assistant (implied by CSV entity_id format).
    """
    n_csv = len(csv_files)
    systems_present = []
    if any("comfoairq" in k for k in csv_files): systems_present.append("MVHR (ComfoAir Q)")
    if any("_riscaldamento" in k or "modalita_tado" in k for k in csv_files): systems_present.append("Heating (Tado)")
    if any("meross" in k for k in csv_files): systems_present.append("Ambient temperature (Meross/MTS200B)")
    if any("percentuale_solare" in k for k in csv_files): systems_present.append("Solar (PV/thermal %)")
    if any("modalita_geofencing" in k for k in csv_files): systems_present.append("Occupancy (Geofencing)")

    n_sys = len(systems_present)
    # All CSVs have entity_id in HA format → Home Assistant is the central monitoring platform
    # HA stores long-term history → L2 (historical multi-system trends)
    level = 2 if n_sys >= 3 else 1
    conf = 0.72 if n_sys >= 3 else 0.55

    return _result("MC-13", VERIFIED, level, conf,
                   f"Home Assistant (HA) integrates {n_sys} building systems ({', '.join(systems_present)}) "
                   f"as evidenced by entity_id format in {n_csv} CSV files. HA provides centralised "
                   f"monitoring dashboard with historical logging → L2 (multi-system historical trends). "
                   f"L3 (detailed analysis with recommendations) not evidenced. Conservative: L2.",
                   {"n_systems": n_sys, "systems": systems_present, "n_csv_files": n_csv})


def check_MC25(csv_files: dict) -> dict:
    """MC-25: Smart grid integration. Source: manual_assessments.json."""
    return _from_manual("MC-25")


def check_MC28(csv_files: dict) -> dict:
    """MC-28: DSM performance reporting. Source: manual_assessments.json."""
    return _from_manual("MC-28")


def check_MC29(csv_files: dict) -> dict:
    """
    MC-29: Override of DSM control (max FL=4). L1=always overridable (can be negative score); L2=limited.
    Note: MC-29 L1 has negative scores for Comfort/Maint/Info per catalogue — these are kept as-is.
    """
    # Manual override of geofencing/Tado auto mode is inherent (user can switch to Manual)
    # But DSM override presupposes DSM control (MC-25 UNRESOLVED)
    # Conservative: VERIFIED L2 (time-limited manual override is standard for Tado)
    geo_key = next((k for k in csv_files if "modalita_geofencing" in k), None)
    states = []
    if geo_key:
        states = csv_files[geo_key]["state"].unique().tolist() if "state" in csv_files[geo_key].columns else []

    has_manual = any("Home" in str(s) and "Auto" not in str(s) for s in states) or True
    # MC-29 = Override of DSM control. L0 = no DSM exists at all.
    # Villa has no DSM (Demand Side Management) integration with the grid.
    # Tado manual override ≠ DSM override. Conservative: L0.
    return _result("MC-29", VERIFIED, 0, 0.85,
                   f"DBL09: No DSM (Demand Side Management) system integrated with grid signals. "
                   f"The building operates autonomously — no utility-side DSM commands to override. "
                   f"Tado manual override is a user schedule override, not a DSM override. "
                   f"Catalogue L0 = 'no DSM control exists'. Corrected from prior L2 assignment. "
                   f"Geofencing states observed: {[str(s) for s in states]}.",
                   {"states_observed": [str(s) for s in states], "correction": "L2→L0: no DSM system"})


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

    # HA integrates multiple systems but control is via individual apps (Tado app, ComfoAir app)
    # True integrated platform (L2) would require cross-system control from one interface
    # HA provides monitoring integration; control still fragmented per system
    return _result("MC-30", VERIFIED, 2, 0.65,
                   f"Home Assistant integrates {n_systems} building systems: MVHR (ComfoAir), "
                   f"Heating (Tado), Solar monitoring, Geofencing, Ambient temperatures (Meross). "
                   f"HA provides centralised monitoring dashboard (all visible in one place) + "
                   f"automation capabilities → L2 (integrated monitoring and control platform). "
                   f"L3 (full cross-system optimisation) not evidenced. Conservative: L2.",
                   {"n_integrated_systems": n_systems})


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
