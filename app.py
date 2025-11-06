# app.py — Final version: employee management, weeks with daily cells, right fixed employee list,
# add/remove propagate to future months, autosave, safe normalization of old data.

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
    """Return list of weeks as lists of 7 date objects Mon..Sun covering the month."""
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
            # backup corrupted file and start fresh
            os.rename(DATA_FILE, DATA_FILE + ".bak")
            raw = {}
    else:
        raw = {}

    data: Dict[str, Any] = {}

    for key, val in raw.items():
        md = dict(val) if isinstance(val, dict) else {}
        # ensure year/month
        if "year" not in md or "month" not in md:
            y, m = parse_month_key(key)
            md.setdefault("year", y)
            md.setdefault("month", m)
        # ensure employees and plans
        md.setdefault("employees", [])
        if "employee_plans" not in md:
            md["employee_plans"] = {e: 0.0 for e in md.get("employees", [])}
        # ensure weeks: we'll rebuild weeks based on year/month but try to preserve daily_profits if present
        expected = weeks_covering_month(md["year"], md["month"])
        old_weeks = md.get("weeks", [])
        new_weeks = []
        for week_dates in expected:
            start = week_dates[0]; end = week_dates[-1]
            label = f"{start.strftime('%b %d')} - {end.strftime('%b %d')}"
            # try find old week by label
            old_week = None
            for ow in old_weeks:
                if isinstance(ow, dict) and ow.get("label") == label:
                    old_week = ow
                    break
            week_obj = {"label": label, "daily_profits": {}, "total": 0.0}
            for emp in md.get("employees", []):
                week_obj["daily_profits"].setdefault(emp, {})
                for d in week_dates:
                    if d.month != md["month"]:
                        # keep keys for outside-month days too (optional) — but default 0
                        iso = d.isoformat()
                        # preserve if present in old_week.daily_profits
                        if old_week and isinstance(old_week.get("daily_profits"), dict):
                            old_emp_daily = old_week["daily_profits"].get(emp, {})
                            if iso in old_emp_daily:
                                week_obj["daily_profits"][emp][iso] = float(old_emp_daily.get(iso, 0.0) or 0.0)
                                continue
                        week_obj["daily_profits"][emp][iso] = 0.0
                    else:
                        iso = d.isoformat()
                        if old_week and isinstance(old_week.get("daily_profits"), dict):
                            old_emp_daily = old_week["daily_profits"].get(emp, {})
                            if iso in old_emp_daily:
                                week_obj["daily_profits"][emp][iso] = float(old_emp_daily.get(iso, 0.0) or 0.0)
                                continue
                        week_obj["daily_profits"][emp][iso] = 0.0
            new_weeks.append(week_obj)
        md["weeks"] = new_weeks
        # ensure employee_plans keys
        for emp in md["employees"]:
            md["employee_plans"].setdefault(emp, 0.0)
        data[key] = md

    # if no months, create current month
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
    """Add employee to selected month and to all months >= selected month (by year/month)."""
    sy, sm = parse_month_key(month_key)
    for k, md in data.items():
        y, m = md.get("year", sy), md.get("month", sm)
        # compare tuple
        if (y, m) >= (sy, sm):
            if name not in md["employees"]:
                md["employees"].append(name)
                md.setdefault("employee_plans", {})[name] = 0.0
                # ensure daily_profits keys for each week/dates
                expected_weeks = weeks_covering_month(md["year"], md["month"])
                # if weeks length mismatches, rebuild consistent weeks (but keep existing daily_profits where possible)
                if len(md.get("weeks", [])) != len(expected_weeks):
                    # simple rebuild preserving old label matches
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
                    # just add default zeros for new employee into existing weeks
                    for idx, wk in enumerate(md.get("weeks", [])):
                        week_dates = weeks_covering_month(md["year"], md["month"])[idx]
                        wk.setdefault("daily_profits", {})
                        wk["daily_profits"].setdefault(name, {})
                        for d in week_dates:
                            iso = d.isoformat()
                            wk["daily_profits"][name].setdefault(iso, 0.0)
    save_data(data)


