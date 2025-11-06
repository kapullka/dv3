# app.py — Final version: employee management, weeks with daily cells, right fixed employee list,
# add/remove propagate to future months, autosave, safe normalization of old data.
import streamlit as st
import pandas as pd
import calendar
from datetime import date, datetime, timedelta
import json
import os
from typing import Dict, Any, List, Tuple

APP_TITLE = "Dispatch Tracker — Final"
DATA_FILE = "dispatch_data.json"

st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)

# -------------------- CSS: компактность, узкие колонки, минимум отступов --------------------
st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    .css-1d391kg { padding-top: 0.5rem; }
    
    [data-testid="stTable"] th,
    [data-testid="stTable"] td {
        white-space: pre-line !important;
        text-align: center !important;
        font-size: 12px !important;
        padding: 4px 2px !important;
        line-height: 1.3 !important;
    }
    [data-testid="stTable"] th:nth-child(n+2):nth-child(-n+8),
    [data-testid="stTable"] td:nth-child(n+2):nth-child(-n+8) {
        width: 55px !important;
        min-width: 55px !important;
        max-width: 55px !important;
    }
    [data-testid="stTable"] th:first-child,
    [data-testid="stTable"] td:first-child {
        min-width: 90px !important;
        width: 90px !important;
    }
    [data-testid="stTable"] th:last-child,
    [data-testid="stTable"] td:last-child {
        width: 70px !important;
        min-width: 70px !important;
    }
    .stMarkdown + .stMarkdown { margin-top: -1rem; }
</style>
""", unsafe_allow_html=True)

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

# -------------------- Load & normalize --------------------
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
        md.setdefault("employee_plans", {e: 0.0 for e in md.get("employees", [])})
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
                    if old_week and isinstance(old_week.get("daily_profits"), dict):
                        old_val = old_week["daily_profits"].get(emp, {}).get(iso)
                        week_obj["daily_profits"][emp][iso] = float(old_val) if old_val is not None else 0.0
                    else:
                        week_obj["daily_profits"][emp][iso] = 0.0
            new_weeks.append(week_obj)
        md["weeks"] = new_weeks
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

# -------------------- Employee ops --------------------
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
                            wk["daily_profits"][name][iso] = 0.0
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

# -------------------- Init --------------------
data = load_data()
save_data(data)

# ---------- UI: Top controls ----------
month_keys = sorted(list(data.keys()), key=lambda k: month_sort_key(k, data), reverse=True)
if not month_keys:
    t = date.today()
    key = t.strftime("%B %Y")
    data[key] = {"year": t.year, "month": t.month, "employees": [], "employee_plans": {}, "weeks": []}
    month_keys = [key]
    save_data(data)

col_left, col_right = st.columns([2, 1])
with col_left:
    selected_month = st.selectbox("Select month", month_keys, index=0, key="month_select")
with col_right:
    if st.button("Add New Month"):
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
            st.success(f"Created {nxt_key}")
            st.rerun()

if selected_month not in data:
    selected_month = month_keys[0]
md = data[selected_month]

# Нормализация недель
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

# -------------------- Right panel --------------------
_, right_col = st.columns([3, 1])
with right_col:
    st.markdown("### Employee list")
    with st.form("add_remove_form", clear_on_submit=False):
        new_emp = st.text_input("New employee", key="new_emp")
        col_a, col_b = st.columns(2)
        with col_a:
            add_btn = st.form_submit_button("Add")
        with col_b:
            remove_select = st.selectbox("Remove", [""] + md.get("employees", []), key="remove_emp")
            remove_btn = st.form_submit_button("Remove")
        if add_btn and new_emp.strip():
            add_employee_to_month_and_future(data, selected_month, new_emp.strip())
            st.success(f"Added '{new_emp.strip()}'")
            st.rerun()
        if remove_btn and remove_select:
            remove_employee_from_month_and_future(data, selected_month, remove_select)
            st.success(f"Removed '{remove_select}'")
            st.rerun()

    # Планы
    rows = []
    for emp in md.get("employees", []):
        # Безопасный подсчёт текущего
        cur = 0.0
        for wk in md.get("weeks", []):
            emp_profits = wk.get("daily_profits", {}).get(emp, {})
            cur += sum(float(v) for v in emp_profits.values() if v is not None)
        plan_val = float(md.get("employee_plans", {}).get(emp, 0.0))
        rows.append({"Employee": emp, "Plan": plan_val, "Current": cur})
    if rows:
        df_emps = pd.DataFrame(rows).set_index("Employee")
        edited = st.data_editor(df_emps[["Plan"]], key=f"plans_{selected_month}", use_container_width=True, num_rows="fixed")
        for emp_name in edited.index:
            md["employee_plans"][emp_name] = float(edited.loc[emp_name, "Plan"])
        st.markdown("**Current**")
        st.table(df_emps[["Current"]].style.format("${:,.0f}"))
    else:
        st.info("No employees")

    # Итоги
    total_planned = sum(float(md.get("employee_plans", {}).get(e, 0.0)) for e in md.get("employees", []))
    total_current = sum(
        sum(float(v) for v in wk.get("daily_profits", {}).get(e, {}).values() if v is not None)
        for wk in md.get("weeks", [])
        for e in md.get("employees", [])
    )
    st.markdown("---")
    st.metric("Month Plan", f"${total_planned:,.0f}")
    st.metric("Month Current", f"${total_current:,.0f}")

data[selected_month] = md
save_data(data)

# -------------------- Main: Weeks --------------------
st.markdown(f"### {selected_month}")

for wi, week_dates in enumerate(weeks_covering_month(md["year"], md["month"]), start=1):
    week_in_month = [d for d in week_dates if d.month == md["month"]]
    if not week_in_month:
        continue

    st.markdown(f"**Week {wi}: {week_in_month[0].strftime('%b %d')} - {week_in_month[-1].strftime('%b %d')}**")

    tech_days = [f"day_{i}" for i in range(len(week_in_month))]
    display_days = [d.strftime("%a\n%-d") for d in week_in_month]

    header_html = "<tr><th>Employee</th>" + "".join(
        f"<th style='white-space: pre-line; text-align: center;'>{d}</th>" for d in display_days
    ) + "<th>Week Total</th></tr>"
    st.markdown(header_html, unsafe_allow_html=True)

    rows = []
    for emp in md.get("employees", []):
        row = {"Employee": emp}
        profits = []
        for i, d in enumerate(week_in_month):
            iso = d.isoformat()
            val = float(md["weeks"][wi-1]["daily_profits"].get(emp, {}).get(iso, 0.0))
            row[tech_days[i]] = val
            profits.append(val)
        row["Weekly Total"] = sum(profits)
        rows.append(row)

    df = pd.DataFrame(rows)

    edited = st.data_editor(
        df,
        key=f"week_{selected_month}_{wi}",
        use_container_width=True,
        hide_index=True,
        column_config={
            "Weekly Total": st.column_config.NumberColumn("Weekly Total", format="$%.0f", disabled=True),
            **{tech_days[i]: st.column_config.NumberColumn(tech_days[i], format="$%.0f", min_value=0) for i in range(len(tech_days))}
        }
    )

    for _, row in edited.iterrows():
        emp = row["Employee"]
        for i in range(len(week_in_month)):
            md["weeks"][wi-1]["daily_profits"].setdefault(emp, {})[week_in_month[i].isoformat()] = float(row[tech_days[i]])

    st.markdown("---")

save_data(data)
