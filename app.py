import streamlit as st
import pandas as pd
import calendar
from datetime import datetime, timedelta
import json
import os

# ---------------- CONFIG ---------------- #
st.set_page_config(page_title="Dispatch Tracker v4", page_icon="truck", layout="wide")
st.title("truck Dispatch Tracker v4")

# CSS — узкие колонки + перенос строки
st.markdown("""
<style>
[data-testid="stTable"] th,
[data-testid="stTable"] td {
    white-space: pre-line !important;
    text-align: center !important;
    line-height: 1.4 !important;
    font-size: 13px !important;
    padding: 6px 4px !important;
    vertical-align: top !important;
}
[data-testid="stTable"] th:nth-child(n+2):nth-child(-n+8),
[data-testid="stTable"] td:nth-child(n+2):nth-child(-n+8) {
    width: 60px !important;
    min-width: 60px !important;
    max-width: 60px !important;
}
[data-testid="stTable"] th:first-child,
[data-testid="stTable"] td:first-child {
    min-width: 100px !important;
    width: 100px !important;
}
[data-testid="stTable"] th:last-child,
[data-testid="stTable"] td:last-child {
    width: 80px !important;
    min-width: 80px !important;
}
</style>
""", unsafe_allow_html=True)

DATA_FILE = "dispatch_data.json"

# ---------------- LOAD & SAVE ---------------- #
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()

# ---------------- HELPERS ---------------- #
def get_weeks_with_dates(year, month):
    first_day = datetime(year, month, 1)
    last_day = datetime(year, month, calendar.monthrange(year, month)[1])
    weeks = []
    current = first_day - timedelta(days=first_day.weekday())
    while current <= last_day:
        week_days = []
        for i in range(7):
            day = current + timedelta(days=i)
            if day.month == month:
                week_days.append(f"{calendar.day_abbr[i]}\n{day.month}/{day.day}")
            else:
                week_days.append("-\n-")
        week_label = f"Week {len(weeks)+1} ({current.strftime('%b %d')} - {(current + timedelta(days=6)).strftime('%b %d')})"
        weeks.append((week_label, week_days))
        current += timedelta(days=7)
    return weeks

def ensure_month_structure(month_name):
    if month_name not in data:
        prev_month = list(data.keys())[-1] if data else None
        try:
            year = int(month_name.split()[-1])
            month_str = month_name.split()[0]
            month = list(calendar.month_name).index(month_str)
        except (ValueError, IndexError):
            st.error(f"Invalid month format: {month_name}")
            return

        data[month_name] = {"employees": [], "employee_plans": {}, "weeks": []}
        if prev_month and prev_month in data:
            data[month_name]["employees"] = data[prev_month]["employees"].copy()
            data[month_name]["employee_plans"] = data[prev_month]["employee_plans"].copy()

        for label, days in get_weeks_with_dates(year, month):
            data[month_name]["weeks"].append({"label": label, "days": days, "profits": {}})

    month_data = data[month_name]
    month_data.setdefault("weeks", [])
    month_data.setdefault("employees", [])
    month_data.setdefault("employee_plans", {})

    current_employees = set(month_data["employees"])
    for week in month_data["weeks"]:
        week.setdefault("profits", {})
        week.setdefault("days", [])
        if not week["days"]:
            try:
                year = int(month_name.split()[-1])
                month = list(calendar.month_name).index(month_name.split()[0])
                all_weeks = get_weeks_with_dates(year, month)
                idx = next((i for i, (lbl, _) in enumerate(all_weeks) if lbl == week["label"]), None)
                if idx is not None:
                    _, days = all_weeks[idx]
                    week["days"] = days
            except:
                pass

        for emp in current_employees - week["profits"].keys():
            week["profits"][emp] = [0] * 7
        for emp in list(week["profits"].keys() - current_employees):
            week["profits"].pop(emp, None)

    save_data(data)

# ---------------- UI ---------------- #
available_months = list(data.keys())
if not available_months:
    default_month = datetime.now().strftime("%B %Y")
    ensure_month_structure(default_month)
    available_months = [default_month]

selected_month = st.selectbox("Select Month", available_months)

col_btn1, _ = st.columns([1, 4])
with col_btn1:
    if st.button("Add New Month"):
        try:
            last_month = datetime.strptime(available_months[-1], "%B %Y")
            next_month_date = (last_month.replace(day=28) + timedelta(days=4)).replace(day=1)
            next_month_str = next_month_date.strftime("%B %Y")
            ensure_month_structure(next_month_str)
            st.success(f"Added new month: {next_month_str}")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to add month: {e}")

