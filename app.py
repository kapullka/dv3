# app.py — Employee management with styled UI, fixed panel, Plan editable, Clear Data button

import streamlit as st
import pandas as pd
import calendar
from datetime import date, datetime, timedelta
import json
import os
from typing import Dict, Any, List, Tuple

APP_TITLE = "🚚 SunTrans Profit"
DATA_FILE = "dispatch_data.json"

st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)

# -------------------- Utilities: calendar / keys --------------------
def parse_month_key(key: str) -> Tuple[int, int]:
    try:
        dt = datetime.strptime(key, "%B %Y")
        return dt.year, dt.month
    except Exception:
        t = date.today()
        return t.year, t.month

def weeks_covering_month(year: int, month: int) -> List[List[date]]:
    first = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    last = date(year, month, last_day)
    start_monday = first - timedelta(days=first.weekday())
    weeks = []
    cur = start_monday
    while cur <= last:
        week = [cur + timedelta(days=i) for i in range(7)]
        weeks.append(week)
        cur += timedelta(days=7)
    return weeks

def month_sort_key(k: str, data: Dict[str, Any]) -> Tuple[int, int]:
    md = data.get(k, {})
    y = md.get("year")
    m = md.get("month")
    if isinstance(y, int) and isinstance(m, int):
        return (y, m)
    return parse_month_key(k)

# -------------------- Load & normalize old data --------------------
def load_data() -> Dict[str, Any]:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            os.rename(DATA_FILE, DATA_FILE + ".bak")
            raw = {}
    else:
        raw = {}

    data: Dict[str, Any] = {}

    for key, val in raw.items():
        md = dict(val) if isinstance(val, dict) else {}
        if "year" not in md or "month" not in md:
            y, m = parse_month_key(key)
            md.setdefault("year", y)
            md.setdefault("month", m)
        md.setdefault("employees", [])
        if "employee_plans" not in md:
            md["employee_plans"] = {e: 0.0 for e in md.get("employees", [])}

        expected = weeks_covering_month(md["year"], md["month"])
        old_weeks = md.get("weeks", [])
        new_weeks = []
        for week_dates in expected:
            start = week_dates[0]; end = week_dates[-1]
            label = f"{start.strftime('%b %d')} - {end.strftime('%b %d')}"
            old_week = next((ow for ow in old_weeks if isinstance(ow, dict) and ow.get("label") == label), None)
            week_obj = {"label": label, "daily_profits": {}, "total": 0.0}
            for emp in md.get("employees", []):
                week_obj["daily_profits"].setdefault(emp, {})
                for d in week_dates:
                    iso = d.isoformat()
                    if old_week and emp in old_week.get("daily_profits", {}):
                        week_obj["daily_profits"][emp][iso] = float(old_week["daily_profits"][emp].get(iso, 0.0) or 0.0)
                    else:
                        week_obj["daily_profits"][emp][iso] = 0.0
            new_weeks.append(week_obj)
        md["weeks"] = new_weeks

        for emp in md["employees"]:
            md["employee_plans"].setdefault(emp, 0.0)
        data[key] = md

    if not data:
        t = date.today()
        key = t.strftime("%B %Y")
        data[key] = {"year": t.year, "month": t.month, "employees": [], "employee_plans": {}, "weeks": []}
        for week_dates in weeks_covering_month(t.year, t.month):
            start = week_dates[0]; end = week_dates[-1]
            label = f"{start.strftime('%b %d')} - {end.strftime('%b %d')}"
            data[key]["weeks"].append({"label": label, "daily_profits": {}, "total": 0.0})
    return data

def save_data(data: Dict[str, Any]):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# -------------------- Core ops: add/remove employee propagation --------------------
def add_employee_to_month_and_future(data: Dict[str, Any], month_key: str, name: str):
    sy, sm = parse_month_key(month_key)
    for k, md in data.items():
        y, m = md.get("year", sy), md.get("month", sm)
        if (y, m) >= (sy, sm):
            if name not in md["employees"]:
                md["employees"].append(name)
                md.setdefault("employee_plans", {})[name] = 0.0
                expected_weeks = weeks_covering_month(md["year"], md["month"])
                if len(md.get("weeks", [])) != len(expected_weeks):
                    old_weeks = md.get("weeks", [])
                    new_weeks = []
                    for idx, week_dates in enumerate(expected_weeks):
                        start = week_dates[0]; end = week_dates[-1]
                        label = f"{start.strftime('%b %d')} - {end.strftime('%b %d')}"
                        old_week = next((ow for ow in old_weeks if isinstance(ow, dict) and ow.get("label") == label), None)
                        wk = {"label": label, "daily_profits": {}, "total": 0.0}
                        for emp in md["employees"]:
                            wk["daily_profits"].setdefault(emp, {})
                            for d in week_dates:
                                iso = d.isoformat()
                                if old_week and "daily_profits" in old_week and emp in old_week["daily_profits"]:
                                    wk["daily_profits"][emp][iso] = float(old_week["daily_profits"][emp].get(iso, 0.0) or 0.0)
                                else:
                                    wk["daily_profits"][emp][iso] = 0.0
                        new_weeks.append(wk)
                    md["weeks"] = new_weeks
                else:
                    for idx, wk in enumerate(md.get("weeks", [])):
                        week_dates = weeks_covering_month(md["year"], md["month"])[idx]
                        wk.setdefault("daily_profits", {})
                        wk["daily_profits"].setdefault(name, {})
                        for d in week_dates:
                            iso = d.isoformat()
                            wk["daily_profits"][name].setdefault(iso, 0.0)
    save_data(data)

