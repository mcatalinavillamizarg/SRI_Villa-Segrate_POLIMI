"""
SRI Method C -- Interactive Dashboard | Villa Segrate
EU Delegated Regulation 2020/2155
Run: python -m streamlit run app.py
"""
import os, sys, re, types, json, calendar
from pathlib import Path
import pandas as pd
import streamlit as st

# ── PATHS ─────────────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent
ENGINE_PATH = str(_HERE / "sri_method_c_FINAL.py")

# ── DOMAIN WEIGHTS (all zones x building types) ───────────────────────────────
DOMAIN_WEIGHTS_ALL = {
    ("South","Residential"):     {"Heating":{"EE":0.32,"Flex":0.38,"Comfort":0.16,"Conv":0.10,"Health":0.16,"Maint":0.33,"Info":0.11},"DHW":{"EE":0.10,"Flex":0.12,"Comfort":0.00,"Conv":0.10,"Health":0.00,"Maint":0.10,"Info":0.11},"Cooling":{"EE":0.07,"Flex":0.08,"Comfort":0.16,"Conv":0.10,"Health":0.16,"Maint":0.07,"Info":0.11},"Ventilation":{"EE":0.09,"Flex":0.00,"Comfort":0.16,"Conv":0.10,"Health":0.16,"Maint":0.10,"Info":0.11},"Lighting":{"EE":0.03,"Flex":0.00,"Comfort":0.16,"Conv":0.10,"Health":0.16,"Maint":0.00,"Info":0.00},"Dynamic_Envelope":{"EE":0.05,"Flex":0.00,"Comfort":0.16,"Conv":0.10,"Health":0.16,"Maint":0.05,"Info":0.11},"Electricity":{"EE":0.15,"Flex":0.17,"Comfort":0.00,"Conv":0.10,"Health":0.00,"Maint":0.15,"Info":0.11},"EV_Charging":{"EE":0.00,"Flex":0.05,"Comfort":0.00,"Conv":0.10,"Health":0.00,"Maint":0.00,"Info":0.11},"Monitoring_Control":{"EE":0.20,"Flex":0.20,"Comfort":0.20,"Conv":0.20,"Health":0.20,"Maint":0.20,"Info":0.20}},
    ("South","Non-Residential"):  {"Heating":{"EE":0.24,"Flex":0.26,"Comfort":0.12,"Conv":0.10,"Health":0.12,"Maint":0.25,"Info":0.08},"DHW":{"EE":0.08,"Flex":0.08,"Comfort":0.00,"Conv":0.10,"Health":0.00,"Maint":0.08,"Info":0.08},"Cooling":{"EE":0.14,"Flex":0.16,"Comfort":0.24,"Conv":0.10,"Health":0.24,"Maint":0.14,"Info":0.17},"Ventilation":{"EE":0.18,"Flex":0.00,"Comfort":0.24,"Conv":0.10,"Health":0.24,"Maint":0.18,"Info":0.17},"Lighting":{"EE":0.12,"Flex":0.00,"Comfort":0.12,"Conv":0.10,"Health":0.12,"Maint":0.00,"Info":0.00},"Dynamic_Envelope":{"EE":0.05,"Flex":0.00,"Comfort":0.12,"Conv":0.10,"Health":0.12,"Maint":0.05,"Info":0.08},"Electricity":{"EE":0.10,"Flex":0.25,"Comfort":0.00,"Conv":0.10,"Health":0.00,"Maint":0.10,"Info":0.17},"EV_Charging":{"EE":0.00,"Flex":0.05,"Comfort":0.00,"Conv":0.10,"Health":0.00,"Maint":0.00,"Info":0.08},"Monitoring_Control":{"EE":0.09,"Flex":0.20,"Comfort":0.16,"Conv":0.20,"Health":0.16,"Maint":0.20,"Info":0.17}},
    ("Central","Residential"):    {"Heating":{"EE":0.40,"Flex":0.47,"Comfort":0.20,"Conv":0.10,"Health":0.20,"Maint":0.42,"Info":0.14},"DHW":{"EE":0.13,"Flex":0.15,"Comfort":0.00,"Conv":0.10,"Health":0.00,"Maint":0.13,"Info":0.14},"Cooling":{"EE":0.03,"Flex":0.03,"Comfort":0.07,"Conv":0.10,"Health":0.07,"Maint":0.03,"Info":0.04},"Ventilation":{"EE":0.09,"Flex":0.00,"Comfort":0.16,"Conv":0.10,"Health":0.16,"Maint":0.09,"Info":0.11},"Lighting":{"EE":0.03,"Flex":0.00,"Comfort":0.16,"Conv":0.10,"Health":0.16,"Maint":0.00,"Info":0.00},"Dynamic_Envelope":{"EE":0.05,"Flex":0.00,"Comfort":0.16,"Conv":0.10,"Health":0.16,"Maint":0.05,"Info":0.11},"Electricity":{"EE":0.15,"Flex":0.17,"Comfort":0.00,"Conv":0.10,"Health":0.00,"Maint":0.15,"Info":0.11},"EV_Charging":{"EE":0.00,"Flex":0.05,"Comfort":0.00,"Conv":0.10,"Health":0.00,"Maint":0.00,"Info":0.11},"Monitoring_Control":{"EE":0.12,"Flex":0.13,"Comfort":0.09,"Conv":0.10,"Health":0.09,"Maint":0.13,"Info":0.24}},
    ("Central","Non-Residential"):{"Heating":{"EE":0.30,"Flex":0.33,"Comfort":0.15,"Conv":0.10,"Health":0.15,"Maint":0.31,"Info":0.10},"DHW":{"EE":0.10,"Flex":0.10,"Comfort":0.00,"Conv":0.10,"Health":0.00,"Maint":0.10,"Info":0.10},"Cooling":{"EE":0.07,"Flex":0.08,"Comfort":0.16,"Conv":0.10,"Health":0.16,"Maint":0.07,"Info":0.11},"Ventilation":{"EE":0.18,"Flex":0.00,"Comfort":0.24,"Conv":0.10,"Health":0.24,"Maint":0.18,"Info":0.17},"Lighting":{"EE":0.12,"Flex":0.00,"Comfort":0.12,"Conv":0.10,"Health":0.12,"Maint":0.00,"Info":0.00},"Dynamic_Envelope":{"EE":0.05,"Flex":0.00,"Comfort":0.12,"Conv":0.10,"Health":0.12,"Maint":0.05,"Info":0.08},"Electricity":{"EE":0.10,"Flex":0.25,"Comfort":0.00,"Conv":0.10,"Health":0.00,"Maint":0.10,"Info":0.17},"EV_Charging":{"EE":0.00,"Flex":0.05,"Comfort":0.00,"Conv":0.10,"Health":0.00,"Maint":0.00,"Info":0.08},"Monitoring_Control":{"EE":0.08,"Flex":0.19,"Comfort":0.21,"Conv":0.20,"Health":0.21,"Maint":0.19,"Info":0.19}},
    ("North","Residential"):      {"Heating":{"EE":0.46,"Flex":0.54,"Comfort":0.23,"Conv":0.10,"Health":0.23,"Maint":0.48,"Info":0.16},"DHW":{"EE":0.15,"Flex":0.17,"Comfort":0.00,"Conv":0.10,"Health":0.00,"Maint":0.15,"Info":0.16},"Cooling":{"EE":0.01,"Flex":0.01,"Comfort":0.02,"Conv":0.10,"Health":0.02,"Maint":0.01,"Info":0.01},"Ventilation":{"EE":0.09,"Flex":0.00,"Comfort":0.16,"Conv":0.10,"Health":0.16,"Maint":0.09,"Info":0.11},"Lighting":{"EE":0.03,"Flex":0.00,"Comfort":0.16,"Conv":0.10,"Health":0.16,"Maint":0.00,"Info":0.00},"Dynamic_Envelope":{"EE":0.05,"Flex":0.00,"Comfort":0.16,"Conv":0.10,"Health":0.16,"Maint":0.05,"Info":0.11},"Electricity":{"EE":0.15,"Flex":0.17,"Comfort":0.00,"Conv":0.10,"Health":0.00,"Maint":0.15,"Info":0.11},"EV_Charging":{"EE":0.00,"Flex":0.05,"Comfort":0.00,"Conv":0.10,"Health":0.00,"Maint":0.00,"Info":0.11},"Monitoring_Control":{"EE":0.06,"Flex":0.06,"Comfort":0.27,"Conv":0.10,"Health":0.27,"Maint":0.07,"Info":0.33}},
    ("North","Non-Residential"):  {"Heating":{"EE":0.34,"Flex":0.38,"Comfort":0.17,"Conv":0.10,"Health":0.17,"Maint":0.36,"Info":0.12},"DHW":{"EE":0.11,"Flex":0.12,"Comfort":0.00,"Conv":0.10,"Health":0.00,"Maint":0.11,"Info":0.12},"Cooling":{"EE":0.02,"Flex":0.03,"Comfort":0.05,"Conv":0.10,"Health":0.05,"Maint":0.02,"Info":0.03},"Ventilation":{"EE":0.18,"Flex":0.00,"Comfort":0.24,"Conv":0.10,"Health":0.24,"Maint":0.18,"Info":0.17},"Lighting":{"EE":0.12,"Flex":0.00,"Comfort":0.12,"Conv":0.10,"Health":0.12,"Maint":0.00,"Info":0.00},"Dynamic_Envelope":{"EE":0.05,"Flex":0.00,"Comfort":0.12,"Conv":0.10,"Health":0.12,"Maint":0.05,"Info":0.08},"Electricity":{"EE":0.10,"Flex":0.25,"Comfort":0.00,"Conv":0.10,"Health":0.00,"Maint":0.10,"Info":0.17},"EV_Charging":{"EE":0.00,"Flex":0.05,"Comfort":0.00,"Conv":0.10,"Health":0.00,"Maint":0.00,"Info":0.08},"Monitoring_Control":{"EE":0.08,"Flex":0.17,"Comfort":0.30,"Conv":0.20,"Health":0.30,"Maint":0.18,"Info":0.22}},
}