def remove_employee_from_month_and_future(data: Dict[str, Any], month_key: str, name: str):
    """Remove employee from selected month AND all future months (>=selected), but keep in previous months."""
    sy, sm = parse_month_key(month_key)
    for k, md in data.items():
        y, m = md.get("year", sy), md.get("month", sm)
        if (y, m) >= (sy, sm):
            if name in md.get("employees", []):
                md["employees"].remove(name)
            if "employee_plans" in md and name in md["employee_plans"]:
                md["employee_plans"].pop(name, None)
            # remove daily_profits entries across weeks
            for wk in md.get("weeks", []):
                if "daily_profits" in wk and name in wk["daily_profits"]:
                    wk["daily_profits"].pop(name, None)
    save_data(data)


# -------------------- Initialize data --------------------
data = load_data()
# persist normalization
save_data(data)

# ---------- UI: Top controls (month select + add month) ----------
# robust month list sorted by year/month
month_keys = sorted(list(data.keys()), key=lambda k: month_sort_key(k, data), reverse=True)
if not month_keys:
    # ensure at least current
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
        # create next month after the newest (max by sort key)
        newest_key = max(month_keys, key=lambda k: month_sort_key(k, data))
        ny, nm = parse_month_key(newest_key)
        newest_dt = date(ny, nm, 1)
        nxt = newest_dt.replace(day=28) + timedelta(days=4)
        nxt_key = nxt.strftime("%B %Y")
        if nxt_key not in data:
            # copy employees & plans from newest_key
            data[nxt_key] = {"year": nxt.year, "month": nxt.month, "employees": [], "employee_plans": {}, "weeks": []}
            # copy employees and their plans
            src = data[newest_key]
            for emp in src.get("employees", []):
                data[nxt_key]["employees"].append(emp)
                data[nxt_key]["employee_plans"][emp] = float(src.get("employee_plans", {}).get(emp, 0.0) or 0.0)
            # build weeks and daily_profits zeros (or copy if logic desired)
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

# ensure selected_month exists and normalized
if selected_month not in data:
    selected_month = month_keys[0]
md = data[selected_month]

# ensure weeks structure length matches calendar
expected_weeks = weeks_covering_month(md["year"], md["month"])
if len(md.get("weeks", [])) != len(expected_weeks):
    # rebuild preserving matching labels where possible
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

# -------------------- Right fixed panel: Employee list & month totals --------------------
# We'll render it in a right column so visually it is fixed on the right
_, right_col = st.columns([3, 1])
with right_col:
    st.markdown("### 👥 Employee list")
    # Add / Remove employee controls
    with st.form("add_remove_employee_form", clear_on_submit=False):
        new_emp = st.text_input("New employee name")
        add_sub = st.form_submit_button("➕ Add employee")
        remove_select = st.selectbox("Remove employee", options=["(select)"] + md.get("employees", []))
        remove_sub = st.form_submit_button("🗑 Remove selected")
        if add_sub and new_emp:
            if new_emp.strip():
                add_employee_to_month_and_future(data, selected_month, new_emp.strip())
                st.success(f"Added employee '{new_emp.strip()}' to month {selected_month} and future months.")
                try:
                    st.rerun()
                except Exception:
                    pass
        if remove_sub and remove_select != "(select)":
            remove_employee_from_month_and_future(data, selected_month, remove_select)
            st.success(f"Removed employee '{remove_select}' from {selected_month} and future months.")
            try:
                st.rerun()
            except Exception:
                pass

    # Show editable table of Plans (Plan editable, Current read-only)
    rows = []
    for emp in md.get("employees", []):
        # compute current total from daily_profits
        cur = 0.0
        for wk in md.get("weeks", []):
            cur += sum(float(v or 0.0) for v in wk.get("daily_profits", {}).get(emp, {}).values())
        plan_val = md.get("employee_plans", {}).get(emp, 0.0)
        rows.append({"Employee": emp, "Plan": float(plan_val), "Current": float(cur)})
    if rows:
        df_emps = pd.DataFrame(rows).set_index("Employee")
        # editable Plan column only
        edited = st.data_editor(df_emps[["Plan"]], key=f"emp_plans_editor_{selected_month}", use_container_width=True, num_rows="fixed")
        # write back plans immediately
        for emp_name in edited.index:
            try:
                md.setdefault("employee_plans", {})[emp_name] = float(edited.loc[emp_name, "Plan"])
            except Exception:
                md.setdefault("employee_plans", {})[emp_name] = 0.0
        # show current totals beneath
        st.markdown("**Current totals**")
        st.table(df_emps[["Current"]])
    else:
        st.info("No employees for this month. Add one above.")

    # Month totals
    total_planned = sum(float(x or 0.0) for x in md.get("employee_plans", {}).values())
    total_current = 0.0
    for wk in md.get("weeks", []):
        for emp in md.get("employees", []):
            total_current += sum(float(v or 0.0) for v in wk.get("daily_profits", {}).get(emp, {}).values())
    st.markdown("---")
    st.metric("🎯 Month Plan Total", f"${total_planned:,.2f}")
    st.metric("💰 Month Current Total", f"${total_current:,.2f}")

