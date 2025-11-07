# app.py — Employee Profit Dashboard with Admin Controls and Weekly Summaries

import streamlit as st
import pandas as pd
import calendar
from datetime import date, datetime, timedelta
import json
import os
from typing import Dict, Any, List, Tuple

APP_TITLE = "🚚 SunTrans Profit Dashboard"
DATA_FILE = "dispatch_data.json"
ADMIN_PASSWORD = "1234"

st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)

# -------------------- Utilities --------------------
def parse_month_key(key: str) -> Tuple[int, int]:
    try:
        dt = datetime.strptime(key, "%B %Y")
        return dt.year, dt.month
    except:
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

# -------------------- Load & normalize data --------------------
def load_data() -> Dict[str, Any]:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except:
            os.rename(DATA_FILE, DATA_FILE + ".bak")
            raw = {}
    else:
        raw = {}

    data: Dict[str, Any] = {}
    for key, val in raw.items():
        md = dict(val) if isinstance(val, dict) else {}
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
                        week_obj["daily_profits"][emp][iso] = int(round(old_week["daily_profits"][emp].get(iso, 0.0)))
                    else:
                        week_obj["daily_profits"][emp][iso] = 0
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

# -------------------- Core operations --------------------
def add_employee_to_month_and_future(data: Dict[str, Any], month_key: str, name: str):
    sy, sm = parse_month_key(month_key)
    for k, md in data.items():
        y, m = md.get("year", sy), md.get("month", sm)
        if (y, m) >= (sy, sm) and name not in md["employees"]:
            md["employees"].append(name)
            md.setdefault("employee_plans", {})[name] = 0.0
            for idx, week_dates in enumerate(weeks_covering_month(md["year"], md["month"])):
                if len(md["weeks"]) <= idx:
                    md["weeks"].append({"label": "", "daily_profits": {}, "total": 0.0})
                wk = md["weeks"][idx]
                wk.setdefault("daily_profits", {})[name] = {d.isoformat():0 for d in week_dates}
    save_data(data)

def remove_employee_from_month_and_future(data: Dict[str, Any], month_key: str, name: str):
    sy, sm = parse_month_key(month_key)
    for k, md in data.items():
        y, m = md.get("year", sy), md.get("month", sm)
        if (y, m) >= (sy, sm):
            if name in md.get("employees", []):
                md["employees"].remove(name)
            md.get("employee_plans", {}).pop(name, None)
            for wk in md.get("weeks", []):
                wk.get("daily_profits", {}).pop(name, None)
    save_data(data)

# -------------------- Initialize --------------------
data = load_data()
save_data(data)
month_keys = sorted(list(data.keys()), key=lambda k: month_sort_key(k, data), reverse=True)
if not month_keys:
    t = date.today()
    key = t.strftime("%B %Y")
    data[key] = {"year": t.year, "month": t.month, "employees": [], "employee_plans": {}, "weeks": []}
    month_keys = [key]
    save_data(data)

# -------------------- Admin check --------------------
is_admin = st.sidebar.text_input("Admin Password", type="password") == ADMIN_PASSWORD

# -------------------- Layout: Month select + Employee Panel --------------------
col_main, col_right = st.columns([3, 1])

with col_main:
    selected_month = st.selectbox("Select month", month_keys, index=0)
    md = data[selected_month]

with col_right:
    st.markdown("### 👥 Employee Panel")
    # Add / Remove employee - only admin
    if is_admin:
        with st.form("emp_form"):
            new_emp = st.text_input("New employee name")
            add_btn = st.form_submit_button("➕ Add")
            remove_sel = st.selectbox("Remove employee", ["(select)"] + md.get("employees", []))
            remove_btn = st.form_submit_button("🗑 Remove")
            if add_btn and new_emp.strip():
                add_employee_to_month_and_future(data, selected_month, new_emp.strip())
                st.experimental_rerun()
            if remove_btn and remove_sel != "(select)":
                remove_employee_from_month_and_future(data, selected_month, remove_sel)
                st.experimental_rerun()
    # Plan editable by all
    rows = []
    for emp in md.get("employees", []):
        cur = sum(sum(v for v in wk.get("daily_profits", {}).get(emp, {}).values()) for wk in md.get("weeks", []))
        plan_val = md.get("employee_plans", {}).get(emp, 0.0)
        rows.append({"Employee": emp, "Plan": int(plan_val), "Current": int(cur)})
    if rows:
        df_emp = pd.DataFrame(rows).set_index("Employee")
        edited = st.data_editor(df_emp[["Plan"]], use_container_width=True, num_rows="fixed")
        for emp_name in edited.index:
            md.setdefault("employee_plans", {})[emp_name] = int(edited.loc[emp_name, "Plan"])
        # Current totals under Plan
        st.markdown("**Current totals**")
        st.table(df_emp[["Current"]])
    else:
        st.info("No employees for this month.")

# Persist any changes
data[selected_month] = md
save_data(data)

# -------------------- Weeks Table --------------------
col_main, col_right = st.columns([3, 1])

with col_main:
    for wi, week_dates in enumerate(weeks_covering_month(md["year"], md["month"]), start=1):
        week_in_month = [d for d in week_dates if d.month == md["month"]]
        if not week_in_month:
            continue
        week_label = f"Week {wi}: {week_in_month[0].strftime('%b %d')} - {week_in_month[-1].strftime('%b %d')}"
        st.subheader(week_label)

        rows = []
        for emp in md.get("employees", []):
            row = {}
            # Days
            for d in week_in_month:
                val = md["weeks"][wi-1]["daily_profits"].get(emp, {}).get(d.isoformat(), 0)
                row[d.strftime("%a %d")] = int(val)
            # Weekly plan & total
            weekly_total = sum(md["weeks"][wi-1]["daily_profits"].get(emp, {}).get(d.isoformat(), 0) for d in week_in_month)
            weekly_plan = md["employee_plans"].get(emp, 0.0) / len(week_dates) * len(week_in_month)
            row["Weekly Plan"] = int(round(weekly_plan))
            row["Weekly Total"] = int(round(weekly_total))
            rows.append(row)

        df_week = pd.DataFrame(rows, index=md.get("employees"))

        # Style
        def color_week(val, col):
            if col in ["Weekly Plan", "Weekly Total"]:
                return 'background-color:white;color:black;font-weight:bold;border:1px solid black;'
            else:
                return 'background-color:#ffe5b4;color:black;border:1px solid black;'

        styled = df_week.style.applymap(lambda v: 'background-color:#ffe5b4;color:black;border:1px solid black;', subset=df_week.columns[:-2]) \
                              .applymap(lambda v: 'background-color:white;color:black;font-weight:bold;border:1px solid black;', subset=["Weekly Plan","Weekly Total"]) \
                              .set_properties(**{'text-align':'center','border':'1px solid black','font-family':'Arial','font-size':'14px'})
        st.dataframe(styled, use_container_width=False)