CLASS_COLORS = {"A":"#1a9641","B":"#7bc143","C":"#c4d600","D":"#ffd700","E":"#e16e28","F":"#d45b1a","G":"#d7191c"}
CLASS_RANGES = [("G","0–20%",0),("F","20–35%",20),("E","35–50%",35),("D","50–65%",50),("C","65–75%",65),("B","75–90%",75),("A",">90%",90)]
MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug",
          "Sep","Oct","Nov","Dec"]


@st.cache_data(show_spinner=False)
def _data_bounds(fingerprint: str = ""):
    """First and last timestamp in the dataset, so the period controls follow the
    data instead of being pinned to the months that happened to exist when the
    dashboard was written.

    Falls back to scanning the CSV folder directly if the engine predates
    detect_csv_period, so the dashboard keeps working when the two files are
    deployed out of step with each other.
    """
    eng = _load_engine()
    lo = hi = None
    detect = getattr(eng, "detect_csv_period", None)
    csv_dir = getattr(eng, "CSV_DIR", None)
    if detect is not None and csv_dir:
        try:
            lo, hi = detect(csv_dir)
        except Exception:
            lo = hi = None
    if (lo is None or hi is None) and csv_dir and os.path.isdir(csv_dir):
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
    if lo is None or hi is None:
        return pd.Timestamp("2026-01-01", tz="UTC"), pd.Timestamp("2026-08-31", tz="UTC")
    return lo, hi


def _period_options():
    """Every calendar month the dataset touches, as year-month periods.

    Month numbers alone break as soon as the data crosses a year boundary, which
    this dataset does: it starts on 31 December 2025 and runs into August 2026.
    Working in periods keeps the control correct in that case and for any future
    refresh."""
    lo, hi = _data_bounds(_engine_fingerprint())
    return list(pd.period_range(lo.to_period("M"), hi.to_period("M"), freq="M"))


def _fmt_period(p) -> str:
    return f"{MONTHS[p.month - 1]} {p.year}"
NA_SET = {"N/A_NOT_EVIDENCED","N/A_EXPLICIT_ABSENCE"}

# ── ENGINE ────────────────────────────────────────────────────────────────────
def _engine_fingerprint() -> str:
    """Hash of the engine source.

    Streamlit keeps @st.cache_resource entries across a redeploy whenever the
    decorated function's own source is unchanged. Since _load_engine reads the
    engine from disk, an updated engine would otherwise keep serving the version
    cached before the deploy. Passing the file's hash as an argument makes the
    cache key follow the engine's contents instead.
    """
    try:
        import hashlib
        return hashlib.md5(Path(ENGINE_PATH).read_bytes()).hexdigest()
    except Exception:
        return "unknown"


@st.cache_resource
def _load_engine_cached(fingerprint: str):
    with open(ENGINE_PATH, encoding="utf-8") as f:
        code = f.read()
    code = code.replace('if __name__ == "__main__":', 'if False:')
    mod = types.ModuleType("sri_engine")
    mod.__file__ = ENGINE_PATH
    exec(compile(code, ENGINE_PATH, "exec"), mod.__dict__)
    return mod


def _load_engine():
    return _load_engine_cached(_engine_fingerprint())


@st.cache_data(show_spinner=False)
def _load_all_csv(fingerprint: str = ""):
    eng = _load_engine()
    return eng.load_csv_files(eng.CSV_DIR)

def run_sri(p_start, p_end, zone, btype):
    """p_start and p_end are pandas year-month Periods, so a period that crosses
    a calendar year is expressed correctly."""
    eng = _load_engine()
    all_csv = _load_all_csv(_engine_fingerprint())
    t_start = pd.Timestamp(p_start.start_time, tz="UTC")
    t_end = pd.Timestamp(p_end.end_time, tz="UTC")
    filtered = {}
    for k, df in all_csv.items():
        if "last_changed" in df.columns:
            sub = df[(df["last_changed"] >= t_start) & (df["last_changed"] <= t_end)]
            if len(sub) > 0:
                filtered[k] = sub.reset_index(drop=True)
        else:
            filtered[k] = df
    eng.DOMAIN_WEIGHTS = DOMAIN_WEIGHTS_ALL[(zone, btype)]
    svc = eng.run_all_checks(filtered)
    result = eng.calculate_sri_score(svc)
    return result, svc, t_start, t_end

def score_only(svc_list, zone, btype):
    """Re-run only the aggregation layer (FL -> SRI) on a modified service list.
    No CSV reload, no evidence re-derivation. This is the layer shared by
    Methods A, B and C, fixed by EU Delegated Regulation 2020/2155."""
    eng = _load_engine()
    eng.DOMAIN_WEIGHTS = DOMAIN_WEIGHTS_ALL[(zone, btype)]
    return eng.calculate_sri_score(svc_list)

