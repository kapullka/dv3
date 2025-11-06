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
def get_week_ranges(year, month):
    """Return list of weeks (Monday–Sunday) with numbers."""
    weeks = []
    first_day = datetime(year, month, 1)
    last_day = datetime(year, month, calendar.monthrange(year, month)[1])
    current = first_day - timedelta(days=first_day.weekday())
    while current <= last_day:
        week_start = current
        week_end = current + timedelta(days=6)
        weeks.append((week_start, week_end))
        current += timedelta(days=7)
    return weeks

def ensure_month_structure(month_name):
    """Ensure month exists in data."""
    if month_name not in data:
        now = datetime.now()
        data[month_name] = {
            "employees": [],
            "employee_plans": {},
            "weeks": []
        }
        year = int(month_name.split()[-1])
        month = list(calendar.month_name).index(month_name.split()[0])
        for start, end in get_week_ranges(year, month):
            week_label = f"{start.strftime('%b %d')} - {end.strftime('%b %d')}"
            data[month_name]["weeks"].append({
                "label": week_label,
                "profits": {},
                "total": 0
            })
        save_data(data)

# ---------------- UI ---------------- #
months = list(data.keys()) or [datetime.now().strftime("%B %Y")]
selected_month = st.selectbox("Select Month", months)

if st.button("➕ Add New Month"):
    last_month_date = datetime.strptime(months[-1], "%B %Y")
    next_month = last_month_date.replace(day=28) + timedelta(days=4)
    next_month_str = next_month.strftime("%B %Y")
    ensure_month_structure(next_month_str)
    save_data(data)
    st.success(f"Added new month: {next_month_str}")
    st.rerun()

ensure_month_structure(selected_month)
month_data = data[selected_month]

# ---------------- EMPLOYEES ---------------- #
st.subheader("👥 Employees")
col1, col2 = st.columns([3, 1])
with col1:
    new_employee = st.text_input("New employee name")
with col2:
    if st.button("Add employee to month"):
        if new_employee and new_employee not in month_data["employees"]:
            month_data["employees"].append(new_employee)
            month_data["employee_plans"][new_employee] = 0
            for week in month_data["weeks"]:
                week["profits"][new_employee] = 0
            save_data(data)
            st.success(f"Added {new_employee} to month {selected_month}")
            st.rerun()

# ---------------- MONTHLY PLAN HEADER ---------------- #
total_month = sum(week["total"] for week in month_data["weeks"])
monthly_plan_total = sum(month_data["employee_plans"].values())

header_col1, header_col2 = st.columns([3, 2])
with header_col1:
    st.markdown(f"### 📅 {selected_month}")
with header_col2:
    st.metric("🎯 Monthly Target", f"${monthly_plan_total:,.2f}")
    st.metric("💰 Current Total", f"${total_month:,.2f}")

# ---------------- EMPLOYEE PLANS TABLE ---------------- #
if month_data["employees"]:
    emp_data = []
    for emp in month_data["employees"]:
        emp_total = sum(week["profits"].get(emp, 0) for week in month_data["weeks"])
        emp_plan = month_data["employee_plans"].get(emp, 0)
        emp_data.append({"Employee": emp, "Plan": emp_plan, "Done": emp_total})

    df_emp = pd.DataFrame(emp_data)
    edited_emp = st.data_editor(df_emp, key="emp_plans", use_container_width=True)

    # Update data
    for _, row in edited_emp.iterrows():
        month_data["employee_plans"][row["Employee"]] = row["Plan"]

else:
    st.info("No employees added yet.")

st.divider()

# ---------------- WEEKS TABLE ---------------- #
st.subheader(f"📊 Weekly Profits – {selected_month}")

for i, week in enumerate(month_data["weeks"]):
    st.markdown(f"**{week['label']}**")
    week_profits = week["profits"]

    if not week_profits:
        for emp in month_data["employees"]:
            week_profits[emp] = 0

    df = pd.DataFrame(list(week_profits.items()), columns=["Employee", "Profit"])
    df["Profit"] = df["Profit"].astype(float)
    total_week = df["Profit"].sum()
    week["total"] = total_week

    edited_df = st.data_editor(
        df,
        num_rows="fixed",
        key=f"week_{i}",
        use_container_width=True
    )

    for _, row in edited_df.iterrows():
        week["profits"][row["Employee"]] = row["Profit"]

    st.markdown(f"**Weekly Total:** ${total_week:,.2f}")
    st.divider()

# ---------------- SAVE ---------------- #
save_data(data)