def remove_employee_from_month_and_future(data: Dict[str, Any], month_key: str, name: str):
    sy, sm = parse_month_key(month_key)
    for k, md in data.items():
        y, m = md.get("year", sy), md.get("month", sm)
        if (y, m) >= (sy, sm):
            if name in md.get("employees", []):
                md["employees"].remove(name)
            if "employee_plans" in md and name in md["employee_plans"]:
                md["employee_plans"].pop(name, None)
            for wk in md.get("weeks", []):
                if "daily_profits" in wk and name in wk["daily_profits"]:
                    wk["daily_profits"].pop(name, None)
    save_data(data)

# -------------------- Initialize data --------------------
data = load_data()
save_data(data)

# ---------- UI: Top controls (month select + add month) ----------
month_keys = sorted(list(data.keys()), key=lambda k: month_sort_key(k, data), reverse=True)
if not month_keys:
    t = date.today()
    key = t.strftime("%B %Y")
    data[key] = {"year": t.year, "month": t.month, "employees": [], "employee_plans": {}, "weeks": []}
    month_keys = [key]
    save_data(data)

col_left, col_right = st.columns([3, 1])
with col_left:
    selected_month = st.selectbox("Select month", month_keys, index=0)
with col_right:
    if st.button("➕ Add New Month"):
        newest_key = max(month_keys, key=lambda k: month_sort_key(k, data))
        ny, nm = parse_month_key(newest_key)
        newest_dt = date(ny, nm, 1)
        nxt = newest_dt.replace(day=28) + timedelta(days=4)
        nxt_key = nxt.strftime("%B %Y")
        if nxt_key not in data:
            data[nxt_key] = {"year": nxt.year, "month": nxt.month, "employees": [], "employee_plans": {}, "weeks": []}
            src = data[newest_key]
            for emp in src.get("employees", []):
                data[nxt_key]["employees"].append(emp)
                data[nxt_key]["employee_plans"][emp] = float(src.get("employee_plans", {}).get(emp, 0.0) or 0.0)
            for week_dates in weeks_covering_month(nxt.year, nxt.month):
                wk = {"label": f"{week_dates[0].strftime('%b %d')} - {week_dates[-1].strftime('%b %d')}", "daily_profits": {}, "total": 0.0}
                for emp in data[nxt_key]["employees"]:
                    wk["daily_profits"][emp] = {d.isoformat(): 0.0 for d in week_dates}
                data[nxt_key]["weeks"].append(wk)
            save_data(data)
            st.success(f"Created new month {nxt_key}")
            try:
                st.rerun()
            except Exception:
                pass

if selected_month not in data:
    selected_month = month_keys[0]
md = data[selected_month]

expected_weeks = weeks_covering_month(md["year"], md["month"])
if len(md.get("weeks", [])) != len(expected_weeks):
    old = md.get("weeks", [])
    new_weeks = []
    for idx, week_dates in enumerate(expected_weeks):
        label = f"{week_dates[0].strftime('%b %d')} - {week_dates[-1].strftime('%b %d')}"
        old_w = next((ow for ow in old if isinstance(ow, dict) and ow.get("label") == label), None)
        wk = {"label": label, "daily_profits": {}, "total": 0.0}
        for emp in md.get("employees", []):
            if old_w and "daily_profits" in old_w and emp in old_w["daily_profits"]:
                wk["daily_profits"][emp] = dict(old_w["daily_profits"][emp])
            else:
                wk["daily_profits"][emp] = {d.isoformat(): 0.0 for d in week_dates}
        new_weeks.append(wk)
    md["weeks"] = new_weeks
    data[selected_month] = md
    save_data(data)

# -------------------- Style --------------------
st.markdown(
    """
    <style>
    /* Правая панель */
    [data-testid="stSidebar"] {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
    }
    h1, h2, h3, h4, h5 {
        font-family: 'Arial', sans-serif;
    }
    .dataframe, table {
        font-family: 'Verdana', sans-serif;
        font-size: 14px;
        border: 1px solid #ccc;
        border-radius: 5px;
    }
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        border-radius: 5px;
    }
    .week-table th {
        background-color: #f9f9f9;
    }
    .week-table tr:nth-child(even) {
        background-color: #f2f2f2;
    }
    .week-table tr:nth-child(odd) {
        background-color: #ffffff;
    }
    </style>
    """, unsafe_allow_html=True
)

