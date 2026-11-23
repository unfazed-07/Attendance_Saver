from __future__ import annotations

from datetime import date, timedelta
from math import floor
import os
from pathlib import Path

import pandas as pd
import requests
import streamlit as st


st.set_page_config(page_title="Attendance Saver", page_icon="📚", layout="wide")

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
HOLIDAY_SEED = [
    date(2026, 8, 15), date(2026, 10, 2), date(2026, 10, 20),
    date(2026, 10, 26), date(2026, 11, 7), date(2026, 11, 8),
    date(2026, 11, 9), date(2026, 11, 10), date(2026, 11, 24),
]
MTT_DATES = {date(2026, 10, day) for day in range(12, 18)}
TARGETS = [90, 85, 80, 75]
API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def api_call(method: str, path: str, **kwargs):
    headers = dict(kwargs.pop("headers", {}))
    token = st.session_state.get("access_token")
    if token and not path.startswith("/api/auth/"):
        headers["Authorization"] = f"Bearer {token}"
    if headers:
        kwargs["headers"] = headers
    response = requests.request(method, f"{API_BASE_URL}{path}", timeout=60, **kwargs)
    if not response.ok:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise RuntimeError(f"API returned {response.status_code}: {detail}")
    return response.json()


def ensure_profile() -> str:
    # Streamlit keeps session_state across hot reloads; discard any ID left
    # over from the removed phone/email sign-in flow if its token is missing.
    if not st.session_state.get("student_id") or not st.session_state.get("access_token"):
        profile = api_call("POST", "/api/auth/guest")
        st.session_state.access_token = profile["access_token"]
        st.session_state.student_id = profile["student_id"]
    return st.session_state.student_id


def slots_to_grid(slots: list[dict[str, object]]) -> pd.DataFrame:
    by_course: dict[str, dict[str, object]] = {}
    for slot in slots:
        code = str(slot["course_code"])
        row = by_course.setdefault(code, {"course_code": code, **{day: 0 for day in WEEKDAYS}})
        day = slot["day_of_week"]
        if day in WEEKDAYS:
            row[day] += int(slot["attendance_units"])
    return pd.DataFrame(list(by_course.values()), columns=["course_code", *WEEKDAYS])


def attendance_frame(rows: list[dict[str, object]]) -> pd.DataFrame:
    columns = ["course_code", "course_name", "total_delivered", "total_attended", "duty_leave", "first_week_bonus", "reported_percentage"]
    return pd.DataFrame(rows, columns=columns)


def rounded_percent(attended: int, delivered: int) -> int:
    if delivered <= 0:
        return 0
    return min(100, floor(attended * 100 / delivered + 0.5))


def marks_for(percent: int) -> int:
    if percent >= 90:
        return 5
    if percent >= 85:
        return 4
    if percent >= 80:
        return 3
    if percent >= 75:
        return 2
    return 0


def teaching_days(start: date, end: date, holidays: set[date], mtt_dates: set[date]) -> list[date]:
    days: list[date] = []
    current = start
    while current <= end:
        if current.weekday() != 6 and current not in holidays and current not in mtt_dates:
            days.append(current)
        current += timedelta(days=1)
    return days


def slab_rows(attended: int, delivered: int, remaining: int) -> list[dict[str, object]]:
    rows = []
    for target in TARGETS:
        total = delivered + remaining
        strict_required = (target * total + 99) // 100
        rounded_required = ((2 * target - 1) * total + 199) // 200
        must_attend = max(0, strict_required - attended)
        reachable = must_attend <= remaining
        rows.append({
            "Target": f"{target}% · {marks_for(target)} marks",
            "Attend (strict)": must_attend,
            "Can miss": max(0, remaining - must_attend) if reachable else 0,
            "Reachable": "Yes" if reachable else "No",
            "Rounded threshold": rounded_required,
        })
    return rows