# persist right-panel changes
data[selected_month] = md
save_data(data)

st.markdown("---")
st.header(f"📅 {selected_month}")

# -------------------- Main area: weeks vertical list --------------------
# For each week, render editable table with employees rows and day columns (only days inside month)
for wi, week_dates in enumerate(weeks_covering_month(md["year"], md["month"]), start=1):
    # restrict to dates inside month for columns
    week_in_month = [d for d in week_dates if d.month == md["month"]]
    if not week_in_month:
        continue
    week_label = f"Week {wi}: {week_in_month[0].strftime('%b %d')} - {week_in_month[-1].strftime('%b %d')}"
    st.subheader(week_label)

    # build column labels safely (Windows-safe)
    col_labels = []
    for d in week_in_month:
        try:
            lab = d.strftime("%a %b %-d")
        except Exception:
            lab = d.strftime("%a %b %d").replace(" 0", " ")
        col_labels.append(lab)

    # ensure week structure has daily_profits for each emp
    if len(md["weeks"]) < wi:
        # should not happen, but safeguard
        md["weeks"].append({"label": week_label, "daily_profits": {}, "total": 0.0})
    wk_obj = md["weeks"][wi - 1]
    wk_obj.setdefault("daily_profits", {})
    # ensure per-employee dicts exist
    for emp in md.get("employees", []):
        wk_obj["daily_profits"].setdefault(emp, {})
        for d in week_in_month:
            wk_obj["daily_profits"][emp].setdefault(d.isoformat(), 0.0)

    # build DataFrame rows
    rows = []
    for emp in md.get("employees", []):
        row = {"Employee": emp}
        for d in week_in_month:
            iso = d.isoformat()
            val = float(wk_obj["daily_profits"].get(emp, {}).get(iso, 0.0) or 0.0)
            # label for display
            lab = d.strftime("%a %b %d").replace(" 0", " ")
            row[lab] = val
        rows.append(row)
    if not rows:
        st.info("No employees configured.")
        continue

    df_week = pd.DataFrame(rows).set_index("Employee")
    editor_key = f"week_editor_{selected_month}_{wi}"
    edited = st.data_editor(df_week, key=editor_key, use_container_width=True, num_rows="fixed")

    # write back edited values into md["weeks"][wi-1]["daily_profits"]
    for emp_name in edited.index:
        for idx, d in enumerate(week_in_month):
            col_label = edited.columns[idx]
            try:
                new_val = float(edited.loc[emp_name, col_label])
            except Exception:
                new_val = 0.0
            md["weeks"][wi - 1]["daily_profits"].setdefault(emp_name, {})[d.isoformat()] = new_val

    # automatically persist after each week edit
    data[selected_month] = md
    save_data(data)

# persist final data
data[selected_month] = md
save_data(data)
