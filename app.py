import streamlit as st
import pandas as pd
import calendar
from datetime import datetime, timedelta
import json
import os

# ---------------- CONFIG ---------------- #
st.set_page_config(page_title="Dispatch Tracker v4", page_icon="🚚", layout="wide")
st.title("🚚 Dispatch Tracker v4")

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
    """Return list of weeks with day numbers (Monday–Sunday)."""
    first_day = datetime(year, month, 1)
    last_day = datetime(year, month, calendar.monthrange(year, month)[1])

    weeks = []
    current = first_day - timedelta(days=first_day.weekday())  # go to Monday
    while current <= last_day:
        week_days = []
        for i in range(7):
            day = current + timedelta(days=i)
            if day.month == month:
                week_days.append(f"{calendar.day_abbr[i]} ({day.day})")
            else:
                week_days.append(f"{calendar.day_abbr[i]} (-)")
        week_label = f"Week {len(weeks)+1} ({current.strftime('%b %d')} - {(current+timedelta(days=6)).strftime('%b %d')})"
        weeks.append((week_label, week_days))
        current += timedelta(days=7)
    return weeks

def ensure_month_structure(month_name):
    """Ensure month exists in data and has correct structure."""
    if month_name not in data:
        prev_month = list(data.keys())[-1] if data else None
        now = datetime.now()
        year = int(month_name.split()[-1])
        month = list(calendar.month_name).index(month_name.split()[0])

        data[month_name] = {
            "employees": [],
            "employee_plans": {},
            "weeks": []
        }

        # copy employees from previous month
        if prev_month:
            data[month_name]["employees"] = data[prev_month]["employees"].copy()
            data[month_name]["employee_plans"] = data[prev_month]["employee_plans"].copy()

        for label, days in get_weeks_with_dates(year, month):
            week_data = {
                "label": label,
                "days": days,
                "profits": {emp: [0]*7 for emp in data[month_name]["employees"]}
            }
            data[month_name]["weeks"].append(week_data)
        save_data(data)

# ---------------- UI ---------------- #
months = list(data.keys()) or [datetime.now().strftime("%B %Y")]
selected_month = st.selectbox("Select Month", months)

col_btn1, col_btn2 = st.columns([1, 4])
with col_btn1:
    if st.button("➕ Add New Month"):
        last_month = datetime.strptime(months[-1], "%B %Y")
        next_month_date = (last_month.replace(day=28) + timedelta(days=4)).replace(day=1)
        next_month_str = next_month_date.strftime("%B %Y")
        ensure_month_structure(next_month_str)
        st.success(f"Added new month: {next_month_str}")
        st.rerun()

ensure_month_structure(selected_month)
month_data = data[selected_month]

# ---------------- EMPLOYEES CONTROL ---------------- #
st.divider()
st.subheader("👥 Employees")

col_add, col_remove = st.columns([2, 2])
with col_add:
    new_employee = st.text_input("Add employee name:")
    if st.button("Add Employee"):
        if new_employee and new_employee not in month_data["employees"]:
            month_data["employees"].append(new_employee)
            month_data["employee_plans"][new_employee] = 0
            for week in month_data["weeks"]:
                week["profits"][new_employee] = [0]*7
            save_data(data)
            st.success(f"Added {new_employee} to {selected_month}")
            st.rerun()

with col_remove:
    if month_data["employees"]:
        remove_name = st.selectbox("Remove employee:", [""] + month_data["employees"])
        if st.button("Remove Selected"):
            if remove_name:
                # Remove from this and all following months
                months_list = list(data.keys())
                start_index = months_list.index(selected_month)
                for m in months_list[start_index:]:
                    if remove_name in data[m]["employees"]:
                        data[m]["employees"].remove(remove_name)
                        data[m]["employee_plans"].pop(remove_name, None)
                        for week in data[m]["weeks"]:
                            week["profits"].pop(remove_name, None)
                save_data(data)
                st.warning(f"{remove_name} removed from {selected_month} and later months.")
                st.rerun()

# ---------------- RIGHT SIDEBAR – EMPLOYEE TABLE ---------------- #
st.divider()
st.markdown("### 💼 Employee Plans (Monthly)")
employee_data = []
total_sum = 0
for emp in month_data["employees"]:
    plan = month_data["employee_plans"].get(emp, 0)
    total_profit = 0
    for week in month_data["weeks"]:
        if emp in week["profits"]:
            total_profit += sum(week["profits"][emp])
    employee_data.append({"Employee": emp, "Plan": plan, "Total": total_profit})
    total_sum += total_profit

df_emp = pd.DataFrame(employee_data)
edited_plans = st.data_editor(df_emp, use_container_width=True, key="plans_editor")

# Update plan values
for _, row in edited_plans.iterrows():
    month_data["employee_plans"][row["Employee"]] = row["Plan"]

st.markdown(f"**💰 Monthly Total: ${total_sum:,.2f}**")

# ---------------- MAIN TABLE ---------------- #
st.divider()
st.markdown(f"### 📅 Weekly Profits for {selected_month}")

for week in month_data["weeks"]:
    st.markdown(f"**{week['label']}**")
    cols = ["Employee"] + week["days"] + ["Weekly Total"]

    rows = []
    for emp in month_data["employees"]:
        profits = week["profits"].get(emp, [0]*7)
        total = sum(profits)
        row = [emp] + profits + [total]
        rows.append(row)

    df = pd.DataFrame(rows, columns=cols)
    edited_df = st.data_editor(
        df,
        key=f"week_{week['label']}",
        use_container_width=True,
        hide_index=True,
    )

    # Update data from editor
    for _, row in edited_df.iterrows():
        emp = row["Employee"]
        week["profits"][emp] = [row[day] for day in week["days"]]
    st.markdown("---")

save_data(data)
