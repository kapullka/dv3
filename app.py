# app.py (fixed)
import streamlit as st
import pandas as pd
import calendar
from datetime import date, datetime, timedelta
import json
import os
from typing import Dict, Any, List

# ---------- CONFIG ----------
APP_TITLE = "🚚 Dispatch Tracker (fixed)"
DATA_FILE = "dispatch_data.json"

st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)

# ---------- HELPERS: calendar/weeks ----------
def weeks_covering_month(year: int, month: int) -> List[List[date]]:
    """Return list of weeks (each is list of 7 date objects Mon..Sun) covering the month.
       Weeks may include days outside the month; caller can filter by d.month==month if needed."""
    first = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    last = date(year, month, last_day)
    # monday on or before first
    start_monday = first - timedelta(days=first.weekday())
    weeks = []
    cur = start_monday
    while cur <= last:
        week = [cur + timedelta(days=i) for i in range(7)]
        weeks.append(week)
        cur += timedelta(days=7)
    return weeks

def parse_month_key(key: str) -> (int, int):
    """Parse "MonthName YYYY" to (year, month). If fails, return today."""
    try:
        dt = datetime.strptime(key, "%B %Y")
        return dt.year, dt.month
    except Exception:
        t = date.today()
        return t.year, t.month

# ---------- LOAD / NORMALIZE DATA ----------
def load_data() -> Dict[str, Any]:
    """Load JSON and normalize older structures to have year, month, employee_plans, weeks, daily_profits."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            # backup corrupted file
            os.rename(DATA_FILE, DATA_FILE + ".bak")
            raw = {}
    else:
        raw = {}

    data: Dict[str, Any] = {}

    for key, val in raw.items():
        # start from existing object or empty
        md = dict(val) if isinstance(val, dict) else {}
        # ensure year/month
        if "year" not in md or "month" not in md:
            y, m = parse_month_key(key)
            md.setdefault("year", y)
            md.setdefault("month", m)
        # ensure employees list
        md.setdefault("employees", [])
        # ensure employee_plans dict
        if "employee_plans" not in md:
            # try older 'plan' key
            if "plan" in md and isinstance(md["plan"], dict):
                # if plan had "Monthly Target", we ignore; create per-employee plans 0
                md["employee_plans"] = {e: 0.0 for e in md.get("employees", [])}
            else:
                md["employee_plans"] = {e: 0.0 for e in md.get("employees", [])}
        # ensure weeks array
        # we'll rebuild weeks based on year/month but try to copy any existing profits/daily_profits if possible
        expected_weeks = weeks_covering_month(md["year"], md["month"])
        old_weeks = md.get("weeks", [])
        new_weeks = []
        for idx, week_dates in enumerate(expected_weeks):
            start = week_dates[0]
            end = week_dates[-1]
            label = f"{start.strftime('%b %d')} - {end.strftime('%b %d')}"
            # try to find matching old week by label
            old_week = None
            for ow in old_weeks:
                if isinstance(ow, dict) and ow.get("label") == label:
                    old_week = ow
                    break
            week_obj = {"label": label, "profits": {}, "daily_profits": {}, "total": 0.0}
            # populate per-employee daily_profits (preserve old daily if present)
            for emp in md["employees"]:
                # init daily dict for this week for this employee
                week_obj["daily_profits"].setdefault(emp, {})
                for d in week_dates:
                    iso = d.isoformat()
                    # try to preserve from old_week.daily_profits if present
                    if old_week and isinstance(old_week.get("daily_profits"), dict):
                        old_emp_daily = old_week["daily_profits"].get(emp, {})
                        if iso in old_emp_daily:
                            week_obj["daily_profits"][emp][iso] = float(old_emp_daily.get(iso, 0.0) or 0.0)
                            continue
                    # else maybe old_week had single weekly profits stored in 'profits' key
                    if old_week and isinstance(old_week.get("profits"), dict) and emp in old_week.get("profits", {}):
                        # Distribute weekly single value into daily zeros (we cannot reconstruct), keep 0
                        week_obj["daily_profits"][emp][iso] = 0.0
                    else:
                        week_obj["daily_profits"][emp][iso] = 0.0
                # also keep old_week.profits[emp] if exists (compat), but we won't use it for daily editing
                if old_week and isinstance(old_week.get("profits"), dict):
                    week_obj["profits"][emp] = float(old_week["profits"].get(emp, 0.0) or 0.0)
                else:
                    week_obj["profits"][emp] = 0.0
            new_weeks.append(week_obj)
        md["weeks"] = new_weeks
        # ensure employee_plans contains all employees
        for emp in md["employees"]:
            md["employee_plans"].setdefault(emp, 0.0)
        data[key] = md

    # if there were no months, create current month skeleton
    if not data:
        today = date.today()
        key = today.strftime("%B %Y")
        data[key] = {"year": today.year, "month": today.month, "employees": [], "employee_plans": {}, "weeks": []}
        # initialize weeks
        expected_weeks = weeks_covering_month(today.year, today.month)
        for week_dates in expected_weeks:
            start = week_dates[0]; end = week_dates[-1]
            label = f"{start.strftime('%b %d')} - {end.strftime('%b %d')}"
            data[key]["weeks"].append({"label": label, "profits": {}, "daily_profits": {}, "total": 0.0})
    return data

def save_data(data: Dict[str, Any]):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------- Load and normalize ----------
data = load_data()
save_data(data)  # persist normalization

# ---------- UI: top controls ----------
# produce sorted month keys robustly (fallback to parse if keys lack year/month)
def month_sort_key(k):
    md = data.get(k, {})
    y = md.get("year")
    m = md.get("month")
    if isinstance(y, int) and isinstance(m, int):
        return (y, m)
    # fallback: try parsing from key
    py, pm = parse_month_key(k)
    return (py, pm)

month_keys = sorted(list(data.keys()), key=month_sort_key, reverse=True)

col_top_left, col_top_right = st.columns([3, 1])
with col_top_left:
    selected_month = st.selectbox("Select month", month_keys, index=0)
with col_top_right:
    if st.button("➕ Add New Month"):
        # create next month based on latest available
        newest_key = sorted(month_keys, key=month_sort_key)[0] if month_keys else date.today().strftime("%B %Y")
        ny, nm = parse_month_key(newest_key)
        newest_dt = date(ny, nm, 1)
        nxt = newest_dt.replace(day=28) + timedelta(days=4)
        nxt_key = nxt.strftime("%B %Y")
        # ensure and re-save
        data = ensure_month_and_normalize(data := data, month_key=nxt_key) if False else data  # placeholder; we'll call ensure_month below
        # direct ensure: (we'll call function below)
        # create normalized month entry
        data.setdefault(nxt_key, {})
        data = load_data() if False else data  # noop to satisfy linter
        # simpler approach: call ensure_month creation by using our ensure_month helper we'll define below
        # We'll just create skeleton here:
        if nxt_key not in data:
            y, m = parse_month_key(nxt_key)
            data[nxt_key] = {"year": y, "month": m, "employees": [], "employee_plans": {}, "weeks": []}
            # build weeks
            for week_dates in weeks_covering_month(y, m):
                start = week_dates[0]; end = week_dates[-1]
                label = f"{start.strftime('%b %d')} - {end.strftime('%b %d')}"
                data[nxt_key]["weeks"].append({"label": label, "profits": {}, "daily_profits": {}, "total": 0.0})
            # ensure plans
            data[nxt_key]["employee_plans"] = {}
            save_data(data)
            st.success(f"Added month {nxt_key}")
            st.experimental_rerun()

# re-normalize selected month to be safe
if selected_month not in data:
    selected_month = month_keys[0] if month_keys else date.today().strftime("%B %Y")
md = data[selected_month]

# ---------- RIGHT TOP: Employee list & month totals ----------
right_col = st.columns([3,1])[1]  # pick right column
with right_col:
    st.markdown("### 👥 Employee list")
    # build rows: Employee | Plan | Current
    rows = []
    for emp in md.get("employees", []):
        # current sum across all weeks daily_profits
        total_emp = 0.0
        for wk in md.get("weeks", []):
            daily = wk.get("daily_profits", {}).get(emp, {})
            # daily is dict iso->value
            for v in daily.values():
                try:
                    total_emp += float(v or 0.0)
                except Exception:
                    total_emp += 0.0
        plan = md.get("employee_plans", {}).get(emp, 0.0)
        rows.append({"Employee": emp, "Plan": float(plan), "Current": float(total_emp)})
    if rows:
        df_emps = pd.DataFrame(rows).set_index("Employee")
        # allow editing plan column
        edited = st.data_editor(df_emps[["Plan"]], key=f"emp_plans_{selected_month}", use_container_width=True, num_rows="fixed")
        # write back
        for emp_name in edited.index:
            try:
                md.setdefault("employee_plans", {})[emp_name] = float(edited.loc[emp_name, "Plan"])
            except Exception:
                md.setdefault("employee_plans", {})[emp_name] = 0.0
        # show current
        st.markdown("**Current totals**")
        st.table(df_emps[["Current"]])
    else:
        st.info("No employees yet for this month.")

    total_planned = sum(float(x or 0.0) for x in md.get("employee_plans", {}).values())
    total_current = 0.0
    # compute total_current as sum of all daily_profits across all weeks
    for wk in md.get("weeks", []):
        for emp in md.get("employees", []):
            daily = wk.get("daily_profits", {}).get(emp, {})
            for v in daily.values():
                try:
                    total_current += float(v or 0.0)
                except Exception:
                    total_current += 0.0
    st.markdown("---")
    st.metric("🎯 Month Plan Total", f"${total_planned:,.2f}")
    st.metric("💰 Month Current Total", f"${total_current:,.2f}")

# ---------- MAIN: Weeks listing (left/middle area) ----------
st.markdown("---")
st.header(f"📅 {selected_month} — Weeks (rows = employees, columns = days Mon..Sun)")

# left/middle bigger area
left_col, mid_col = st.columns([1, 3])

# ensure the md structure contains weeks with daily_profits for each employee
# rebuild weeks list if lengths mismatch with calendar (keeps existing daily_profits where labels match)
year = md.get("year", date.today().year)
month_num = md.get("month", date.today().month)
expected_weeks = weeks_covering_month(year, month_num)
# if mismatch, rebuild with attempt to preserve data by label
if len(md.get("weeks", [])) != len(expected_weeks):
    old = md.get("weeks", [])
    new_weeks = []
    for week_dates in expected_weeks:
        start = week_dates[0]; end = week_dates[-1]
        label = f"{start.strftime('%b %d')} - {end.strftime('%b %d')}"
        # find old by label
        old_week = next((ow for ow in old if isinstance(ow, dict) and ow.get("label")==label), None)
        wk = {"label": label, "profits": {}, "daily_profits": {}, "total": 0.0}
        for emp in md.get("employees", []):
            # try to preserve old daily
            if old_week and "daily_profits" in old_week and emp in old_week["daily_profits"]:
                wk["daily_profits"][emp] = dict(old_week["daily_profits"][emp])
            else:
                wk["daily_profits"][emp] = {d.isoformat(): 0.0 for d in week_dates if d.month == month_num}
        new_weeks.append(wk)
    md["weeks"] = new_weeks
    save_data(data)

# Render weeks
for wi, week_dates in enumerate(expected_weeks, start=1):
    # restrict to days inside month
    week_in_month = [d for d in week_dates if d.month == month_num]
    if not week_in_month:
        continue
    week_label = f"Week {wi}: {week_in_month[0].strftime('%b %d')} - {week_in_month[-1].strftime('%b %d')}"
    st.subheader(week_label)

    # prepare DataFrame: index Employee, columns = day labels
    col_labels = []
    for d in week_in_month:
        # platform-safe day formatting (no %-d on Windows)
        try:
            day_label = d.strftime("%a %b %-d")
        except Exception:
            day_label = d.strftime("%a %b %d").replace(" 0", " ")
        col_labels.append(day_label)

    rows = []
    for emp in md.get("employees", []):
        row = {}
        for d in week_in_month:
            iso = d.isoformat()
            row_label = d.strftime("%a %b %d").replace(" 0", " ")
            # ensure daily_profits exists
            if "daily_profits" not in md["weeks"][wi-1]:
                md["weeks"][wi-1]["daily_profits"] = {}
            if emp not in md["weeks"][wi-1]["daily_profits"]:
                # initialize for this emp/week
                md["weeks"][wi-1]["daily_profits"][emp] = {dd.isoformat(): 0.0 for dd in week_in_month}
            # get value (if missing, default 0)
            val = md["weeks"][wi-1]["daily_profits"][emp].get(iso, 0.0)
            row[row_label] = float(val or 0.0)
        rows.append({"Employee": emp, **row})
    if not rows:
        st.info("No employees configured for this month.")
        continue

    df_week = pd.DataFrame(rows).set_index("Employee")
    editor_key = f"week_editor_{selected_month}_{wi}"
    edited = st.data_editor(df_week, key=editor_key, use_container_width=True, num_rows="fixed")

    # write back daily values immediately
    for emp_name in edited.index:
        for j, d in enumerate(week_in_month):
            label = edited.columns[j]  # column ordering matches week_in_month
            try:
                new_val = float(edited.loc[emp_name, label])
            except Exception:
                new_val = 0.0
            iso = d.isoformat()
            md["weeks"][wi-1].setdefault("daily_profits", {}).setdefault(emp_name, {})[iso] = new_val

    # compute weekly totals per employee & overall
    week_totals = {}
    for emp in md.get("employees", []):
        s = 0.0
        for d in week_in_month:
            s += float(md["weeks"][wi-1]["daily_profits"].get(emp, {}).get(d.isoformat(), 0.0) or 0.0)
        week_totals[emp] = s
    md["weeks"][wi-1]["total"] = sum(week_totals.values())

    # show summary table for this week
    df_tot = pd.DataFrame([{"Employee": e, "Week Total": week_totals[e], "Plan": md.get("employee_plans", {}).get(e, 0.0)} for e in md.get("employees", [])]).set_index("Employee")
    st.table(df_tot)

# After all weeks: recompute monthly Current totals
for emp in md.get("employees", []):
    monthly_sum = 0.0
    for wk in md.get("weeks", []):
        for v in wk.get("daily_profits", {}).get(emp, {}).values():
            try:
                monthly_sum += float(v or 0.0)
            except Exception:
                monthly_sum += 0.0
    # update nothing here (we display current dynamically from sums)

# save and finish
data[selected_month] = md
save_data(data)

st.markdown("## Month summary")
tot_planned = sum(float(v or 0.0) for v in md.get("employee_plans", {}).values())
tot_current = 0.0
for wk in md.get("weeks", []):
    for emp in md.get("employees", []):
        # sum daily values
        for v in wk.get("daily_profits", {}).get(emp, {}).values():
            try:
                tot_current += float(v or 0.0)
            except Exception:
                tot_current += 0.0

col1, col2 = st.columns([2,3])
with col1:
    st.metric("🎯 Month Plan Total", f"${tot_planned:,.2f}")
    st.metric("💰 Month Current Total", f"${tot_current:,.2f}")
with col2:
    st.write("Employee plans are editable in the right panel above.")

# End of file