ensure_month_structure(selected_month)
month_data = data[selected_month]

# ---------------- EMPLOYEES ---------------- #
st.divider()
st.subheader("Employees")

col_add, col_remove = st.columns([2, 2])
with col_add:
    new_employee = st.text_input("Add employee name:", key="add_emp_input")
    if st.button("Add Employee", key="add_emp_btn"):
        if new_employee and new_employee not in month_data["employees"]:
            month_data["employees"].append(new_employee)
            month_data["employee_plans"][new_employee] = 0
            for week in month_data["weeks"]:
                week["profits"][new_employee] = [0]*7
            save_data(data)
            st.success(f"Added {new_employee}")
            st.rerun()
        elif new_employee in month_data["employees"]:
            st.warning("Employee already exists.")

with col_remove:
    if month_data["employees"]:
        remove_name = st.selectbox("Remove employee:", [""] + month_data["employees"], key="remove_emp_select")
        if st.button("Remove Selected", key="remove_emp_btn"):
            if remove_name:
                months_list = list(data.keys())
                try:
                    start_index = months_list.index(selected_month)
                except ValueError:
                    start_index = 0
                for m in months_list[start_index:]:
                    if m in data and remove_name in data[m]["employees"]:
                        data[m]["employees"].remove(remove_name)
                        data[m]["employee_plans"].pop(remove_name, None)
                        for week in data[m].get("weeks", []):
                            week["profits"].pop(remove_name, None)
                save_data(data)
                st.warning(f"{remove_name} removed.")
                st.rerun()

# ---------------- PLANS ---------------- #
st.divider()
st.markdown("### Employee Plans (Monthly)")

employee_data = []
total_sum = 0
for emp in month_data["employees"]:
    plan = month_data["employee_plans"].get(emp, 0)
    total_profit = sum(sum(week.get("profits", {}).get(emp, [0]*7)) for week in month_data.get("weeks", []))
    employee_data.append({"Employee": emp, "Plan": plan, "Total": total_profit})
    total_sum += total_profit

df_emp = pd.DataFrame(employee_data)
if not df_emp.empty:
    edited_plans = st.data_editor(df_emp, use_container_width=True, key="plans_editor")
    for _, row in edited_plans.iterrows():
        month_data["employee_plans"][row["Employee"]] = row["Plan"]
else:
    st.info("No employees yet.")

st.markdown(f"**Monthly Total: ${total_sum:,.2f}**")

# ---------------- WEEKLY PROFITS ---------------- #
st.divider()
st.markdown(f"### Weekly Profits for {selected_month}")

weeks = month_data.get("weeks", [])
if not weeks:
    st.warning("No weeks found. Recreating...")
    ensure_month_structure(selected_month)
    weeks = month_data.get("weeks", [])
    st.rerun()

for week in weeks:
    label = week.get("label", "Unknown Week")
    days = week.get("days", [])
    
    if not days:
        try:
            year = int(selected_month.split()[-1])
            month = list(calendar.month_name).index(selected_month.split()[0])
            all_weeks = get_weeks_with_dates(year, month)
            idx = next((i for i, (lbl, _) in enumerate(all_weeks) if lbl == label), None)
            if idx is not None:
                _, days = all_weeks[idx]
                week["days"] = days
                save_data(data)
                st.rerun()
        except:
            continue

    # --- КЛЮЧЕВОЕ: Уникальные имена колонок без \n ---
    safe_days = [f"day_{i}" for i in range(len(days))]
    cols = ["Employee"] + safe_days + ["Weekly Total"]

    rows = []
    for emp in month_data["employees"]:
        profits = week.get("profits", {}).get(emp, [0]*7)
        rows.append([emp] + profits + [sum(profits)])

    df = pd.DataFrame(rows, columns=cols)

    # Отображаем с красивыми заголовками через HTML
    header_html = "<tr><th>Employee</th>" + "".join(f"<th style='white-space: pre-line; text-align: center;'>{d}</th>" for d in days) + "<th>Weekly Total</th></tr>"
    st.markdown(f"**{label}**", unsafe_allow_html=True)
    st.markdown(header_html, unsafe_allow_html=True)

    edited_df = st.data_editor(
        df,
        key=f"week_{label}",
        use_container_width=True,
        hide_index=True,
    )

    # Сохраняем по порядку
    for idx, row in edited_df.iterrows():
        emp = row["Employee"]
        week["profits"][emp] = list(row[safe_days])

    st.markdown("---")

save_data(data)