def readable_slab_table(rows: list[dict[str, object]]) -> pd.DataFrame:
    table = pd.DataFrame(rows)
    return table.rename(columns={
        "Target": "Target and attendance marks",
        "Attend (strict)": "Sessions to attend",
        "Can miss": "Sessions you can miss",
        "Reachable": "Can reach target?",
    }).drop(columns=["Rounded threshold"], errors="ignore")


if st.session_state.get("data_version") != 2:
    st.session_state.attendance = attendance_frame([])
    st.session_state.timetable = slots_to_grid([])
    st.session_state.attendance_editor_version = st.session_state.get("attendance_editor_version", 0) + 1
    st.session_state.timetable_editor_version = st.session_state.get("timetable_editor_version", 0) + 1
    st.session_state.data_verified = False
    st.session_state.data_version = 2
if "attendance" not in st.session_state:
    st.session_state.attendance = attendance_frame([])
if "attendance_editor_version" not in st.session_state:
    st.session_state.attendance_editor_version = 0
if "timetable" not in st.session_state:
    st.session_state.timetable = slots_to_grid([])
if "timetable_editor_version" not in st.session_state:
    st.session_state.timetable_editor_version = 0

st.markdown("""
<style>
  .block-container {padding-top: 2rem; padding-bottom: 3rem; max-width: 1440px;}
  [data-testid="stMetric"] {background:#f5f7fb; border:1px solid #e4e9f2; padding:16px; border-radius:14px;}
  h1 {letter-spacing:-.04em;}
</style>
""", unsafe_allow_html=True)

st.title("📚 Attendance Saver")
st.caption("Know where you stand, plan the classes ahead, and see how many you can safely miss.")

with st.sidebar:
    st.header("Fixed session calendar")
    reference_day = date(2026, 11, 23)
    semester_end = date(2026, 12, 11)
    holiday_dates = HOLIDAY_SEED
    st.write("**Odd Semester Aug–Dec 2026**")
    st.caption("Aug 10 – Dec 11 · Today: Nov 23 · MTT: Oct 12–17")
    st.caption("The calendar is fixed for this project. Sundays, test days, and listed holidays do not count as teaching days.")
    try:
        requests.get(f"{API_BASE_URL}/health", timeout=2).raise_for_status()
        st.success("Backend connected")
    except requests.RequestException:
        st.warning("Backend or Azure SQL is unavailable. Check the backend terminal and Azure SQL settings.")
