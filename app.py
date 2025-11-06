
import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import date, datetime, timedelta
import calendar

DB = "tracker_v3.db"

def get_conn():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS months (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        start_date TEXT,
        end_date TEXT
    );
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT
    );
    CREATE TABLE IF NOT EXISTS plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER,
        month_id INTEGER,
        planned_profit REAL,
        UNIQUE(employee_id, month_id)
    );
    CREATE TABLE IF NOT EXISTS profits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER,
        month_id INTEGER,
        date TEXT,
        profit REAL,
        UNIQUE(employee_id, month_id, date)
    );
    """)
    conn.commit()
    conn.close()

def month_name(dt):
    return dt.strftime("%B %Y")

def first_day_of_next_month(dt):
    year = dt.year + (dt.month // 12)
    month = dt.month % 12 + 1
    return date(year, month, 1)

def month_date_range_from_start(start_date):
    _, last = calendar.monthrange(start_date.year, start_date.month)
    return start_date, date(start_date.year, start_date.month, last)

def get_or_create_initial_month():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, start_date, end_date, name FROM months ORDER BY start_date DESC LIMIT 1")
    row = cur.fetchone()
    if row is None:
        today = date.today()
        start = date(today.year, today.month, 1)
        _, last = calendar.monthrange(start.year, start.month)
        end = date(start.year, start.month, last)
        name = month_name(start)
        cur.execute("INSERT INTO months (name, start_date, end_date) VALUES (?, ?, ?)", (name, start.isoformat(), end.isoformat()))
        conn.commit()
    conn.close()

def add_new_month():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT start_date FROM months ORDER BY start_date DESC LIMIT 1")
    last = cur.fetchone()
    if last:
        last_start = datetime.fromisoformat(last[0]).date()
        next_start = first_day_of_next_month(last_start)
    else:
        today = date.today()
        next_start = date(today.year, today.month, 1)
    start, end = month_date_range_from_start(next_start)
    name = month_name(start)
    cur.execute("INSERT INTO months (name, start_date, end_date) VALUES (?, ?, ?)", (name, start.isoformat(), end.isoformat()))
    month_id = cur.lastrowid
    # copy employees from previous month if exists: copy all employees present in DB
    cur.execute("SELECT id FROM employees")
    emp_rows = cur.fetchall()
    dates = []
    d = start
    while d <= end:
        dates.append(d)
        d += timedelta(days=1)
    for emp in emp_rows:
        eid = emp[0]
        for dt in dates:
            cur.execute("INSERT OR IGNORE INTO profits (employee_id, month_id, date, profit) VALUES (?, ?, ?, ?)", (eid, month_id, dt.isoformat(), 0.0))
        # copy plan from previous month if exists (take last month's plan)
        cur.execute("SELECT pl.planned_profit FROM plans pl JOIN months m ON pl.month_id = m.id ORDER BY m.start_date DESC LIMIT 1")
        prev_plan = cur.fetchone()
        if prev_plan:
            try:
                cur.execute("INSERT OR IGNORE INTO plans (employee_id, month_id, planned_profit) VALUES (?, ?, ?)", (eid, month_id, prev_plan[0]))
            except:
                pass
    conn.commit()
    conn.close()

def list_months():
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM months ORDER BY start_date DESC", conn)
    conn.close()
    return df

def list_employees():
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM employees ORDER BY name", conn)
    conn.close()
    return df

def add_employee(name, month_id=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO employees (name) VALUES (?)", (name,))
    emp_id = cur.lastrowid
    if month_id:
        cur.execute("SELECT start_date, end_date FROM months WHERE id = ?", (month_id,))
        row = cur.fetchone()
        if row:
            start = datetime.fromisoformat(row[0]).date()
            end = datetime.fromisoformat(row[1]).date()
            d = start
            while d <= end:
                cur.execute("INSERT OR IGNORE INTO profits (employee_id, month_id, date, profit) VALUES (?, ?, ?, ?)", (emp_id, month_id, d.isoformat(), 0.0))
                d += timedelta(days=1)
    conn.commit()
    conn.close()
    return emp_id

def remove_employee_from_month(employee_id, month_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM profits WHERE employee_id = ? AND month_id = ?", (employee_id, month_id))
    cur.execute("DELETE FROM plans WHERE employee_id = ? AND month_id = ?", (employee_id, month_id))
    conn.commit()
    conn.close()

def get_month_dates(month_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT start_date, end_date FROM months WHERE id = ?", (month_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return []
    start = datetime.fromisoformat(row[0]).date()
    end = datetime.fromisoformat(row[1]).date()
    dates = []
    d = start
    while d <= end:
        dates.append(d)
        d += timedelta(days=1)
    return dates

def get_profits_for_month(month_id):
    conn = get_conn()
    df = pd.read_sql("SELECT p.*, e.name FROM profits p JOIN employees e ON e.id = p.employee_id WHERE p.month_id = ?", conn, params=(month_id,))
    conn.close()
    return df

def save_profit(employee_id, month_id, dt_iso, value):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO profits (employee_id, month_id, date, profit) VALUES (?, ?, ?, ?)", (employee_id, month_id, dt_iso, float(value)))
    conn.commit()
    conn.close()

def get_plans(month_id):
    conn = get_conn()
    df = pd.read_sql("SELECT pl.*, e.name FROM plans pl JOIN employees e ON e.id = pl.employee_id WHERE pl.month_id = ?", conn, params=(month_id,))
    return df

def set_plan(employee_id, month_id, planned):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO plans (employee_id, month_id, planned_profit) VALUES (?, ?, ?) ON CONFLICT(employee_id, month_id) DO UPDATE SET planned_profit=excluded.planned_profit", (employee_id, month_id, float(planned)))
    conn.commit()
    conn.close()

# Initialize DB and default month
init_db()
# ensure at least one month exists
conn = get_conn()
cur = conn.cursor()
cur.execute("SELECT COUNT(1) FROM months")
if cur.fetchone()[0] == 0:
    today = date.today()
    start = date(today.year, today.month, 1)
    _, last = calendar.monthrange(start.year, start.month)
    end = date(start.year, start.month, last)
    cur.execute("INSERT INTO months (name, start_date, end_date) VALUES (?, ?, ?)", (start.strftime("%B %Y"), start.isoformat(), end.isoformat()))
    conn.commit()
conn.close()

st.set_page_config(page_title="Dispatch Tracker v3", layout="wide")
st.title("🚛 Dispatch Tracker v3")

months_df = list_months()
month_options = months_df['name'].tolist()
if not month_options:
    st.error("No months available. Add new month.")
    st.stop()

col1, col2 = st.columns([3,1])
with col1:
    selected_month = st.selectbox("Select Month", month_options, index=0)
with col2:
    if st.button("➕ Add New Month"):
        add_new_month()
        st.experimental_rerun()

selected_row = months_df[months_df['name'] == selected_month].iloc[0]
month_id = int(selected_row['id'])
dates = get_month_dates(month_id)

left, main, right = st.columns([1,3,1])
with left:
    st.header("👥 Employees")
    new_name = st.text_input("New employee name")
    if st.button("Add employee to month"):
        if new_name.strip():
            add_employee(new_name.strip(), month_id=month_id)
            st.success(f"Added {new_name} to month {selected_month}")
            st.experimental_rerun()
    st.write("---")
    profits_df = get_profits_for_month(month_id)
    if profits_df.empty:
        st.info("No employees in this month yet.")
    else:
        emps = profits_df[['employee_id','name']].drop_duplicates().sort_values('name')
        for _, r in emps.iterrows():
            eid = int(r['employee_id'])
            st.write(r['name'])
            if st.button(f"Remove {r['name']}", key=f"rem_{eid}"):
                remove_employee_from_month(eid, month_id)
                st.experimental_rerun()

with main:
    st.header(f"📅 {selected_month}")
    start = dates[0]
    end = dates[-1]
    start_monday = start - timedelta(days=(start.weekday()))
    weeks = []
    curd = start_monday
    while curd <= end:
        week_days = [curd + timedelta(days=i) for i in range(7)]
        if any((d >= start and d <= end) for d in week_days):
            weeks.append(week_days)
        curd += timedelta(days=7)
    month_profits = get_profits_for_month(month_id)
    total_month_sum = 0.0
    for wi, week in enumerate(weeks, start=1):
        week_in_month = [d for d in week if d >= start and d <= end]
        cols = [d.strftime("%a %b %d") for d in week_in_month]
        st.subheader(f"Week {wi}: {week_in_month[0].strftime('%b %d')} - {week_in_month[-1].strftime('%b %d')}")
        emps = month_profits[['employee_id','name']].drop_duplicates().sort_values('name')
        if emps.empty:
            st.info("No employees")
            continue
        rows = []
        for _, er in emps.iterrows():
            eid = int(er['employee_id'])
            row = {"employee_id": eid, "name": er['name']}
            week_sum = 0.0
            for d in week_in_month:
                rec = month_profits[(month_profits['employee_id']==eid) & (month_profits['date']==d.isoformat())]
                val = float(rec['profit'].iloc[0]) if not rec.empty else 0.0
                row[d.strftime("%a %b %d")] = val
                week_sum += val
            row["Total"] = week_sum
            rows.append(row)
            total_month_sum += week_sum
        df = pd.DataFrame(rows).set_index('name')
        editable = df.drop(columns=['employee_id','Total'], errors='ignore')
        edited = st.data_editor(editable, num_rows="fixed", key=f"week_{month_id}_{wi}")
        if st.button(f"Save Week {wi}", key=f"save_{month_id}_{wi}"):
            for emp_name in edited.index:
                eid = int(df.loc[emp_name,'employee_id'])
                for d in week_in_month:
                    col = d.strftime("%a %b %d")
                    new_val = float(edited.loc[emp_name, col])
                    save_profit(eid, month_id, d.isoformat(), new_val)
            st.success("Week saved")
            st.experimental_rerun()
        totals = df['Total']
        plans_df = get_plans(month_id)
        plan_map = {r['employee_id']: r['planned_profit'] for _, r in plans_df.iterrows()} if not plans_df.empty else {}
        status = []
        for emp_name in df.index:
            eid = int(df.loc[emp_name,'employee_id'])
            planned = plan_map.get(eid, 0.0)
            tot = df.loc[emp_name,'Total']
            emoji = "✅" if tot >= planned and planned>0 else ("⚠️" if planned>0 else "")
            status.append(emoji)
        df_display = df.copy()
        df_display['Total'] = df_display['Total'].round(2)
        df_display['Status'] = status
        st.dataframe(df_display.style.format("{:.2f}"), use_container_width=True)
        st.write("---")
    st.markdown(f"### 🔢 Total month profit: **{total_month_sum:.2f}**")

with right:
    st.header("📋 Monthly Plan")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT e.id, e.name FROM employees e JOIN profits p ON e.id = p.employee_id WHERE p.month_id = ? ORDER BY e.name", (month_id,))
    emps = cur.fetchall()
    rows = []
    for eid, name in emps:
        cur.execute("SELECT planned_profit FROM plans WHERE employee_id = ? AND month_id = ?", (eid, month_id))
        pr = cur.fetchone()
        planned = float(pr[0]) if pr else 0.0
        cur.execute("SELECT SUM(profit) FROM profits WHERE employee_id = ? AND month_id = ?", (eid, month_id))
        s = cur.fetchone()[0] or 0.0
        rows.append({"employee_id": eid, "name": name, "planned": planned, "current": s})
    conn.close()
    plan_df = pd.DataFrame(rows).set_index('name') if rows else pd.DataFrame(columns=['employee_id','planned','current'])
    edited_plans = st.data_editor(plan_df[['planned']], num_rows="fixed", key=f"plans_{month_id}")
    if st.button("Save Plans"):
        for name in edited_plans.index:
            eid = int(plan_df.loc[name, 'employee_id'])
            planned_val = float(edited_plans.loc[name, 'planned'])
            set_plan(eid, month_id, planned_val)
        st.success("Plans saved")
        st.experimental_rerun()
    if not plan_df.empty:
        total_planned = plan_df['planned'].sum()
        total_current = plan_df['current'].sum()
        st.markdown(f"**Total Planned:** {total_planned:.2f}")
        st.markdown(f"**Total Current:** {total_current:.2f}")
