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
MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug"]
NA_SET = {"N/A_NOT_EVIDENCED","N/A_EXPLICIT_ABSENCE"}

# ── ENGINE ────────────────────────────────────────────────────────────────────
@st.cache_resource
def _load_engine():
    with open(ENGINE_PATH, encoding="utf-8") as f:
        code = f.read()
    code = code.replace('if __name__ == "__main__":', 'if False:')
    mod = types.ModuleType("sri_engine")
    mod.__file__ = ENGINE_PATH
    exec(compile(code, ENGINE_PATH, "exec"), mod.__dict__)
    return mod

@st.cache_data(show_spinner=False)
def _load_all_csv():
    eng = _load_engine()
    return eng.load_csv_files(eng.CSV_DIR)

def run_sri(m_start, m_end, zone, btype):
    eng = _load_engine()
    all_csv = _load_all_csv()
    t_start = pd.Timestamp(f"2026-{m_start:02d}-01", tz="UTC")
    last_day = calendar.monthrange(2026, m_end)[1]
    t_end = pd.Timestamp(f"2026-{m_end:02d}-{last_day} 23:59:59", tz="UTC")
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

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="SRI Method C | Villa Segrate", page_icon="🏠", layout="wide")

st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:#f2f4f7}
[data-testid="stSidebar"]{background:#1c2541}
[data-testid="stSidebar"] *{color:white!important}
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

    month_range = st.select_slider(
        "Analysis Period (2026)",
        options=list(range(1,9)),
        value=(1,8),
        format_func=lambda x: MONTHS[x-1],
    )
    m_start, m_end = month_range

    zone = st.selectbox("Climate Zone", ["South","Central","North"], index=0)
    btype = st.selectbox("Building Type", ["Residential","Non-Residential"], index=0)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    calc_clicked = st.button("CALCULATE SRI", use_container_width=True)

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
if "result" not in st.session_state:
    st.session_state.result = None

if calc_clicked:
    with st.spinner("Running SRI assessment..."):
        result, svc_list, t_start, t_end = run_sri(m_start, m_end, zone, btype)
    st.session_state.result = (result, svc_list, t_start, t_end, zone, btype)

# ── HEADER ────────────────────────────────────────────────────────────────────
if st.session_state.result:
    result, svc_list, t_start, t_end, zone_used, btype_used = st.session_state.result
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
          Zone: {zone_used} &middot; {btype_used}
        </div>
      </div>
      <div style="background:{color};border-radius:10px;padding:12px 22px;text-align:center;min-width:130px">
        <div style="font-size:10px;color:rgba(255,255,255,.8);text-transform:uppercase;letter-spacing:.08em">SRI Score</div>
        <div style="font-size:36px;font-weight:800;color:white;line-height:1">{sri_pct:.1f}%</div>
        <div style="font-size:14px;color:rgba(255,255,255,.85)">Class {sri_cls}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Disclaimer
    st.markdown("""
    <div style="background:#fff8e1;border-left:4px solid #f59f00;padding:8px 18px;
                font-size:11px;color:#5a4000;border-radius:4px;margin-bottom:16px">
      Research prototype only &mdash; not an officially approved SRI assessment.
      Results are for academic purposes (MSc Thesis, Politecnico di Milano).
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
            <div style="font-size:26px;font-weight:800;color:#1c2541">{sri_pct:.1f}%</div>
            <div style="font-size:9px;text-transform:uppercase;color:#6c757d;letter-spacing:.06em">SRI Score</div>
          </div>
          <div style="text-align:center;background:{color};border-radius:6px;padding:12px">
            <div style="font-size:26px;font-weight:800;color:white">Class {sri_cls}</div>
            <div style="font-size:9px;text-transform:uppercase;color:rgba(255,255,255,.8);letter-spacing:.06em">Classification</div>
          </div>
          <div style="text-align:center;background:#f8fafc;border-radius:6px;padding:10px">
            <div style="font-size:20px;font-weight:800;color:#1c2541">{sri_lo:.1f}%</div>
            <div style="font-size:9px;text-transform:uppercase;color:#6c757d">Lower bound</div>
          </div>
          <div style="text-align:center;background:#f8fafc;border-radius:6px;padding:10px">
            <div style="font-size:20px;font-weight:800;color:#1c2541">{sri_hi:.1f}%</div>
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
              <div style="font-size:26px;font-weight:800;color:{color_kf};line-height:1">{pct:.1f}%</div>
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
    </tr></thead><tbody>"""
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
              {sr:.1f}%
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
    st.markdown('<div class="card"><h2>Service Assessment Detail (54 services)</h2>', unsafe_allow_html=True)

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
      <th style="padding:8px 10px;text-align:left;color:white;font-size:10px;text-transform:uppercase;letter-spacing:.05em;position:sticky;top:0">Justification</th>
    </tr></thead><tbody>"""

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
            just = (s["justification"] or "")[:180] + ("..." if len(s.get("justification","")) > 180 else "")
            tbl += f"""<tr style="border-bottom:1px solid #e9ecef">
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
    export = {"period": f"{t_start.date()} to {t_end.date()}", "climate_zone": zone_used,
              "building_type": btype_used, "sri": result, "services": svc_list}
    st.download_button("Download JSON", data=json.dumps(export, indent=2, default=str),
        file_name=f"sri_method_c_{t_start.strftime('%Y%m')}-{t_end.strftime('%Y%m')}.json",
        mime="application/json")

else:
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