setup, dashboard = st.tabs(["1 · Set up your data", "2 · Attendance dashboard"])
with setup:
    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("Timetable")
        st.write("Upload your weekly schedule or add classes in the grid. A two-hour practical counts as two class sessions.")
        schedule_file = st.file_uploader("Schedule.xlsx", type=["xlsx"], key="schedule_upload")
        if schedule_file:
            st.caption(f"Selected: {schedule_file.name}")
            if st.button("Parse and save timetable", type="primary", key="parse_schedule"):
                try:
                    ensure_profile()
                    parsed = api_call("POST", "/api/student/upload-timetable", files={"file": (schedule_file.name, schedule_file.getvalue(), schedule_file.type or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
                    st.session_state.timetable = slots_to_grid(parsed["slots"])
                    st.session_state.timetable_editor_version += 1
                    st.session_state.timetable_saved = True
                    st.session_state.data_verified = False
                    st.success(f"Parsed {len(parsed['slots'])} timetable entries for {len(st.session_state.timetable)} courses.")
                except (RuntimeError, requests.RequestException) as exc:
                    st.error(str(exc))
        prior_timetable = st.session_state.timetable.copy()
        edited_timetable = st.data_editor(
            st.session_state.timetable,
            key=f"timetable_editor_{st.session_state.timetable_editor_version}",
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "course_code": st.column_config.TextColumn("Course code", required=True),
                **{day: st.column_config.NumberColumn(f"{day[:3]} sessions", min_value=0, max_value=8, step=1) for day in WEEKDAYS},
            },
        )
        if not edited_timetable.equals(prior_timetable):
            st.session_state.data_verified = False
        st.session_state.timetable = edited_timetable

    with right:
        st.subheader("Attendance summary")
        st.write("Upload your attendance screenshot or enter the figures below. Azure Document Intelligence can read the image when configured.")
        attendance_file = st.file_uploader("Attendance_Summary.png", type=["png", "jpg", "jpeg"], key="attendance_upload")
        if attendance_file:
            st.image(attendance_file, caption="Selected attendance summary", use_container_width=True)
            if st.button("Read attendance with Azure AI", type="primary", key="parse_attendance"):
                try:
                    ensure_profile()
                    parsed = api_call("POST", "/api/student/upload-attendance", files={"file": (attendance_file.name, attendance_file.getvalue(), attendance_file.type or "image/png")})
                    st.session_state.attendance = attendance_frame(parsed["rows"])
                    st.session_state.attendance_editor_version += 1
                    st.session_state.attendance_saved = True
                    st.session_state.data_verified = False
                    st.success(f"Read {len(parsed['rows'])} course rows. Review and edit them below.")
                except (RuntimeError, requests.RequestException) as exc:
                    st.error(str(exc))
                    if "AZURE_DOCUMENT_INTELLIGENCE" in str(exc):
                        st.info("You can still enter or edit attendance manually below. Azure OCR will work after its endpoint and key are added to .env.")
        prior_attendance = st.session_state.attendance.copy()
        edited_attendance = st.data_editor(
            st.session_state.attendance,
            key=f"attendance_editor_{st.session_state.attendance_editor_version}",
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "course_code": st.column_config.TextColumn("Course code", required=True),
                "course_name": st.column_config.TextColumn("Course name"),
                **{name: st.column_config.NumberColumn(label, min_value=0, step=1) for name, label in [
                    ("total_delivered", "Delivered"), ("total_attended", "Attended"),
                    ("duty_leave", "Duty leave"), ("first_week_bonus", "First week bonus"),
                ]},
            },
        )
        if not edited_attendance.equals(prior_attendance):
            st.session_state.data_verified = False
        st.session_state.attendance = edited_attendance
        st.subheader("Project session calendar")
        calendar_path = PROJECT_ROOT / "sample_data" / "Session_Calendar.png"
        if calendar_path.exists():
            with st.expander("View fixed Session_Calendar.png"):
                st.image(str(calendar_path), use_container_width=True)
        if st.button("Save / verify both tables", key="save_verify"):
            try:
                student_id = ensure_profile()
                records = []
                for row in st.session_state.attendance.fillna(0).to_dict(orient="records"):
                    course_code = str(row.get("course_code", "")).strip()
                    if not course_code:
                        continue
                    records.append({
                        "course_code": course_code,
                        "course_name": str(row.get("course_name", "")).strip(),
                        "total_delivered": int(row.get("total_delivered", 0)),
                        "total_attended": int(row.get("total_attended", 0)),
                        "duty_leave": int(row.get("duty_leave", 0)),
                        "first_week_bonus": int(row.get("first_week_bonus", 0)),
                        "reported_percentage": 0,
                    })
                timetable_rows = []
                grid = st.session_state.timetable.fillna(0)
                for row in grid.to_dict(orient="records"):
                    course_code = str(row.get("course_code", "")).strip()
                    if not course_code:
                        continue
                    for day in WEEKDAYS:
                        units = int(row.get(day, 0))
                        if units:
                            timetable_rows.append({"course_code": course_code, "day_of_week": day, "time_slot": "Weekly total", "class_type": "L", "attendance_units": units})
                api_call("PUT", f"/api/student/{student_id}/verify-data", json={"attendance_records": records, "timetable_slots": timetable_rows})
                st.session_state.data_verified = True
                st.success("Your verified data is saved. Open the dashboard tab to review your attendance plan.")
            except (RuntimeError, requests.RequestException) as exc:
                st.error(str(exc))

with dashboard:
    attendance = st.session_state.attendance.fillna(0).copy()
    timetable = st.session_state.timetable.fillna(0).copy()
    if attendance.empty or timetable.empty:
        st.info("Upload or enter both your attendance summary and weekly timetable in the setup tab. Your dashboard will appear once both are provided.")
    else:
        attendance["attended_effective"] = attendance["total_attended"] + attendance["duty_leave"] + attendance["first_week_bonus"]
        future_days = teaching_days(reference_day + timedelta(days=1), semester_end, set(holiday_dates), MTT_DATES)
        day_counts = {day: sum(d.weekday() == index for d in future_days) for index, day in enumerate(WEEKDAYS)}
        unit_columns = [day for day in WEEKDAYS if day in timetable.columns]
        unit_lookup = timetable.set_index("course_code") if not timetable.empty else pd.DataFrame()
        future_by_course: dict[str, int] = {}
        for code in attendance["course_code"].astype(str):
            units = unit_lookup.loc[code] if not timetable.empty and code in unit_lookup.index else None
            future_by_course[code] = int(sum(float(units.get(day, 0) or 0) * day_counts[day] for day in unit_columns)) if units is not None else 0
        attendance["remaining"] = attendance["course_code"].astype(str).map(future_by_course).fillna(0).astype(int)
        api_dashboard = None
        if st.session_state.get("data_verified") and st.session_state.get("student_id"):
            try:
                api_dashboard = api_call("GET", f"/api/student/{st.session_state.student_id}/dashboard")
            except (RuntimeError, requests.RequestException) as exc:
                st.error(f"Could not refresh the saved dashboard: {exc}")
        if api_dashboard:
            aggregate = api_dashboard["aggregate"]
            aggregate_pct = aggregate["current_pct"]
            aggregate_slabs = [{
                "Target": f"{target}% · {details['marks']} marks",
                "Attend (strict)": details["must_attend"],
                "Can miss": details["can_miss"],
                "Reachable": "Yes" if details["is_reachable"] else "No",
                "Rounded threshold": details["rounded_required"],
            } for target, details in aggregate["slabs"].items()]
            aggregate_remaining = aggregate["remaining_classes"]
            aggregate_75 = aggregate["slabs"]["75"]["can_miss"]
            aggregate_85 = aggregate["slabs"]["85"]["can_miss"]
            remaining_teaching_day_count = aggregate["remaining_teaching_days"]
            display_courses = api_dashboard["courses"]
        else:
            total_delivered = int(attendance["total_delivered"].sum())
            total_attended = int(attendance["attended_effective"].sum())
            aggregate_pct = rounded_percent(total_attended, total_delivered)
            aggregate_remaining = int(attendance["remaining"].sum())
            aggregate_slabs = slab_rows(total_attended, total_delivered, aggregate_remaining)
            aggregate_75 = next(row["Can miss"] for row in aggregate_slabs if row["Target"].startswith("75%"))
            aggregate_85 = next(row["Can miss"] for row in aggregate_slabs if row["Target"].startswith("85%"))
            remaining_teaching_day_count = len(future_days)
            display_courses = []
            for _, course in attendance.iterrows():
                row = course.to_dict()
                row.update({"counted_attended": int(course["attended_effective"]), "current_pct": rounded_percent(int(course["attended_effective"]), int(course["total_delivered"])), "current_marks": marks_for(rounded_percent(int(course["attended_effective"]), int(course["total_delivered"]))), "remaining_classes": int(course["remaining"])})
                row["slabs"] = {str(target): {"marks": item["Target"], "must_attend": item["Attend (strict)"], "can_miss": item["Can miss"], "is_reachable": item["Reachable"] == "Yes", "rounded_required": item["Rounded threshold"]} for target, item in zip(TARGETS, slab_rows(row["counted_attended"], int(row["total_delivered"]), row["remaining_classes"]))}
                row["status_badge"] = "REAPPEAR" if row["current_pct"] < 75 else ("BORDERLINE" if row["current_pct"] < 85 else "SAFE")
                display_courses.append(row)

        st.subheader("Your semester at a glance")
        k1, k2, k3, k4 = st.columns(4)
        aggregate_marks = api_dashboard["aggregate"]["current_marks"] if api_dashboard else marks_for(aggregate_pct)
        k1.metric("Current overall attendance", f"{aggregate_pct}%", f"Attendance marks: {aggregate_marks} / 5")
        k2.metric("Remaining teaching days", remaining_teaching_day_count)
        k3.metric("Sessions you can miss · 85% target", aggregate_85)
        k4.metric("Sessions you can miss · 75% target", aggregate_75)
        if aggregate_pct < 75:
            st.error("Aggregate attendance is below 75%. You may be at risk of exam debarment.")

        st.subheader("Course breakdown")
        for course in display_courses:
            code = str(course["course_code"])
            delivered = int(course["total_delivered"])
            attended = int(course.get("counted_attended", int(course["total_attended"]) + int(course.get("duty_leave", 0)) + int(course.get("first_week_bonus", 0))))
            remaining = int(course.get("remaining_classes", course.get("remaining", 0)))
            pct = int(course.get("current_pct", rounded_percent(attended, delivered)))
            status_badge = str(course.get("status_badge", "SAFE"))
            status = "🔴 Reappear risk" if status_badge == "REAPPEAR" else ("🟠 Borderline" if status_badge == "BORDERLINE" or pct < 85 else "🟢 Safe")
            if api_dashboard:
                course_slabs = [{"Target": f"{target}% · {details['marks']} marks", "Attend (strict)": details["must_attend"], "Can miss": details["can_miss"], "Reachable": "Yes" if details["is_reachable"] else "No", "Rounded threshold": details["rounded_required"]} for target, details in course["slabs"].items()]
            else:
                course_slabs = slab_rows(attended, delivered, remaining)
            with st.container(border=True):
                title, stats = st.columns([2, 4])
                title.markdown(f"### {code}")
                title.caption(str(course.get("course_name", "")))
                marks = int(course.get("current_marks", marks_for(pct)))
                stats.markdown(f"**Current attendance: {pct}%** · Attendance marks: **{marks} / 5** · **{attended} of {delivered} class sessions counted** · **{remaining} class sessions remaining** · {status}")
                st.dataframe(readable_slab_table(course_slabs), hide_index=True, use_container_width=True)
                max_skip = max(0, remaining)
                skipped = st.slider(f"Skip upcoming class sessions · {code}", 0, max_skip, 0, key=f"skip_{code}") if max_skip else 0
                if api_dashboard and skipped:
                    try:
                        simulation = api_call("POST", f"/api/student/{st.session_state.student_id}/simulate", json={"extra_bunks_per_course": {code: skipped}})
                        simulated_course = next(item for item in simulation["courses"] if item["course_code"] == code)
                        projected = simulated_course["projected_pct"]
                        projected_marks = simulated_course["projected_marks"]
                        projected_status = "Reappear risk" if simulated_course["status_badge"] == "REAPPEAR" else f"{projected_marks} / 5 marks"
                    except (RuntimeError, requests.RequestException) as exc:
                        projected = rounded_percent(attended + remaining - skipped, delivered + remaining)
                        projected_status = f"{marks_for(projected)} / 5 marks"
                        st.caption(f"Simulation API unavailable: {exc}")
                else:
                    projected = rounded_percent(attended + remaining - skipped, delivered + remaining)
                    projected_status = "Reappear risk" if projected < 75 else f"{marks_for(projected)} / 5 marks"
                plan_text = f"Skip {skipped} class session{'s' if skipped != 1 else ''} and attend the rest" if skipped else "Attend all remaining class sessions"
                projection_message = f"{plan_text} → Projected attendance: {projected}% · Attendance marks: {projected_status}"
                if projected < 75:
                    st.error(projection_message)
                elif projected < 85:
                    st.warning(projection_message)
                else:
                    st.success(projection_message)

        st.caption("Session counts use your weekly timetable and the fixed semester calendar. Attendance targets use the strict percentage threshold for a safety buffer.")

st.divider()
st.caption("Uploads are stored in Azure Blob Storage and verified attendance data is saved in Azure SQL.")
