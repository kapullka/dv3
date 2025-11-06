import streamlit as st
import pandas as pd
import calendar
from datetime import datetime, timedelta
import json
import os

# ---------------- CONFIG ---------------- #
st.set_page_config(page_title="Dispatch Tracker v3", page_icon="🚚", layout="wide")
st.title("🚚 Dispatch Tracker v3")

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
            "plan": {"Monthly Target": 0, "Notes": ""},
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
    next_month_date = datetime.strptime(months[-1], "%B %Y") + timedelta(days=31)
    next_month_str = next_month_date.strftime("%B %Y")
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
            for week in month_data["weeks"]:
                week["profits"][new_employee] = 0
            save_data(data)
            st.success(f"Added {new_employee} to month {selected_month}")
            st.rerun()

# ---------------- WEEKS TABLE ---------------- #
st.divider()
st.subheader(f"📅 Weekly Profits – {selected_month}")

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

save_data(data)

# ---------------- MONTHLY SUMMARY ---------------- #
st.subheader("📊 Monthly Plan & Summary")

col1, col2 = st.columns([2, 3])

with col1:
    total_month = sum(week["total"] for week in month_data["weeks"])
    st.metric("💰 Total Monthly Profit", f"${total_month:,.2f}")

    plan_target = st.number_input(
        "Monthly Target ($)", 
        value=float(month_data["plan"].get("Monthly Target", 0)),
        step=100.0
    )
    month_data["plan"]["Monthly Target"] = plan_target

    notes = st.text_area("Notes / Goals", month_data["plan"].get("Notes", ""))
    month_data["plan"]["Notes"] = notes

    if st.button("💾 Save Monthly Plan"):
        save_data(data)
        st.success("Monthly plan saved successfully!")

with col2:
    st.markdown("### 👤 Employees List")
    if month_data["employees"]:
        st.table(pd.DataFrame(month_data["employees"], columns=["Employee"]))
    else:
        st.info("No employees added yet.")

save_data(data)
