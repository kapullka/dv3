# app.py — Streamlit dashboard: employee management + weekly profits with styling
import streamlit as st
import pandas as pd
import calendar
from datetime import date, datetime, timedelta
import json
import os
from typing import Dict, Any, List, Tuple

APP_TITLE = "🚚 SunTrans Profit"
DATA_FILE = "dispatch_data.json"
ADMIN_PASSWORD = "1234"  # Поставь свой пароль

st.set_page_config(page_title=APP_TITLE, layout="wide")
st.markdown(
    """
    <style>
    .stApp { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .employee-panel { background-color: #f5f5f5; padding: 10px; border-radius: 8px; }
    .week-table th { text-align: center; }
    </style>
    """,
    unsafe_allow_html=True
)

st.title(APP_TITLE)

# -------------------- Utilities --------------------
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

# -------------------- Load / Save --------------------
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
        y, m = parse_month_key(key)
        md.setdefault("year", y)
        md.setdefault("month", m)
        md.setdefault("employees", [])
        if "employee_plans" not in md:
            md["employee_plans"] = {e: 0 for e in md.get("employees", [])}
        # weeks rebuild
        expected = weeks_covering_month(md["year"], md["month"])
        old_weeks = md.get("weeks", [])
        new_weeks = []
        for week_dates in expected:
            start, end = week_dates[0], week_dates[-1]
            label = f"{start.strftime('%b %d')} - {end.strftime('%b %d')}"
            old_week = next((ow for ow in old_weeks if ow.get("label") == label), None)
            wk_obj = {"label": label, "daily_profits": {}, "total": 0}
            for emp in md.get("employees", []):
                wk_obj["daily_profits"].setdefault(emp, {})
                for d in week_dates:
                    iso = d.isoformat()
                    val = 0
                    if old_week and emp in old_week.get("daily_profits", {}):
                        val = int(old_week["daily_profits"][emp].get(iso, 0) or 0)
                    wk_obj["daily_profits"][emp][iso] = val
            new_weeks.append(wk_obj)
        md["weeks"] = new_weeks
        for emp in md["employees"]:
            md["employee_plans"].setdefault(emp, 0)
        data[key] = md

    if not data:
        t = date.today()
        key = t.strftime("%B %Y")
        data[key] = {"year": t.year, "month": t.month, "employees": [], "employee_plans": {}, "weeks": []}
        for week_dates in weeks_covering_month(t.year, t.month):
            label = f"{week_dates[0].strftime('%b %d')} - {week_dates[-1].strftime('%b %d')}"
            data[key]["weeks"].append({"label": label, "daily_profits": {}, "total": 0})
    return data

def save_data(data: Dict[str, Any]):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# -------------------- Employee ops --------------------
def add_employee_to_month_and_future(data: Dict[str, Any], month_key: str, name: str):
    sy, sm = parse_month_key(month_key)
    for k, md in data.items():
        y, m = md.get("year", sy), md.get("month", sm)
        if (y, m) >= (sy, sm):
            if name not in md["employees"]:
                md["employees"].append(name)
                md.setdefault("employee_plans", {})[name] = 0
                expected_weeks = weeks_covering_month(md["year"], md["month"])
                for idx, wk in enumerate(md.get("weeks", [])):
                    week_dates = expected_weeks[idx]
                    wk.setdefault("daily_profits", {})
                    wk["daily_profits"].setdefault(name, {})
                    for d in week_dates:
                        iso = d.isoformat()
                        wk["daily_profits"][name].setdefault(iso, 0)
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

# ---------- UI: Month + Password ----------
col_left, col_right = st.columns([3,1])
with col_left:
    selected_month = st.selectbox("Select month", month_keys, index=0)