# -------------------- Right fixed panel --------------------
_, right_col = st.columns([3, 1])
with right_col:
    st.markdown("### 👥 Employee Panel")
    # Add / Remove employee (only visible to admin)
    with st.form("add_remove_employee_form", clear_on_submit=False):
        new_emp = st.text_input("New employee name")
        add_sub = st.form_submit_button("➕ Add employee")
        remove_select = st.selectbox("Remove employee", options=["(select)"] + md.get("employees", []))
        remove_sub = st.form_submit_button("🗑 Remove selected")
        # admin check
        if add_sub and new_emp and new_emp.strip() == "admin123":  # <-- простая проверка, поменяй пароль
            add_employee_to_month_and_future(data, selected_month, new_emp.strip())
            st.success(f"Added employee '{new_emp.strip()}' to month {selected_month} and future months.")
            try: st.rerun()
            except: pass
        if remove_sub and remove_select != "(select)" and new_emp.strip() == "admin123":
            remove_employee_from_month_and_future(data, selected_month, remove_select)
            st.success(f"Removed employee '{remove_select}' from {selected_month} and future months.")
            try: st.rerun()
            except: pass

    # Plan editable by all
    rows = []
    for emp in md.get("employees", []):
        cur = sum(sum(float(v or 0.0) for v in wk.get("daily_profits", {}).get(emp, {}).values()) for wk in md.get("weeks", []))
        plan_val = md.get("employee_plans", {}).get(emp, 0.0)
        rows.append({"Employee": emp, "Plan": float(plan_val), "Current": float(cur)})
    if rows:
        df_emps = pd.DataFrame(rows).set_index("Employee")
        edited = st.data_editor(df_emps[["Plan"]], key=f"emp_plans_editor_{selected_month}", use_container_width=False, num_rows="fixed")
        for emp_name in edited.index:
            try: md.setdefault("employee_plans", {})[emp_name] = float(edited.loc[emp_name, "Plan"])
            except: md.setdefault("employee_plans", {})[emp_name] = 0.0
        # show Current totals
        st.markdown("**Current totals**")
        st.table(df_emps[["Current"]])
    else:
        st.info("No employees for this month. Add one above.")

    # Month totals
    total_planned = sum(float(x or 0.0) for x in md.get("employee_plans", {}).values())
    total_current = sum(sum(float(v or 0.0) for v in wk.get("daily_profits", {}).get(emp, {}).values())
                        for wk in md.get("weeks", []) for emp in md.get("employees", []))
    st.markdown("---")
    st.metric("🎯 Month Plan Total", f"${total_planned:,.2f}")
    st.metric("💰 Month Current Total", f"${total_current:,.2f}")

    # Clear all data button
    if st.button("🧹 Clear all data"):
        if os.path.exists(DATA_FILE):
            os.remove(DATA_FILE)
            st.success("All data cleared! Reload the app to start fresh.")

data[selected_month] = md
save_data(data)

st.markdown("---")
st.header(f"📅 {selected_month}")

# -------------------- Main area: weeks horizontal --------------------
weeks = weeks_covering_month(md["year"], md["month"])
for wi, week_dates in enumerate(weeks, start=1):
    week_in_month = [d for d in week_dates if d.month == md["month"]]
    if not week_in_month: continue
    week_label = f"Week {wi}: {week_in_month[0].strftime('%b %d')} - {week_in_month[-1].strftime('%b %d')}"
    st.subheader(week_label)

    col_labels = [d.strftime("%a %b %d").replace(" 0", " ") for d in week_in_month]
    if len(md["weeks"]) < wi: md["weeks"].append({"label": week_label, "daily_profits": {}, "total": 0.0})
    wk_obj = md["weeks"][wi-1]; wk_obj.setdefault("daily_profits", {})
    for emp in md.get("employees", []):
        wk_obj["daily_profits"].setdefault(emp, {})
        for d in week_in_month:
            wk_obj["daily_profits"][emp].setdefault(d.isoformat(), 0.0)

    rows = []
    for emp in md.get("employees", []):
        row = {"Employee": emp}
        for d in week_in_month:
            iso = d.isoformat()
            val = float(wk_obj["daily_profits"].get(emp, {}).get(iso, 0.0) or 0.0)
            lab = d.strftime("%a %b %d").replace(" 0", " ")
            row[lab] = val
        rows.append(row)
    if not rows: continue

    df_week = pd.DataFrame(rows).set_index("Employee")
    editor_key = f"week_editor_{selected_month}_{wi}"
    edited = st.data_editor(df_week, key=editor_key, use_container_width=False, num_rows="fixed")

    for emp_name in edited.index:
        for idx, d in enumerate(week_in_month):
            col_label = edited.columns[idx]
            try: new_val = float(edited.loc[emp_name, col_label])
            except: new_val = 0.0
            md["weeks"][wi-1]["daily_profits"].setdefault(emp_name, {})[d.isoformat()] = new_val

    data[selected_month] = md
    save_data(data)

data[selected_month] = md
save_data(data)