def seed_applicable(s):
    """Applicability as the baseline assessment sees it."""
    return s["applicability_status"] not in NA_SET

def seed_fl(s):
    """The functionality level the baseline calculation actually USES for this
    service. Not always level_achieved: UNRESOLVED services are scored at L0 by
    calculate_sri_score regardless of the level recorded on the service. Seeding
    the editor with the effective value is what guarantees that opening override
    mode without editing anything reproduces the baseline score exactly."""
    if s["applicability_status"] in NA_SET:
        return 0
    if s["applicability_status"] == "UNRESOLVED":
        return 0
    fl = s["level_achieved"]
    return 0 if fl is None else int(fl)

def apply_overrides(baseline_svc, edited_df):
    """Build a new service list from baseline + manual FL / applicability edits.

    Rows left untouched keep their original status, so the evidence-based
    assessment passes through unchanged. Only edited rows are rewritten: an
    explicit FL is marked VERIFIED so the aggregation treats it as a determinate
    level, since UNRESOLVED would otherwise be forced back to L0."""
    out = []
    for i, s in enumerate(baseline_svc):
        row = edited_df.iloc[i]
        applicable = bool(row["Applicable"])
        fl_raw = row["FL"]
        fl = 0 if pd.isna(fl_raw) else int(fl_raw)
        fl = max(0, min(fl, int(s["level_max"])))

        untouched = (applicable == seed_applicable(s)) and (fl == seed_fl(s))
        if untouched:
            new = dict(s)
            new["overridden"] = False
            out.append(new)
            continue

        new = dict(s)
        new["overridden"] = True
        new["derived_level"] = s["level_achieved"]
        new["derived_status"] = s["applicability_status"]
        if not applicable:
            new["applicability_status"] = "N/A_EXPLICIT_ABSENCE"
            new["level_achieved"] = None
            new["justification"] = "Manually excluded by assessor (override mode)."
        else:
            new["applicability_status"] = "VERIFIED"
            new["level_achieved"] = fl
            new["justification"] = (
                f"Manually set to L{fl} by assessor (override mode). "
                f"Evidence-derived value: "
                f"{'L' + str(s['level_achieved']) if s['level_achieved'] is not None else 'N/A'}"
                f" [{s['applicability_status']}].")
        out.append(new)
    return out

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="SRI Method C | Villa Segrate", page_icon="🏠", layout="wide")