with col_right:
    password = st.text_input("Admin password", type="password")
    add_new_enabled = password == ADMIN_PASSWORD
    if add_new_enabled and st.button("➕ Add New Month"):
        newest_key = max(month_keys, key=lambda k: month_sort_key(k, data))
        ny, nm = parse_month_key(newest_key)
        nxt = date(ny, nm, 28) + timedelta(days=4)
        nxt_key = nxt.strftime("%B %Y")
        if nxt_key not in data:
            src = data[newest_key]
            data[nxt_key] = {"year": nxt.year, "month": nxt.month, "employees": list(src["employees"]), 
                             "employee_plans": dict(src["employee_plans"]), "weeks": []}
            for week_dates in weeks_covering_month(nxt.year, nxt.month):
                wk = {"label": f"{week_dates[0].strftime('%b %d')} - {week_dates[-1].strftime('%b %d')}", "daily_profits": {}, "total": 0}
                for emp in data[nxt_key]["employees"]:
                    wk["daily_profits"][emp] = {d.isoformat(): 0 for d in week_dates}
                data[nxt_key]["weeks"].append(wk)
            save_data(data)
            st.success(f"Created new month {nxt_key}")
            st.experimental_rerun()

md = data[selected_month]

# -------------------- Layout: Weeks + Employee Panel --------------------
col_weeks, col_panel = st.columns([3,1])
with col_panel:
    st.markdown("### 👥 Employee Panel")
    # Add/Remove
    with st.form("emp_form"):
        new_emp = st.text_input("New employee name")
        add_sub = st.form_submit_button("➕ Add employee")
        remove_select = st.selectbox("Remove employee", ["(select)"] + md.get("employees", []))
        remove_sub = st.form_submit_button("🗑 Remove selected")
        if add_sub and new_emp.strip() and password == ADMIN_PASSWORD:
            add_employee_to_month_and_future(data, selected_month, new_emp.strip())
            st.success(f"Added {new_emp.strip()}")
            st.experimental_rerun()
        if remove_sub and remove_select != "(select)" and password == ADMIN_PASSWORD:
            remove_employee_from_month_and_future(data, selected_month, remove_select)
            st.success(f"Removed {remove_select}")
            st.experimental_rerun()

    # Employee Plans editable
    rows = []
    for emp in md.get("employees", []):
        cur = sum(sum(int(v) for v in wk.get("daily_profits", {}).get(emp, {}).values()) for wk in md["weeks"])
        plan_val = md.get("employee_plans", {}).get(emp, 0)
        rows.append({"Employee": emp, "Plan": plan_val, "Current": cur})
    if rows:
        df_emps = pd.DataFrame(rows).set_index("Employee")
        edited = st.data_editor(df_emps[["Plan"]], key=f"emp_plans_editor_{selected_month}", use_container_width=True, num_rows="fixed")
        for emp_name in edited.index:
            md.setdefault("employee_plans", {})[emp_name] = int(edited.loc[emp_name, "Plan"])
        st.markdown("**Current totals**")
        st.table(df_emps[["Current"]])
    else:
        st.info("No employees for this month.")

# -------------------- Weeks Tables --------------------
with col_weeks:
    for wi, week_dates in enumerate(weeks_covering_month(md["year"], md["month"]), start=1):
        week_in_month = [d for d in week_dates if d.month == md["month"]]
        if not week_in_month:
            continue
        week_label = f"Week {wi}: {week_in_month[0].strftime('%b %d')} - {week_in_month[-1].strftime('%b %d')}"
        st.subheader(week_label)

        # Build week DataFrame
        rows = []
        for emp in md.get("employees", []):
            row = {}
            total_week = sum(md["weeks"][wi-1]["daily_profits"].get(emp, {}).get(d.isoformat(),0) for d in week_in_month)
            row["Weekly Total"] = total_week
            for d in week_in_month:
                row[d.strftime("%a %d")] = int(md["weeks"][wi-1]["daily_profits"][emp][d.isoformat()])
            rows.append(row)

        if not rows:
            st.info("No employees configured.")
            continue

        df_week = pd.DataFrame(rows, index=md.get("employees"))

        # Editable table excluding Weekly Total
        editable_cols = [c for c in df_week.columns if c != "Weekly Total"]
        edited_week = st.data_editor(
            df_week[editable_cols],
            key=f"week_editor_{selected_month}_{wi}",
            use_container_width=True,
            num_rows="fixed"
        )

        # Save edited values back to md["weeks"]
        for emp_name in edited_week.index:
            for d in week_in_month:
                col_str = d.strftime("%a %d")
                if col_str in edited_week.columns:
                    md["weeks"][wi-1]["daily_profits"][emp_name][d.isoformat()] = int(edited_week.loc[emp_name, col_str])

# -------------------- Save Data --------------------
save_data(data)
