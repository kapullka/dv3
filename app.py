# app.py
import streamlit as st
import pandas as pd
import calendar
from datetime import date, datetime, timedelta
import json
import os

# ---------- CONFIG ----------
APP_TITLE = "🚚 Dispatch Tracker"
DATA_FILE = "dispatch_data.json"

st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)

# ---------- HELPERS ----------
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception:
                # Corrupted file -> backup and create fresh
                os.rename(DATA_FILE, DATA_FILE + ".bak")
                data = {}
    else:
        data = {}
    # Ensure backwards compatibility: add employee_plans where missing
    for m, md in data.items():
        if "employee_plans" not in md:
            md["employee_plans"] = {e: 0 for e in md.get("employees", [])}
        # ensure weeks exist and their profits structure
        if "weeks" not in md:
            md["weeks"] = []
    return data

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def weeks_covering_month(year:int, month:int):
    """Return list of weeks covering the month. Each week is list of datetime.date (Mon..Sun),
       but we will only use dates that belong to the month when rendering."""
    first = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    last = date(year, month, last_day)
    # find Monday on or before first
    start_monday = first - timedelta(days=first.weekday())
    weeks = []
    cur = start_monday
    while cur <= last:
        week = [cur + timedelta(days=i) for i in range(7)]
        weeks.append(week)
        cur += timedelta(days=7)
    return weeks

def ensure_month(data, month_key):
    """Ensure month structure exists and is normalized (employees list, employee_plans, weeks with profits)."""
    if month_key not in data:
        # create new month based on parsing
        try:
            dt = datetime.strptime(month_key, "%B %Y")
            year, month = dt.year, dt.month
        except Exception:
            today = date.today()
            year, month = today.year, today.month
            month_key = date(year, month, 1).strftime("%B %Y")
        data[month_key] = {
            "year": year,
            "month": month,
            "employees": [],
            "employee_plans": {},
            "weeks": []
        }
    md = data[month_key]
    # fix missing keys
    if "employees" not in md: md["employees"] = []
    if "employee_plans" not in md: md["employee_plans"] = {e: 0 for e in md["employees"]}
    if "weeks" not in md: md["weeks"] = []

    # build weeks array (one entry per calendar week)
    year = md.get("year", datetime.now().year)
    month = md.get("month", datetime.now().month)
    cal_weeks = weeks_covering_month(year, month)
    # If weeks list length does not match, rebuild weeks list keeping existing profits where possible
    if len(md["weeks"]) != len(cal_weeks):
        old_weeks = md.get("weeks", [])
        new_weeks = []
        for week_dates in cal_weeks:
            start = week_dates[0]
            end = week_dates[-1]
            label = f"{start.strftime('%b %d')} - {end.strftime('%b %d')}"
            # try to find matching old week by label to copy profits
            old_copy = None
            for ow in old_weeks:
                if ow.get("label") == label:
                    old_copy = ow
                    break
            week_obj = {"label": label, "profits": {}, "total": 0.0}
            # initialize profits for employees, prefer old_copy values
            for emp in md["employees"]:
                val = 0.0
                if old_copy and emp in old_copy.get("profits", {}):
                    val = float(old_copy["profits"].get(emp, 0.0) or 0.0)
                week_obj["profits"][emp] = val
            new_weeks.append(week_obj)
        md["weeks"] = new_weeks
    else:
        # ensure all employees exist in profits dictionaries for each week
        for wk in md["weeks"]:
            if "profits" not in wk: wk["profits"] = {}
            for emp in md["employees"]:
                if emp not in wk["profits"]:
                    wk["profits"][emp] = 0.0
    # ensure all employee_plans keys exist
    for emp in md["employees"]:
        if emp not in md["employee_plans"]:
            md["employee_plans"][emp] = 0.0

    data[month_key] = md
    return data

# ---------- Load data ----------
data = load_data()

# ensure at least current month exists
today = date.today()
current_month_key = today.strftime("%B %Y")
data = ensure_month(data, current_month_key)
save_data(data)

# ---------- UI: Top controls ----------
month_keys = sorted(list(data.keys()), key=lambda k: (data[k]["year"], data[k]["month"]), reverse=True)
if not month_keys:
    month_keys = [current_month_key]