st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:#f2f4f7}
[data-testid="stSidebar"]{background:#1c2541}
[data-testid="stSidebar"] *{color:white!important}
/* Widgets with a light background must keep dark text, otherwise the sidebar
   rule above renders them white-on-white and the value becomes invisible. */
[data-testid="stSidebar"] [data-baseweb="select"] *{color:#1c2541!important}
[data-testid="stSidebar"] input{color:#1c2541!important}
[data-baseweb="popover"] *{color:#1c2541!important}
[data-baseweb="popover"] li:hover{background:#eef1f8!important}
[data-testid="stSidebar"] .stSelectbox label, [data-testid="stSidebar"] .stSlider label{color:#9baac8!important;font-size:11px;text-transform:uppercase;letter-spacing:.06em}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p{color:#9baac8!important;font-size:11px}
div[data-testid="stButton"] button{background:#e16e28;color:white;border:none;border-radius:6px;font-weight:700;font-size:14px;padding:12px 0;width:100%;letter-spacing:.04em}
div[data-testid="stButton"] button:hover{background:#c85e20}
.card{background:white;border-radius:8px;border:1px solid #e2e6ea;padding:18px 22px;margin-bottom:16px}
.card h2{font-size:11px;font-weight:700;color:#1c2541;margin-bottom:13px;padding-bottom:7px;border-bottom:1px solid #e2e6ea;text-transform:uppercase;letter-spacing:.06em}
</style>
""", unsafe_allow_html=True)

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:20px 0 16px">
      <div style="font-size:13px;font-weight:700;color:white">SRI Method C</div>
      <div style="font-size:10px;color:#9baac8;margin-top:3px">Villa Segrate | 2026</div>
    </div>
    """, unsafe_allow_html=True)

    # Period options are read from the data rather than fixed, so adding a month
    # of CSVs widens the slider instead of leaving the new data unreachable.
    _periods = _period_options()
    month_range = st.select_slider(
        "Analysis Period",
        options=_periods,
        value=(_periods[0], _periods[-1]),
        format_func=_fmt_period,
    )
    m_start, m_end = month_range

    zone = st.selectbox("Climate Zone", ["South","Central","North"], index=0)
    btype = st.selectbox("Building Type", ["Residential","Non-Residential"], index=0)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    mode = st.radio(
        "Assessment Mode",
        ["Evidence-derived (Method C)", "Assessor-defined"],
        index=0,
        help=("Evidence-derived: the engine determines each functionality level from "
              "operational data, the Digital Building Logbook and the IFC models. "
              "Assessor-defined: the assessor sets each functionality level. "
              "Applicability, weighting and aggregation follow the same EU procedure "
              "in both modes; only the origin of the levels differs."),
    )
    override_mode = mode.startswith("Assessor")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    calc_clicked = st.button(
        "CALCULATE SRI" if not override_mode else "CALCULATE (ASSESSOR)",
        use_container_width=True, key="calc_sidebar")

    st.markdown("""
    <div style="margin-top:24px;padding-top:16px;border-top:1px solid #2e3d5c">
      <div style="font-size:10px;color:#9baac8;line-height:1.7">
        Data: Home Assistant CSV 2026 (240 days)<br>
        54 services | EU Reg. 2020/2155<br>
        Research prototype
      </div>
    </div>
    """, unsafe_allow_html=True)

# ── SESSION STATE ─────────────────────────────────────────────────────────────
# The two modes hold separate results. Switching mode therefore clears the other
# mode's dashboard from view rather than leaving a number on screen that was not
# produced the way the current mode says it was.
for _k in ("result", "assessor_result", "baseline"):
    if _k not in st.session_state:
        st.session_state[_k] = None
if st.session_state.get("last_mode") != mode:
    st.session_state["last_mode"] = mode
    st.session_state.assessor_result = None
    if override_mode:
        st.session_state.result = None

# The assessor table has to be seeded from the evidence-derived levels, so the
# baseline is computed even in assessor mode; it is simply not displayed.
_settings = (m_start, m_end, zone, btype)


def _baseline():
    cached = st.session_state.baseline
    if cached and cached[0] == _settings:
        return cached[1]
    with st.spinner("Reading operational data..."):
        res, svc, t0, t1 = run_sri(m_start, m_end, zone, btype)
    st.session_state.baseline = (_settings, (res, svc, t0, t1))
    return (res, svc, t0, t1)


if calc_clicked and not override_mode:
    result, svc_list, t_start, t_end = _baseline()
    st.session_state.result = (result, svc_list, t_start, t_end, zone, btype)

# ── HEADER ────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
def render_dashboard(result, svc_list, result_base, svc_base, t_start, t_end,
                     zone_used, btype_used, override_mode, n_changed=0):
    """Render the whole result view. Both modes share it, so the two assessments
    are presented identically and only their content differs."""
    sri_pct = result["sri_score_pct"]
    sri_cls = result["sri_class"]
    sri_lo  = result["sri_lower_bound_pct"]
    sri_hi  = result["sri_upper_bound_pct"]
    n_appl  = result["applicable_services"]
    color   = CLASS_COLORS.get(sri_cls, "#888")
    kf      = result.get("kf_breakdown", {})
    ic      = result.get("impact_criterion_breakdown", {})

    # Header bar
    st.markdown(f"""
    <div style="background:#1c2541;color:white;padding:20px 28px;border-radius:8px;
                display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <div>
        <div style="font-size:18px;font-weight:600">Smart Readiness Indicator | Villa Segrate</div>
        <div style="font-size:11px;color:#9baac8;margin-top:3px">
          Method C (Operational Assessment) &middot; EU Delegated Regulation 2020/2155 &middot; D3.1 Catalogue (54 services)
        </div>
        <div style="font-size:11px;color:#d0d8f0;margin-top:5px">
          Period: {t_start.strftime("%b %Y")} &ndash; {t_end.strftime("%b %Y")} &middot;
          Zone: {zone_used} &middot; {btype_used} &middot;
          Mode: {"Assessor-defined" if override_mode else "Evidence-derived (Method C)"}
        </div>
      </div>
      <div style="background:{color};border-radius:10px;padding:12px 22px;text-align:center;min-width:130px">
        <div style="font-size:10px;color:rgba(255,255,255,.8);text-transform:uppercase;letter-spacing:.08em">SRI Score</div>
        <div style="font-size:36px;font-weight:800;color:white;line-height:1">{sri_pct:.2f}%</div>
        <div style="font-size:14px;color:rgba(255,255,255,.85)">Class {sri_cls}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Disclaimer
    st.markdown("""
    <div style="background:#fff8e1;border-left:4px solid #f59f00;padding:8px 18px;
                font-size:11px;color:#5a4000;border-radius:4px;margin-bottom:16px">
      Research prototype only, not an officially approved SRI assessment.
      Results are for academic purposes (MSc Thesis, Politecnico di Milano).
    </div>
    """, unsafe_allow_html=True)

    # ── OVERRIDE COMPARISON ───────────────────────────────────────────────────
    if override_mode:
        b_pct = result_base["sri_score_pct"]
        b_cls = result_base["sri_class"]
        delta = sri_pct - b_pct
        d_col = "#1a9641" if delta > 0 else ("#d7191c" if delta < 0 else "#6c757d")
        d_txt = f"{delta:+.2f} pp" if delta != 0 else "identical"

        if n_changed == 0:
            note = ("No levels were changed. The assessor-defined score reproduces the "
                    "evidence-derived score exactly, confirming that both modes share "
                    "the same aggregation layer.")
            note_bg, note_bd, note_fg = "#e8f5e9", "#1a9641", "#1b5e20"
        else:
            note = (f"{n_changed} of 54 levels set by the assessor. The evidence-derived "
                    f"result remains the Method C assessment of record.")
            note_bg, note_bd, note_fg = "#f3e8fb", "#6a1b9a", "#4a1a7a"

        st.markdown(f"""
        <div class="card" style="margin-bottom:16px">
          <h2>Evidence-derived vs Assessor-defined</h2>
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:12px">
            <div style="text-align:center;background:#f8fafc;border-radius:6px;padding:14px;
                        border:2px solid #cbd5e1">
              <div style="font-size:9px;text-transform:uppercase;color:#6c757d;letter-spacing:.06em">
                Evidence-derived (Method C)</div>
              <div style="font-size:26px;font-weight:800;color:#1c2541;line-height:1.2">{b_pct:.2f}%</div>
              <div style="font-size:11px;color:#6c757d">Class {b_cls}</div>
            </div>
            <div style="text-align:center;background:#f8fafc;border-radius:6px;padding:14px;
                        border:2px solid #6a1b9a">
              <div style="font-size:9px;text-transform:uppercase;color:#6a1b9a;letter-spacing:.06em">
                Assessor-defined</div>
              <div style="font-size:26px;font-weight:800;color:#6a1b9a;line-height:1.2">{sri_pct:.2f}%</div>
              <div style="font-size:11px;color:#6c757d">Class {sri_cls}</div>
            </div>
            <div style="text-align:center;background:#f8fafc;border-radius:6px;padding:14px;
                        border:2px solid #cbd5e1">
              <div style="font-size:9px;text-transform:uppercase;color:#6c757d;letter-spacing:.06em">
                Difference</div>
              <div style="font-size:26px;font-weight:800;color:{d_col};line-height:1.2">{d_txt}</div>
              <div style="font-size:11px;color:#6c757d">{n_changed} service(s) changed</div>
            </div>
          </div>
          <div style="background:{note_bg};border-left:4px solid {note_bd};padding:8px 14px;
                      font-size:11px;color:{note_fg};border-radius:4px">{note}</div>
        </div>
        """, unsafe_allow_html=True)

    # ── ROW 1: SRI Scale + Stats ──────────────────────────────────────────────
    c1, c2 = st.columns([3, 2])

    with c1:
        st.markdown('<div class="card"><h2>SRI Class Scale</h2>', unsafe_allow_html=True)
        scale_html = '<div style="display:flex;gap:4px">'
        for cls, rng, _ in CLASS_RANGES:
            bg = CLASS_COLORS[cls]
            is_active = cls == sri_cls
            border = "3px solid white" if is_active else "none"
            arrow = f'<div style="text-align:center;color:{bg};font-size:12px;margin-top:3px">&#9650;</div>' if is_active else ""
            scale_html += f"""
            <div style="flex:1;text-align:center;background:{bg};padding:8px 2px;border-radius:5px;
                        font-weight:{"900" if is_active else "600"};color:white;
                        outline:{border};outline-offset:-3px">
              <div style="font-size:13px">{cls}</div>
              <div style="font-size:9px;color:rgba(255,255,255,.85)">{rng}</div>
            </div>"""
        scale_html += "</div>"
        # Add arrow under active class
        arrow_html = '<div style="display:flex;gap:4px;margin-top:2px">'
        for cls, _, _ in CLASS_RANGES:
            arrow_html += f'<div style="flex:1;text-align:center;color:{CLASS_COLORS[cls]};font-size:14px">{"&#9650;" if cls==sri_cls else ""}</div>'
        arrow_html += "</div>"
        unresolved_note = ""
        unresolved = result.get("unresolved_services", [])
        if unresolved:
            unresolved_note = f'<div style="font-size:11px;color:#6c757d;margin-top:14px;font-style:italic">&#9650; Current result: Class {sri_cls}, {sri_pct:.2f}% (Method C). With UNRESOLVED services at upper bound: <strong>{sri_hi:.2f}%</strong>, still within Class {sri_cls}. Uncertainty reflects {", ".join(unresolved)}.</div>'
        st.markdown(scale_html + arrow_html + unresolved_note + "</div>", unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="card"><h2>Summary</h2>', unsafe_allow_html=True)
        unresolved = result.get("unresolved_services", [])
        stats_html = f"""
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <div style="text-align:center;background:#f8fafc;border-radius:6px;padding:12px">
            <div style="font-size:26px;font-weight:800;color:#1c2541">{sri_pct:.2f}%</div>
            <div style="font-size:9px;text-transform:uppercase;color:#6c757d;letter-spacing:.06em">SRI Score</div>
          </div>
          <div style="text-align:center;background:{color};border-radius:6px;padding:12px">
            <div style="font-size:26px;font-weight:800;color:white">Class {sri_cls}</div>
            <div style="font-size:9px;text-transform:uppercase;color:rgba(255,255,255,.8);letter-spacing:.06em">Classification</div>
          </div>
          <div style="text-align:center;background:#f8fafc;border-radius:6px;padding:10px">
            <div style="font-size:20px;font-weight:800;color:#1c2541">{sri_lo:.2f}%</div>
            <div style="font-size:9px;text-transform:uppercase;color:#6c757d">Lower bound</div>
          </div>
          <div style="text-align:center;background:#f8fafc;border-radius:6px;padding:10px">
            <div style="font-size:20px;font-weight:800;color:#1c2541">{sri_hi:.2f}%</div>
            <div style="font-size:9px;text-transform:uppercase;color:#6c757d">Upper bound</div>
          </div>
          <div style="text-align:center;background:#f8fafc;border-radius:6px;padding:10px;grid-column:1/-1">
            <div style="font-size:20px;font-weight:800;color:#1c2541">{n_appl}/54</div>
            <div style="font-size:9px;text-transform:uppercase;color:#6c757d">Applicable services</div>
          </div>
        </div>
        </div>"""
        st.markdown(stats_html, unsafe_allow_html=True)

    # ── ROW 2: KF Cards ───────────────────────────────────────────────────────
    kf_styles = {
        "KF1": ("kf1","#1565c0","#e8f4fd","KF1","Energy Performance & Operation"),
        "KF2": ("kf2","#6a1b9a","#f5eefb","KF2","Adaptation to Occupant Needs"),
        "KF3": ("kf3","#bf360c","#fdf0eb","KF3","Response to Energy Grid"),
    }
    kf_cols = st.columns(3)
    for i, (kfk, kfv) in enumerate(kf.items()):
        _, color_kf, bg_kf, tag, name = kf_styles.get(kfk, ("","#333","#eee",kfk,""))
        pct = kfv["SR"]
        bar_w = min(pct, 100)
        with kf_cols[i]:
            st.markdown(f"""
            <div style="background:{bg_kf};border:2px solid {color_kf};border-radius:8px;padding:16px;height:100%">
              <div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.08em;color:{color_kf}">{tag}</div>
              <div style="font-size:12px;font-weight:700;color:#1e293b;margin:4px 0 10px;line-height:1.3">{name}</div>
              <div style="font-size:26px;font-weight:800;color:{color_kf};line-height:1">{pct:.2f}%</div>
              <div style="height:7px;background:rgba(0,0,0,.1);border-radius:4px;margin:8px 0">
                <div style="height:7px;background:{color_kf};border-radius:4px;width:{bar_w}%"></div>
              </div>
              <div style="font-size:10px;color:#64748b">{" &middot; ".join(kfv.get("ics",[]))}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Building Data + Technical Systems ─────────────────────────────────────
    bd1, bd2 = st.columns(2)
    with bd1:
        st.markdown("""<div class="card"><h2>Building Data</h2>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px 20px">
          <div style="display:flex;gap:8px;padding:4px 0;border-bottom:1px solid #f1f5f9"><span style="font-size:10.5px;color:#6c757d;font-weight:600;text-transform:uppercase;min-width:100px">Building</span><span style="font-size:12.5px">Villa Segrate</span></div>
          <div style="display:flex;gap:8px;padding:4px 0;border-bottom:1px solid #f1f5f9"><span style="font-size:10.5px;color:#6c757d;font-weight:600;text-transform:uppercase;min-width:100px">Location</span><span style="font-size:12.5px">Segrate (MI), Italy</span></div>
          <div style="display:flex;gap:8px;padding:4px 0;border-bottom:1px solid #f1f5f9"><span style="font-size:10.5px;color:#6c757d;font-weight:600;text-transform:uppercase;min-width:100px">Year Built</span><span style="font-size:12.5px">1993</span></div>
          <div style="display:flex;gap:8px;padding:4px 0;border-bottom:1px solid #f1f5f9"><span style="font-size:10.5px;color:#6c757d;font-weight:600;text-transform:uppercase;min-width:100px">Building Use</span><span style="font-size:12.5px">Residential</span></div>
          <div style="display:flex;gap:8px;padding:4px 0;border-bottom:1px solid #f1f5f9"><span style="font-size:10.5px;color:#6c757d;font-weight:600;text-transform:uppercase;min-width:100px">Type</span><span style="font-size:12.5px">Single-family villa</span></div>
          <div style="display:flex;gap:8px;padding:4px 0;border-bottom:1px solid #f1f5f9"><span style="font-size:10.5px;color:#6c757d;font-weight:600;text-transform:uppercase;min-width:100px">Net Floor Area</span><span style="font-size:12.5px">292 m²</span></div>
          <div style="display:flex;gap:8px;padding:4px 0"><span style="font-size:10.5px;color:#6c757d;font-weight:600;text-transform:uppercase;min-width:100px">Floors</span><span style="font-size:12.5px">4 (3 above grade + 1 underground)</span></div>
          <div style="display:flex;gap:8px;padding:4px 0"><span style="font-size:10.5px;color:#6c757d;font-weight:600;text-transform:uppercase;min-width:100px">Climate Zone</span><span style="font-size:12.5px">South (IT)</span></div>
        </div></div>""", unsafe_allow_html=True)
    with bd2:
        st.markdown("""<div class="card"><h2>Technical Systems</h2>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:0">
          <div style="font-size:11.5px;padding:5px 0;border-bottom:1px solid #f1f5f9;display:flex;align-items:center;gap:6px"><span style="width:5px;height:5px;border-radius:50%;background:#94a3b8;display:inline-block;flex-shrink:0"></span>INNOVA eHPoca 3in1 (HP)</div>
          <div style="font-size:11.5px;padding:5px 0;border-bottom:1px solid #f1f5f9;display:flex;align-items:center;gap:6px"><span style="width:5px;height:5px;border-radius:50%;background:#94a3b8;display:inline-block;flex-shrink:0"></span>IMMERGAS HERCULES SOLAR 25</div>
          <div style="font-size:11.5px;padding:5px 0;border-bottom:1px solid #f1f5f9;display:flex;align-items:center;gap:6px"><span style="width:5px;height:5px;border-radius:50%;background:#94a3b8;display:inline-block;flex-shrink:0"></span>Tado TRVs (5 zones)</div>
          <div style="font-size:11.5px;padding:5px 0;border-bottom:1px solid #f1f5f9;display:flex;align-items:center;gap:6px"><span style="width:5px;height:5px;border-radius:50%;background:#94a3b8;display:inline-block;flex-shrink:0"></span>Solar thermal CP4 XL</div>
          <div style="font-size:11.5px;padding:5px 0;border-bottom:1px solid #f1f5f9;display:flex;align-items:center;gap:6px"><span style="width:5px;height:5px;border-radius:50%;background:#94a3b8;display:inline-block;flex-shrink:0"></span>PV 2.4 kWp + Battery + BMS</div>
          <div style="font-size:11.5px;padding:5px 0;border-bottom:1px solid #f1f5f9;display:flex;align-items:center;gap:6px"><span style="width:5px;height:5px;border-radius:50%;background:#94a3b8;display:inline-block;flex-shrink:0"></span>ComfoAir Q450 MVHR</div>
          <div style="font-size:11.5px;padding:5px 0;display:flex;align-items:center;gap:6px"><span style="width:5px;height:5px;border-radius:50%;background:#94a3b8;display:inline-block;flex-shrink:0"></span>AC splits x5 (ESPHome/MTS200B)</div>
          <div style="font-size:11.5px;padding:5px 0;display:flex;align-items:center;gap:6px"><span style="width:5px;height:5px;border-radius:50%;background:#94a3b8;display:inline-block;flex-shrink:0"></span>Shelly Pro 3EM (sub-metering)</div>
        </div></div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── ROW 3: IC Table ───────────────────────────────────────────────────────
    st.markdown('<div class="card"><h2>Impact Criteria Breakdown</h2>', unsafe_allow_html=True)
    ic_html = """<table style="width:100%;border-collapse:collapse;font-size:12px">
    <thead><tr style="background:#f0f2f5">
      <th style="padding:6px 10px;text-align:left;font-size:10.5px;color:#495057;text-transform:uppercase;letter-spacing:.04em;border-bottom:2px solid #dee2e6">Impact Criterion</th>
      <th style="padding:6px 10px;text-align:right;font-size:10.5px;color:#495057;text-transform:uppercase;letter-spacing:.04em;border-bottom:2px solid #dee2e6">SR (%)</th>
      <th style="padding:6px 10px;text-align:right;font-size:10.5px;color:#495057;text-transform:uppercase;letter-spacing:.04em;border-bottom:2px solid #dee2e6">Weight</th>
      <th style="padding:6px 10px;text-align:right;font-size:10.5px;color:#495057;text-transform:uppercase;letter-spacing:.04em;border-bottom:2px solid #dee2e6">Contribution</th>
    </tr></thead><tbody>""".replace(
        "__LASTCOL__",
        "Official criterion for the level set" if override_mode else "Justification")
    total_contrib = 0
    for icn, icv in ic.items():
        sr = icv["SR"]; w = icv["weight"]; c = icv["contribution"]
        total_contrib += c
        bar_w = min(sr, 100)
        ic_html += f"""<tr>
          <td style="padding:6px 10px;border-bottom:1px solid #e9ecef;font-weight:600">{icn}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #e9ecef;text-align:right">
            <div style="display:flex;align-items:center;justify-content:flex-end;gap:8px">
              <div style="background:#e9ecef;border-radius:3px;height:6px;width:80px;position:relative;overflow:hidden">
                <div style="position:absolute;top:0;left:0;height:100%;width:{bar_w}%;background:#1c6bb5;border-radius:3px"></div>
              </div>
              {sr:.2f}%
            </div>
          </td>
          <td style="padding:6px 10px;border-bottom:1px solid #e9ecef;text-align:right;color:#6c757d">{w:.4f}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #e9ecef;text-align:right;font-weight:600;color:#1c2541">{c:.2f}</td>
        </tr>"""
    ic_html += f"""<tr style="background:#f8fafc;font-weight:700;border-top:2px solid #dee2e6">
      <td colspan="3" style="padding:7px 10px;color:#1c2541">TOTAL SRI</td>
      <td style="padding:7px 10px;text-align:right;font-size:14px;color:#1c2541">{total_contrib:.2f}%</td>
    </tr></tbody></table></div>"""
    st.markdown(ic_html, unsafe_allow_html=True)

    # ── ROW 4: Service Table ──────────────────────────────────────────────────
    _detail_title = ("Assessment detail (54 services)" if override_mode
                     else "Service Assessment Detail (54 services)")
    st.markdown(f'<div class="card"><h2>{_detail_title}</h2>', unsafe_allow_html=True)

    STATUS_BADGE = {
        "VERIFIED":             ('<span style="background:#d4edda;color:#155724;border:1px solid #c3e6cb;padding:2px 7px;border-radius:10px;font-size:10px;font-weight:600">Verified</span>', True),
        "PARTIAL_EVIDENCE":     ('<span style="background:#fff3cd;color:#856404;border:1px solid #ffeeba;padding:2px 7px;border-radius:10px;font-size:10px;font-weight:600">Partial</span>', True),
        "UNRESOLVED":           ('<span style="background:#e8d5f5;color:#4a1a7a;border:1px solid #d6aef0;padding:2px 7px;border-radius:10px;font-size:10px;font-weight:600">Unresolved</span>', True),
        "N/A_EXPLICIT_ABSENCE": ('<span style="background:#f1f3f5;color:#868e96;border:1px solid #dee2e6;padding:2px 7px;border-radius:10px;font-size:10px;font-weight:600">N/A</span>', False),
        "N/A_NOT_EVIDENCED":    ('<span style="background:#f1f3f5;color:#868e96;border:1px solid #dee2e6;padding:2px 7px;border-radius:10px;font-size:10px;font-weight:600">N/A</span>', False),
    }
    FL_STYLE = {
        None: 'background:#fafafa;color:#9e9e9e;border-color:#e0e0e0',
        0:    'background:#f5f5f5;color:#616161;border-color:#e0e0e0',
        1:    'background:#fff3e0;color:#e65100;border-color:#ffcc80',
        2:    'background:#e3f2fd;color:#1565c0;border-color:#90caf9',
        3:    'background:#e8f5e9;color:#2e7d32;border-color:#a5d6a7',
        4:    'background:#f1f8e9;color:#33691e;border-color:#c5e1a5',
    }

    tbl = """<div style="border-radius:6px;border:1px solid #e2e6ea;overflow:hidden;max-height:700px;overflow-y:auto">
    <table style="width:100%;border-collapse:collapse;font-size:11.5px;table-layout:fixed">
    <thead><tr style="background:#1c2541">
      <th style="padding:8px 10px;text-align:left;color:white;font-size:10px;text-transform:uppercase;letter-spacing:.05em;width:70px;position:sticky;top:0">Code</th>
      <th style="padding:8px 10px;text-align:left;color:white;font-size:10px;text-transform:uppercase;letter-spacing:.05em;width:190px;position:sticky;top:0">Service</th>
      <th style="padding:8px 10px;text-align:left;color:white;font-size:10px;text-transform:uppercase;letter-spacing:.05em;width:100px;position:sticky;top:0">Status</th>
      <th style="padding:8px 10px;text-align:left;color:white;font-size:10px;text-transform:uppercase;letter-spacing:.05em;width:60px;position:sticky;top:0">FL</th>
      <th style="padding:8px 10px;text-align:left;color:white;font-size:10px;text-transform:uppercase;letter-spacing:.05em;position:sticky;top:0">__LASTCOL__</th>
    </tr></thead><tbody>""".replace(
        "__LASTCOL__",
        "Official criterion for the level set" if override_mode else "Justification")

    domain_order = ["Heating","DHW","Cooling","Ventilation","Lighting","Dynamic_Envelope","Electricity","EV_Charging","Monitoring_Control"]
    domain_labels = {"Dynamic_Envelope":"Dynamic Envelope","EV_Charging":"EV Charging","Monitoring_Control":"Monitoring & Control"}
    by_domain = {d: [] for d in domain_order}
    for s in svc_list:
        by_domain.get(s["domain"], []).append(s)

    for dom in domain_order:
        svcs = by_domain[dom]
        if not svcs:
            continue
        label = domain_labels.get(dom, dom)
        tbl += f'<tr><td colspan="5" style="background:#e8ecf5;font-size:11px;font-weight:700;color:#1c2541;padding:6px 10px;border-top:2px solid #c5cff8;border-bottom:1px solid #c5cff8;text-transform:uppercase;letter-spacing:.04em">{label}</td></tr>'
        for s in svcs:
            badge_html, _ = STATUS_BADGE.get(s["applicability_status"], ('',''))
            fl = s["level_achieved"]
            fl_style = FL_STYLE.get(fl, FL_STYLE[None])
            fl_label = f"L{fl}/{s['level_max']}" if fl is not None else "N/A"
            if override_mode:
                # A level chosen by the assessor has no evidence-based
                # justification, so the column carries the official criterion
                # for the level selected instead of an empty cell.
                just = s.get("official_criterion", "") or "-"
            else:
                just = (s["justification"] or "")[:180] + ("..." if len(s.get("justification","")) > 180 else "")
            if s.get("assessor_changed") or s.get("overridden"):
                row_style = "border-bottom:1px solid #e9ecef;background:#faf5ff;box-shadow:inset 3px 0 0 #6a1b9a"
                badge_html = ('<span style="background:#e8d5f5;color:#4a1a7a;border:1px solid #d6aef0;'
                              'padding:2px 7px;border-radius:10px;font-size:10px;font-weight:600">Override</span>')
            else:
                row_style = "border-bottom:1px solid #e9ecef"
            tbl += f"""<tr style="{row_style}">
              <td style="padding:7px 10px;font-weight:700;font-family:monospace;color:#1c2541;white-space:nowrap">{s["service"]}</td>
              <td style="padding:7px 10px;color:#1a1a1a">{s["description"]}</td>
              <td style="padding:7px 10px">{badge_html}</td>
              <td style="padding:7px 10px"><span style="padding:2px 8px;border-radius:8px;font-size:10.5px;font-weight:700;border:1px solid;white-space:nowrap;{fl_style}">{fl_label}</span></td>
              <td style="padding:7px 10px;font-size:11px;color:#495057;line-height:1.5">{just}</td>
            </tr>"""

    tbl += "</tbody></table></div></div>"
    st.markdown(tbl, unsafe_allow_html=True)

    # ── EXPORT ────────────────────────────────────────────────────────────────
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    export = {
        "period": f"{t_start.date()} to {t_end.date()}",
        "climate_zone": zone_used,
        "building_type": btype_used,
        "assessment_mode": "assessor_defined" if override_mode else "evidence_derived_method_c",
        "sri": result,
        "services": svc_list,
    }
    if override_mode:
        export["evidence_derived_baseline"] = {
            "sri_score_pct": result_base["sri_score_pct"],
            "sri_class": result_base["sri_class"],
            "sri_lower_bound_pct": result_base["sri_lower_bound_pct"],
            "sri_upper_bound_pct": result_base["sri_upper_bound_pct"],
        }
        export["assessor_delta_pp"] = round(result["sri_score_pct"] - result_base["sri_score_pct"], 2)
        export["assessor_defined_services"] = [
            {"service": s["service"],
             "derived_status": s.get("derived_status"),
             "derived_level": s.get("derived_level"),
             "override_status": s["applicability_status"],
             "override_level": s["level_achieved"]}
            for s in svc_list if s.get("assessor_changed") or s.get("overridden")
        ]
    mode_tag = "assessor" if override_mode else "evidence"
    st.download_button("Download JSON", data=json.dumps(export, indent=2, default=str),
        file_name=f"sri_method_c_{mode_tag}_{t_start.strftime('%Y%m')}-{t_end.strftime('%Y%m')}.json",
        mime="application/json")



def render_welcome():
    # ── WELCOME SCREEN ────────────────────────────────────────────────────────
    st.markdown("""
    <div style="background:#1c2541;color:white;padding:20px 28px;border-radius:8px;margin-bottom:16px">
      <div style="font-size:18px;font-weight:600">Smart Readiness Indicator | Villa Segrate</div>
      <div style="font-size:11px;color:#9baac8;margin-top:3px">
        Method C (Operational Assessment) &middot; EU Delegated Regulation 2020/2155 &middot; D3.1 Catalogue (54 services)
      </div>
    </div>
    <div style="background:white;border-radius:8px;border:1px solid #e2e6ea;padding:40px;text-align:center">
      <div style="font-size:48px;margin-bottom:16px">🏠</div>
      <div style="font-size:16px;font-weight:600;color:#1c2541;margin-bottom:8px">Select parameters and press CALCULATE SRI</div>
      <div style="font-size:12px;color:#6c757d">
        Set the analysis period, climate zone, and building type in the sidebar,<br>
        then click the button to run the full 54-service assessment.
      </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  ASSESSOR-DEFINED MODE
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(show_spinner=False)
def _official_catalog(fingerprint: str = ""):
    """The official service catalogue, so the level options an assessor sees are
    the EU wording rather than bare numbers."""
    eng = _load_engine()
    try:
        return eng._load_official()
    except Exception:
        return {}


def _level_options(code: str, max_fl: int):
    """(value, label) for every level of a service, labelled with its official text."""
    cat = _official_catalog(_engine_fingerprint()).get(code, {})
    levels = cat.get("levels", {})
    out = []
    for lv in range(0, int(max_fl) + 1):
        desc = levels.get(str(lv), {}).get("description", "")
        out.append((lv, f"L{lv} — {desc}" if desc else f"L{lv}"))
    return out


def _level_text(code: str, lv) -> str:
    if lv is None:
        return ""
    cat = _official_catalog(_engine_fingerprint()).get(code, {})
    return cat.get("levels", {}).get(str(int(lv)), {}).get("description", "")


DOMAIN_ORDER = ["Heating", "DHW", "Cooling", "Ventilation", "Lighting",
                "Dynamic_Envelope", "Electricity", "EV_Charging", "Monitoring_Control"]
DOMAIN_LABELS = {"Dynamic_Envelope": "Dynamic Envelope", "EV_Charging": "EV Charging",
                 "Monitoring_Control": "Monitoring & Control"}


def render_assessor_mode():
    eng = _load_engine()
    result_base, svc_base, t_start, t_end = _baseline()

    # Results, if the assessor has already calculated. Rendered first so the
    # numbers sit at the top of the page and the worksheet stays at the bottom.
    stored = st.session_state.assessor_result
    if stored and stored[0] == _settings:
        _res, _svc, _n = stored[1]
        render_dashboard(_res, _svc, result_base, svc_base, t_start, t_end,
                         zone, btype, True, n_changed=_n)
        _render_changes_summary(eng, _svc, svc_base, result_base)
    else:
        st.markdown(f"""
        <div style="background:#1c2541;color:white;padding:20px 28px;border-radius:8px;margin-bottom:16px">
          <div style="font-size:18px;font-weight:600">Smart Readiness Indicator | Villa Segrate</div>
          <div style="font-size:11px;color:#9baac8;margin-top:3px">
            Assessor-defined assessment &middot; EU Delegated Regulation 2020/2155
            &middot; D3.1 Catalogue (54 services)
          </div>
        </div>
        <div style="background:#f3e8fb;border-left:4px solid #6a1b9a;padding:10px 18px;
                    font-size:12px;color:#4a1a7a;border-radius:4px;margin-bottom:18px">
          Set a functionality level for each service below, then press Calculate.
          Levels are listed with their official wording from the SRI calculation
          sheet. Applicability, weighting and aggregation follow the same EU
          procedure as the evidence-derived mode; only the origin of the levels
          differs.
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="card"><h2>Assessor worksheet</h2>', unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size:11.5px;color:#495057;line-height:1.6;margin-bottom:6px'>"
        "The <em>Evidence</em> column shows the level the engine derived from operational "
        "data. Changing a level reveals what the official catalogue requires for it."
        "</div>", unsafe_allow_html=True)

    if st.button("Reset all to evidence-derived levels", key="reset_assessor"):
        for s in svc_base:
            st.session_state.pop(f"fl_{s['service']}", None)
            st.session_state.pop(f"ap_{s['service']}", None)
        st.session_state.assessor_result = None
        st.rerun()

    by_dom = {}
    for s in svc_base:
        by_dom.setdefault(s["domain"], []).append(s)

    selections = {}
    for dom in DOMAIN_ORDER:
        svcs = by_dom.get(dom, [])
        if not svcs:
            continue
        label = DOMAIN_LABELS.get(dom, dom)
        with st.expander(f"{label}  ({len(svcs)} services)", expanded=False):
            for s in svcs:
                code = s["service"]
                mx = int(s["level_max"])
                derived = seed_fl(s)
                derived_ap = seed_applicable(s)
                opts = _level_options(code, mx)

                c1, c2 = st.columns([1, 5])
                with c1:
                    applicable = st.checkbox(
                        "Applicable", value=derived_ap, key=f"ap_{code}",
                        help="Unchecking removes the service from both the numerator "
                             "and the denominator, as the EU procedure prescribes for "
                             "services that do not apply to the building.")
                with c2:
                    st.markdown(
                        f"<div style='font-size:12.5px;font-weight:700;color:#1c2541'>"
                        f"{code} &middot; {s['description']}</div>"
                        f"<div style='font-size:10.5px;color:#6c757d'>Evidence-derived: "
                        f"L{derived}{'' if derived_ap else ' (not applicable)'}</div>",
                        unsafe_allow_html=True)
                    if applicable:
                        chosen = st.selectbox(
                            "Functionality level", options=[o[0] for o in opts],
                            index=min(derived, mx),
                            format_func=lambda v, o=opts: o[v][1],
                            key=f"fl_{code}", label_visibility="collapsed")
                    else:
                        chosen = None
                        st.caption("Excluded from the assessment.")

                if applicable and chosen is not None and chosen != derived:
                    st.markdown(
                        f"<div style='background:#fff8e1;border-left:3px solid #f59f00;"
                        f"padding:7px 12px;border-radius:4px;font-size:11.5px;color:#5a4000;"
                        f"margin:4px 0 10px 0'><strong>L{chosen} requires</strong> &mdash; "
                        f"{_level_text(code, chosen)}</div>", unsafe_allow_html=True)
                    with st.expander("Details: what the engine measured", expanded=False):
                        st.caption(s.get("justification", "") or "No justification recorded.")
                        if s.get("data"):
                            st.json(s["data"], expanded=False)
                st.markdown("<hr style='margin:6px 0;border:none;border-top:1px solid #eef1f8'>",
                            unsafe_allow_html=True)
                selections[code] = (applicable, chosen)

    st.markdown("</div>", unsafe_allow_html=True)

    if st.button("CALCULATE (ASSESSOR)", use_container_width=True, key="calc_bottom") \
            or calc_clicked:
        _run_assessor(eng, svc_base, selections)
        st.rerun()


def _run_assessor(eng, svc_base, selections):
    """Build the assessor's service list and score it through the same aggregation."""
    out, n_changed = [], 0
    for s in svc_base:
        code = s["service"]
        applicable, chosen = selections.get(code, (seed_applicable(s), seed_fl(s)))
        n = dict(s)
        if not applicable:
            if seed_applicable(s):
                n_changed += 1
            n["applicability_status"] = "N/A_EXPLICIT_ABSENCE"
            n["level_achieved"] = None
            n["assessor_changed"] = seed_applicable(s)
        else:
            lv = seed_fl(s) if chosen is None else int(chosen)
            changed = (lv != seed_fl(s)) or (not seed_applicable(s))
            if changed:
                n_changed += 1
            n["applicability_status"] = "VERIFIED"
            n["level_achieved"] = lv
            n["assessor_changed"] = changed
        n["derived_level"] = s["level_achieved"]
        n["derived_status"] = s["applicability_status"]
        n["official_criterion"] = _level_text(code, n["level_achieved"])
        out.append(n)
    res = score_only(out, zone, btype)
    st.session_state.assessor_result = (_settings, (res, out, n_changed))


def _render_changes_summary(eng, svc_list, svc_base, result_base):
    """Every service the assessor moved, with the points it contributes and the
    official requirement for the level chosen."""
    changed = [s for s in svc_list if s.get("assessor_changed")]
    if not changed:
        return
    base_map = {s["service"]: s for s in svc_base}
    rows = ""
    total = 0.0
    for s in sorted(changed, key=lambda x: x["service"]):
        one = [dict(b) for b in svc_base]
        for b in one:
            if b["service"] == s["service"]:
                b["level_achieved"] = s["level_achieved"]
                b["applicability_status"] = s["applicability_status"]
        delta = score_only(one, zone, btype)["sri_score_pct"] - result_base["sri_score_pct"]
        total += delta
        frm = base_map[s["service"]]["level_achieved"]
        to = s["level_achieved"]
        col = "#1a9641" if delta > 0 else ("#d7191c" if delta < 0 else "#6c757d")
        rows += (f"<tr style='border-bottom:1px solid #e9ecef'>"
                 f"<td style='padding:7px 10px;font-weight:700;font-family:monospace'>{s['service']}</td>"
                 f"<td style='padding:7px 10px'>{s['description']}</td>"
                 f"<td style='padding:7px 10px;text-align:center'>"
                 f"{'L'+str(frm) if frm is not None else 'N/A'}</td>"
                 f"<td style='padding:7px 10px;text-align:center;font-weight:700'>"
                 f"{'L'+str(to) if to is not None else 'N/A'}</td>"
                 f"<td style='padding:7px 10px;text-align:right;font-weight:700;color:{col}'>"
                 f"{delta:+.2f} pp</td>"
                 f"<td style='padding:7px 10px;font-size:11px;color:#495057'>"
                 f"{s.get('official_criterion','')}</td></tr>")
    st.markdown(f"""
    <div class="card"><h2>Changes against the evidence-derived assessment</h2>
    <table style="width:100%;border-collapse:collapse;font-size:12px">
      <thead><tr style="background:#1c2541">
        <th style="padding:8px 10px;text-align:left;color:white;font-size:10px;text-transform:uppercase">Service</th>
        <th style="padding:8px 10px;text-align:left;color:white;font-size:10px;text-transform:uppercase"></th>
        <th style="padding:8px 10px;text-align:center;color:white;font-size:10px;text-transform:uppercase">From</th>
        <th style="padding:8px 10px;text-align:center;color:white;font-size:10px;text-transform:uppercase">To</th>
        <th style="padding:8px 10px;text-align:right;color:white;font-size:10px;text-transform:uppercase">Impact</th>
        <th style="padding:8px 10px;text-align:left;color:white;font-size:10px;text-transform:uppercase">That level requires</th>
      </tr></thead><tbody>{rows}
      <tr style="background:#f8fafc;font-weight:700;border-top:2px solid #dee2e6">
        <td colspan="4" style="padding:8px 10px;color:#1c2541">
          Sum of individual contributions</td>
        <td style="padding:8px 10px;text-align:right;font-size:14px;color:#1c2541">{total:+.2f} pp</td>
        <td></td></tr>
    </tbody></table>
    <div style="font-size:10.5px;color:#6c757d;margin-top:8px;font-style:italic">
      Each impact is measured by changing that service alone against the
      evidence-derived assessment. Because impact criteria are normalised across
      services, the individual contributions do not necessarily sum to the
      difference between the two totals.
    </div></div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE FLOW
# ══════════════════════════════════════════════════════════════════════════════
if not override_mode:
    if st.session_state.result:
        _res, _svc, _t0, _t1, _z, _b = st.session_state.result
        render_dashboard(_res, _svc, _res, _svc, _t0, _t1, _z, _b, False)
    else:
        render_welcome()
else:
    render_assessor_mode()
