"""Threshold sensitivity, fast version.

Re-running all 54 checks for every threshold value is wasteful: each threshold
touches one or two services. This version computes the baseline service list
once, then for each threshold value re-runs only the affected check functions
and rescores with those results swapped in.

Usage: sens2.py [start_index] [count]   so the sweep can be done in slices.
"""
import types, json, sys
from pathlib import Path

REPO = Path("/sessions/fervent-intelligent-ritchie/mnt/SRI_Villa-Segrate_POLIMI")
F = REPO / "sri_method_c_FINAL.py"
SRC = F.read_text(encoding="utf-8").replace('if __name__ == "__main__":', 'if False:')

eng = types.ModuleType("eng"); eng.__file__ = str(F)
exec(compile(SRC, str(F), "exec"), eng.__dict__)
csv = eng.load_csv_files(eng.CSV_DIR)
BASE = eng.run_all_checks(csv)
base_res = eng.calculate_sri_score(BASE)
B = base_res["sri_score_pct"]

# threshold -> (values, description, affected check function names)
SWEEPS = [
 ("MIN_COVERAGE_FOR_VERIFIED", [40.0, 60.0, 90.0],
  "time coverage needed to call a result verified",
  ["check_E12","check_E2","check_V1c","check_V3","check_DHW3","check_DHW1d"]),
 ("MIN_RECORDS_FOR_VERIFIED", [10, 100, 1000],
  "records needed to call a result verified",
  ["check_E12","check_E2","check_V1c","check_V3","check_DHW3","check_MC9",
   "check_C1a","check_C2a","check_C3","check_DE1","check_H1a","check_H3",
   "check_MC13","check_MC29"]),
 ("MIN_OPERATIONAL_SPAN_FRACTION", [0.01, 0.10, 0.33],
  "share of the period a capability must be observed", ["check_H1a","check_MC9"]),
 ("COVERAGE_GAP_MULTIPLE", [2, 10, 50],
  "multiple of the median interval that counts as a gap",
  ["check_E12","check_E2","check_V1c","check_DHW3","check_DHW1d"]),
 ("V1A_MIN_AQ_CORRELATION", [0.2, 0.5, 0.9],
  "correlation needed to call a fan demand-controlled", ["check_V1a"]),
 ("V1A_MIN_HOUR_ETA2", [0.002, 0.15, 0.50],
  "variance share needed to call a fan clock-controlled", ["check_V1a"]),
 ("MC4_MIN_FAULT_EVENTS", [5, 20, 600],
  "logged faults needed for central fault detection", ["check_MC4"]),
 ("MC4_MIN_FAULT_ENTITIES", [2, 5, 60],
  "distinct devices needed for central fault detection", ["check_MC4"]),
 ("MC4_MIN_DIAG_HISTORY", [1, 30, 500],
  "records a diagnostic entity needs", ["check_MC4"]),
 ("V6_MIN_ZONES_FOR_L2", [1, 3, 8],
  "zones needed for per-room IAQ reporting", ["check_V6"]),
 ("V6_MIN_RECORDS_PER_SENSOR", [50, 500, 5000],
  "records a sensor needs to count as reporting", ["check_V6"]),
 ("V6_MIN_PARAM_TYPES_FOR_L3", [1, 2, 3],
  "IAQ parameter families needed for multi-parameter reporting", ["check_V6"]),
 ("C1F_MIN_OBSERVATION_DAYS", [5, 30, 120],
  "dual-mode days before an absent conflict is verified", ["check_C1f"]),
 ("E12_REALTIME_MAX_MINUTES", [0.1, 15, 240],
  "sampling interval that still counts as real time", ["check_E12"]),
 ("E12_MIN_APPLIANCE_CIRCUITS", [1, 2, 5],
  "metered circuits needed for appliance-level feedback", ["check_E12"]),
 ("V3_MAX_NIGHT_SHARE", [0.3, 0.6, 0.95],
  "night share above which free cooling is night-only", ["check_V3"]),
 ("V3_MIN_ENTHALPY_CORRELATION", [0.2, 0.5, 0.7],
  "humidity correlation needed for enthalpy control", ["check_V3"]),
 ("H4_MIN_SETPOINT_ZONES", [1, 3, 8],
  "zones with a varying setpoint needed for scheduled operation", ["check_H4"]),
 ("H1A_MIN_ROOM_CONTROLLERS", [2, 5, 12],
  "controllers needed for individual room control", ["check_H1a"]),
 ("DHW2B_MIN_DISTINCT_FRACTIONS", [3, 10, 200],
  "distinct solar fractions needed to show sequencing", ["check_DHW2b"]),
 ("E4_MIN_PV_CORRELATION", [0.01, 0.5, 0.9],
  "load-PV correlation needed for self-consumption control", ["check_E4"]),
 ("E4_MIN_SCHEDULE_ETA2", [0.01, 0.15, 0.50],
  "variance share needed to call a load scheduled", ["check_E4"]),
 ("DE2_MIN_HISTORY", [1, 100, 500],
  "records a window sensor needs to count as operational", ["check_DE2","check_DE4"]),
 ("DHW1D_MIN_COVERAGE_PCT", [20.0, 40.0, 95.0],
  "solar-fraction coverage needed to characterise charging", ["check_DHW1d"]),
 ("E8_MIN_ISLANDING_SHARE", [0.005, 0.02, 0.5],
  "share of hours that counts as sustained island operation", ["check_E8"]),
]

start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
count = int(sys.argv[2]) if len(sys.argv) > 2 else len(SWEEPS)
OUT = Path("/sessions/fervent-intelligent-ritchie/mnt/outputs/sens_results.json")
results = json.loads(OUT.read_text()) if OUT.exists() else {}

for name, values, desc, fns in SWEEPS[start:start + count]:
    orig = getattr(eng, name)
    scores, classes = [], []
    for v in values:
        setattr(eng, name, v)
        eng._MANUAL_CACHE = None
        swapped = {}
        for fname in fns:
            fn = getattr(eng, fname, None)
            if fn is None:
                continue
            try:
                r = fn(csv)
                swapped[r["service"]] = r
            except Exception as e:
                print(f"  !! {fname} @ {name}={v}: {e}")
        merged = [swapped.get(s["service"], s) for s in BASE]
        res = eng.calculate_sri_score(merged)
        scores.append(round(res["sri_score_pct"], 2)); classes.append(res["sri_class"])
    setattr(eng, name, orig)
    span = round(max(scores) - min(scores), 2)
    results[name] = dict(description=desc, values=values, scores=scores,
                         classes=classes, span=span,
                         classes_seen=sorted(set(classes)))
    print(f"{name:<32} {'  '.join(f'{v}->{s}%' for v, s in zip(values, scores))}"
          f"   span {span} pp  {sorted(set(classes))}")

OUT.write_text(json.dumps(results, indent=1))
print(f"\nbaseline {B:.2f}%   thresholds done: {len(results)}/{len(SWEEPS)}")
