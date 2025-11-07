# app.py — Employee management with admin controls, fixed panel, rounded totals

import streamlit as st
import pandas as pd
import calendar
from datetime import date, datetime, timedelta
import json
import os
from typing import Dict, Any, List, Tuple

APP_TITLE = "🚚 SunTrans Profit"
DATA_FILE = "dispatch_data.json"
ADMIN_PASSWORD = "admin123"  # change to your secure password

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
            label = f"{week_dates[0].strftime('%b %d')} - {week_dates[-1].strftime('%b %d')}"
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
                for idx, wk in enumerate(md.get("weeks", [])):
                    week_dates = expected_weeks[idx]
                    wk.setdefault("daily_profits", {})
                    wk["daily_profits"].setdefault(name, {})
                    for d in week_dates:
                        wk["daily_profits"][name].setdefault(d.isoformat(), 0.0)
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

month_keys = sorted(list(data.keys()), key=lambda k: month_sort_key(k, data), reverse=True)
if not month_keys:
    t = date.today()
    key = t.strftime("%B %Y")
    data[key] = {"year": t.year, "month": t.month, "employees": [], "employee_plans": {}, "weeks": []}
    month_keys = [key]
    save_data(data)

# ---------- Layout: Month select + weeks & Employee Panel ----------
col_main, col_panel = st.columns([3, 1])
with col_main:
    selected_month = st.selectbox("Select month", month_keys, index=0)

md = data[selected_month]
expected_weeks = weeks_covering_month(md["year"], md["month"])

# -------------------- Employee Panel --------------------
with col_panel:
    st.markdown("### 👥 Employee Panel")
    # Admin password for employee changes
    password_emp = st.text_input("Admin password", type="password", key="pw_emp_panel")
    with st.form("add_remove_employee_form", clear_on_submit=False):
        new_emp = st.text_input("New employee name")
        add_sub = st.form_submit_button("➕ Add employee")
        remove_select = st.selectbox("Remove employee", options=["(select)"] + md.get("employees", []))
        remove_sub = st.form_submit_button("🗑 Remove selected")
        if add_sub and new_emp:
            if password_emp == ADMIN_PASSWORD:
                add_employee_to_month_and_future(data, selected_month, new_emp.strip())
                st.success(f"Added '{new_emp.strip()}' to {selected_month} and future months.")
                st.experimental_rerun()
            else:
                st.error("Invalid admin password!")
        if remove_sub and remove_select != "(select)":
            if password_emp == ADMIN_PASSWORD:
                remove_employee_from_month_and_future(data, selected_month, remove_select)
                st.success(f"Removed '{remove_select}' from {selected_month} and future months.")
                st.experimental_rerun()
            else:
                st.error("Invalid admin password!")

    # Editable Plans for all
    rows = []
    for emp in md.get("employees", []):
        cur = sum(sum(float(v or 0.0) for v in wk.get("daily_profits", {}).get(emp, {}).values()) for wk in md.get("weeks", []))
        plan_val = md.get("employee_plans", {}).get(emp, 0.0)
        rows.append({"Employee": emp, "Plan": float(plan_val), "Current": int(cur)})
    if rows:
        df_emps = pd.DataFrame(rows).set_index("Employee")
        edited = st.data_editor(df_emps[["Plan"]], key=f"emp_plans_editor_{selected_month}", use_container_width=True, num_rows="fixed")
        for emp_name in edited.index:
            md.setdefault("employee_plans", {})[emp_name] = float(edited.loc[emp_name, "Plan"])
        st.markdown("**Current totals**")
        st.table(df_emps[["Current"]])
    else:
        st.info("No employees for this month.")

    total_planned = sum(float(x or 0.0) for x in md.get("employee_plans", {}).values())
    total_current = sum(sum(float(v or 0.0) for v in wk.get("daily_profits", {}).get(emp, {}).values()) for wk in md.get("weeks", []) for emp in md.get("employees", []))
    st.markdown("---")
    st.metric("🎯 Month Plan Total", f"${int(total_planned):,}")
    st.metric("💰 Month Current Total", f"${int(total_current):,}")

data[selected_month] = md
save_data(data)

# -------------------- Main area: Weeks --------------------
for wi, week_dates in enumerate(expected_weeks, start=1):
    week_in_month = [d for d in week_dates if d.month == md["month"]]
    if not week_in_month:
        continue
    week_label = f"Week {wi}: {week_in_month[0].strftime('%b %d')} - {week_in_month[-1].strftime('%b %d')}"
    st.subheader(week_label)

    col_labels = [d.strftime("%a %b %d").replace(" 0", " ") for d in week_in_month]

    if len(md["weeks"]) < wi:
        md["weeks"].append({"label": week_label, "daily_profits": {}, "total": 0.0})
    wk_obj = md["weeks"][wi - 1]
    wk_obj.setdefault("daily_profits", {})
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
    if not rows:
        st.info("No employees configured.")
        continue

    df_week = pd.DataFrame(rows).set_index("Employee")
    edited = st.data_editor(df_week, key=f"week_editor_{selected_month}_{wi}", use_container_width=False, num_rows="fixed")

    for emp_name in edited.index:
        for idx, d in enumerate(week_in_month):
            col_label = edited.columns[idx]
            try:
                new_val = float(edited.loc[emp_name, col_label])
            except Exception:
                new_val = 0.0
            md["weeks"][wi - 1]["daily_profits"].setdefault(emp_name, {})[d.isoformat()] = new_val

data[selected_month] = md
save_data(data)