col_top_left, col_top_right = st.columns([3,1])
with col_top_left:
    selected_month = st.selectbox("Select month", month_keys, index=0)
with col_top_right:
    if st.button("➕ Add New Month"):
        # create next month relative to the newest present month
        newest = max(data.values(), key=lambda v: (v["year"], v["month"]))
        newest_dt = date(newest["year"], newest["month"], 1)
        nxt = newest_dt.replace(day=28) + timedelta(days=4)  # trick to move to next month
        nxt_key = nxt.strftime("%B %Y")
        data = ensure_month(data, nxt_key)
        save_data(data)
        st.success(f"Added month {nxt_key}")
        st.experimental_rerun()

# normalize selected month
data = ensure_month(data, selected_month)
month = data[selected_month]

# ---------- Right top: Employee list + Month Plan Total ----------
# We'll show this in the right column above weeks. To keep it visually top-right, we'll render it first in a right column.
_, right_col = st.columns([3,1])
with right_col:
    st.markdown("### 👥 Employee list")
    # build DataFrame of employees with Plan and Current sum
    rows = []
    for emp in month["employees"]:
        # current is sum of all week profits for this month
        current = sum(float(wk["profits"].get(emp, 0.0) or 0.0) for wk in month["weeks"])
        plan = month["employee_plans"].get(emp, 0.0)
        rows.append({"Employee": emp, "Plan": float(plan), "Current": float(current)})
    if rows:
        df_emps = pd.DataFrame(rows).set_index("Employee")
        # Allow editing the Plan column inline
        edited_emps = st.data_editor(df_emps[["Plan"]], num_rows="fixed", key=f"emp_plans_{selected_month}", use_container_width=True)
        # write back plans immediately
        for emp_name in edited_emps.index:
            try:
                month["employee_plans"][emp_name] = float(edited_emps.loc[emp_name, "Plan"])
            except Exception:
                month["employee_plans"][emp_name] = 0.0
        # show current totals below
        st.markdown("**Current totals**")
        st.table(df_emps[["Current"]])
    else:
        st.info("No employees yet for this month.")
    # Month plan total
    total_planned = sum(float(v or 0.0) for v in month["employee_plans"].values())
    total_current = sum(float(wk.get("total", 0.0) or 0.0) for wk in month["weeks"])
    st.markdown("---")
    st.metric("🎯 Month Plan Total", f"${total_planned:,.2f}")
    st.metric("💰 Month Current Total", f"${total_current:,.2f}")

# Save potential changes to plans
data[selected_month] = month
save_data(data)

st.markdown("---")

# ---------- Main: Weeks list (each week shows table with employees vs days Mon..Sun) ----------
st.header(f"📅 {selected_month} — Weeks (each row = employee; columns = days Mon..Sun)")

# For each week in month["weeks"], render editable table where columns are only dates inside the month
for wi, wk in enumerate(month["weeks"], start=1):
    # compute week dates (we stored label, but need real dates to compute iso keys if needed)
    st.subheader(f"Week {wi}: {wk['label']}")
    # build list of dates from label: label format "Mon_Day - Sun_Day" with months, it's fine to compute dates from month/year and week index
    # Instead of parsing the label, derive week_days from calendar based on year/month and week index
    year = month["year"]
    mnum = month["month"]
    all_weeks = weeks_covering_month(year, mnum)
    # find corresponding week dates list
    try:
        week_dates = all_weeks[wi-1]
    except Exception:
        # fallback: use first week
        week_dates = all_weeks[0]
    # restrict columns to those dates that are inside the selected month
    week_in_month = [d for d in week_dates if d.month == mnum]
    # create column labels in American style: Mon Nov 3
    col_labels = [d.strftime("%a %b %-d") if os.name != "nt" else d.strftime("%a %b %d").replace(" 0", " ") for d in week_in_month]
    # build DataFrame rows: index employee names, columns day labels
    rows = []
    for emp in month["employees"]:
        row = {"Employee": emp}
        for d in week_in_month:
            iso = d.isoformat()
            # profits are stored per week object keyed by employee (we earlier stored one value per employee per week)
            # But user asked to enter profit per day, so we will store daily values inside week["daily_profits"] as dict[emp][iso]
            # To preserve backwards compatibility, check if wk has "daily_profits"
            if "daily_profits" not in wk:
                wk["daily_profits"] = {}
            if emp not in wk["daily_profits"]:
                # initialize from old weekly single value if exists
                val = wk.get("profits", {}).get(emp, 0.0)
                wk["daily_profits"][emp] = {iso: 0.0 for iso in [d.isoformat() for d in week_in_month]}
                # If previous data only had single weekly value, we keep it as 0 daily (can't reconstruct)
            # fetch value if present
            row[col_labels[week_in_month.index(d)]] = float(wk["daily_profits"][emp].get(iso, 0.0))
        rows.append(row)
    if not rows:
        st.info("No employees for this week.")
        continue
    df_week = pd.DataFrame(rows).set_index("Employee")
    # Show data editor (editable daily cells). We exclude totals column because we compute totals from daily values.
    edited = st.data_editor(df_week, num_rows="fixed", key=f"week_editor_{selected_month}_{wi}", use_container_width=True)
    # Immediately write edits back into data structure and recompute totals
    for emp_name in edited.index:
        for j, d in enumerate(week_in_month):
            col_label = col_labels[j]
            try:
                new_val = float(edited.loc[emp_name, col_label])
            except Exception:
                new_val = 0.0
            iso = d.isoformat()
            if "daily_profits" not in month["weeks"][wi-1]:
                month["weeks"][wi-1]["daily_profits"] = {}
            if emp_name not in month["weeks"][wi-1]["daily_profits"]:
                month["weeks"][wi-1]["daily_profits"][emp_name] = {}
            month["weeks"][wi-1]["daily_profits"][emp_name][iso] = new_val
    # compute weekly totals per employee and overall week total
    week_totals = {}
    for emp in month["employees"]:
        total_emp_week = 0.0
        for d in week_in_month:
            iso = d.isoformat()
            total_emp_week += float(month["weeks"][wi-1]["daily_profits"].get(emp, {}).get(iso, 0.0) or 0.0)
        week_totals[emp] = total_emp_week
    # store weekly total summary in wk["total"] as sum of all employees this week
    wk["total"] = sum(week_totals.values())
    # Recompute month current totals (sum of all daily_profits across weeks)
    # We will compute monthly total later for display

    # Show totals table for this week (employee | week total | plan | progress)
    totals_rows = []
    for emp in month["employees"]:
        emp_plan = month["employee_plans"].get(emp, 0.0)
        totals_rows.append({"Employee": emp, "Week Total": week_totals[emp], "Plan": emp_plan,
                            "Progress %": (week_totals[emp] / emp_plan * 100) if emp_plan else None})
    df_totals = pd.DataFrame(totals_rows).set_index("Employee")
    st.markdown("**Weekly totals / progress**")
    # Format progress
    def fmt_progress(x):
        if x is None:
            return ""
        return f"{x:.1f}%"
    st.table(df_totals.assign(**{"Progress %": df_totals["Progress %"].apply(lambda x: fmt_progress(x))}))
    st.markdown("---")

# After all weeks: recompute monthly totals
for emp in month["employees"]:
    monthly_sum = 0.0
    for idx, wk in enumerate(month["weeks"]):
        if "daily_profits" in wk and emp in wk["daily_profits"]:
            for iso_val in wk["daily_profits"][emp].values():
                monthly_sum += float(iso_val or 0.0)
    # update employee current total implicitly used in right panel (saved earlier)
    month["employee_plans"].setdefault(emp, month["employee_plans"].get(emp, 0.0))
# recompute overall current total and planned total
total_planned = sum(float(v or 0.0) for v in month["employee_plans"].values())
total_current = 0.0
for wk in month["weeks"]:
    total_current += float(wk.get("total", 0.0) or 0.0)

# save changes
data[selected_month] = month
save_data(data)

# show final month summary below weeks
st.markdown("## Monthly summary")
col_a, col_b = st.columns([2, 3])
with col_a:
    st.metric("🎯 Month Plan Total", f"${total_planned:,.2f}")
    st.metric("💰 Month Current Total", f"${total_current:,.2f}")
with col_b:
    st.write("Employee plans (editable above).")

# end
