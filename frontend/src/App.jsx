import { useCallback, useEffect, useState } from "react";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const TARGETS = [90, 85, 80, 75];
const TOKEN_KEY = "attendance-saver-token";
const STUDENT_KEY = "attendance-saver-student";

async function api(path, { method = "GET", token, body, file, timeout = 60000 } = {}) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeout);
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload = body;
  if (file) {
    payload = new FormData();
    payload.append("file", file);
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  try {
    const response = await fetch(`${API_BASE}${path}`, { method, headers, body: payload, signal: controller.signal });
    const contentType = response.headers.get("content-type") || "";
    const result = contentType.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) {
      const detail = typeof result === "object" ? result.detail : result;
      throw new Error(detail || `Request failed (${response.status})`);
    }
    return result;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("The server took too long to respond. Check that the backend and Azure services are available, then try again.");
    if (error instanceof TypeError) throw new Error("Could not reach the API. Check that the backend is running and its URL is configured.");
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}

function blankTimetable() { return [{ course_code: "", ...Object.fromEntries(DAYS.map((day) => [day, 0])) }]; }
function blankAttendance() { return [{ course_code: "", course_name: "", total_delivered: 0, total_attended: 0, duty_leave: 0, first_week_bonus: 0 }]; }

function timetableGrid(slots) {
  const rows = new Map();
  for (const slot of slots || []) {
    const code = String(slot.course_code || "").trim();
    if (!code) continue;
    if (!rows.has(code)) rows.set(code, { course_code: code, ...Object.fromEntries(DAYS.map((day) => [day, 0])) });
    if (DAYS.includes(slot.day_of_week)) rows.get(code)[slot.day_of_week] += Number(slot.attendance_units || 0);
  }
  return rows.size ? [...rows.values()] : blankTimetable();
}

function pctMarks(pct) { return pct >= 90 ? 5 : pct >= 85 ? 4 : pct >= 80 ? 3 : pct >= 75 ? 2 : 0; }
function roundPercent(attended, delivered) { return delivered > 0 ? Math.min(100, Math.floor(attended * 100 / delivered + 0.5)) : 0; }
function showDate(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" }).format(new Date(`${value}T00:00:00`));
}

function Icon({ name, size = 20 }) {
  const common = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true };
  const paths = {
    dashboard: <><rect x="3" y="3" width="8" height="8" rx="1.5"/><rect x="13" y="3" width="8" height="5" rx="1.5"/><rect x="13" y="10" width="8" height="11" rx="1.5"/><rect x="3" y="13" width="8" height="8" rx="1.5"/></>,
    setup: <><path d="M12 3v18M3 12h18"/><circle cx="12" cy="12" r="9"/></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></>,
    upload: <><path d="M12 16V4m0 0L7 9m5-5 5 5"/><path d="M20 16.5v2a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-2"/></>,
    book: <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v17H6.5A2.5 2.5 0 0 0 4 22z"/><path d="M4 5.5v14A2.5 2.5 0 0 1 6.5 17H20M8 7h8M8 11h7"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    alert: <><path d="M12 9v4m0 4h.01"/><path d="M10.3 3.9 2.5 17.4A2 2 0 0 0 4.2 20h15.6a2 2 0 0 0 1.7-2.6L13.7 3.9a2 2 0 0 0-3.4 0Z"/></>,
    arrow: <><path d="M5 12h14M13 6l6 6-6 6"/></>,
    close: <><path d="m18 6-12 12M6 6l12 12"/></>,
    bars: <><path d="M4 6h16M4 12h16M4 18h16"/></>,
    sparkle: <><path d="m12 3 1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3Z"/><path d="m19 16 .7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7L19 16Z"/></>,
    help: <><circle cx="12" cy="12" r="9"/><path d="M9.6 9a2.5 2.5 0 1 1 4.6 1.3c-.8 1.1-2.2 1.4-2.2 3M12 17h.01"/></>,
  };
  return <svg {...common}>{paths[name] || paths.dashboard}</svg>;
}

function Brand() {
  return <div className="brand-lockup"><div className="brand-mark" aria-hidden="true"><span/><span/><span/></div><div><div className="brand-name">Attendance Saver</div><div className="brand-caption">Plan your semester with confidence</div></div></div>;
}

function App() {
  const [page, setPage] = useState("dashboard");
  const [menuOpen, setMenuOpen] = useState(false);
  const [token, setToken] = useState("");
  const [studentId, setStudentId] = useState("");
  const [profileReady, setProfileReady] = useState(false);
  const [backend, setBackend] = useState("checking");
  const [backendMessage, setBackendMessage] = useState("");
  const [timetable, setTimetable] = useState(blankTimetable());
  const [attendance, setAttendance] = useState(blankAttendance());
  const [timetableFile, setTimetableFile] = useState(null);
  const [attendanceFile, setAttendanceFile] = useState(null);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [verified, setVerified] = useState(false);
  const [dashboard, setDashboard] = useState(null);
  const [calendar, setCalendar] = useState(null);
  const [skips, setSkips] = useState({});
  const [projections, setProjections] = useState({});

  const reportError = (reason) => { setError(reason?.message || String(reason)); setMessage(""); };
  const clearNotice = () => { setError(""); setMessage(""); };

  const loadSavedData = useCallback(async (currentToken, currentStudent) => {
    try {
      const result = await api(`/api/student/${currentStudent}/data`, { token: currentToken, timeout: 20000 });
      const grid = timetableGrid(result.timetable_slots);
      const rows = result.attendance_records?.length ? result.attendance_records.map((row) => ({ ...row })) : blankAttendance();
      setTimetable(grid);
      setAttendance(rows);
      const isReady = Boolean(result.timetable_slots?.length && result.attendance_records?.length);
      setVerified(isReady);
      if (isReady) {
        const data = await api(`/api/student/${currentStudent}/dashboard`, { token: currentToken, timeout: 20000 });
        setDashboard(data);
      } else setDashboard(null);
    } catch (reason) {
      reportError(reason);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        api("/health", { timeout: 5000 }).then(() => !cancelled && setBackend("online")).catch((reason) => {
          if (!cancelled) { setBackend("offline"); setBackendMessage(reason.message); }
        });
        let currentToken = localStorage.getItem(TOKEN_KEY) || "";
        let currentStudent = localStorage.getItem(STUDENT_KEY) || "";
        if (currentToken && currentStudent) {
          try { await api("/api/auth/me", { token: currentToken, timeout: 12000 }); }
          catch { currentToken = ""; currentStudent = ""; }
        }
        if (!currentToken) {
          const profile = await api("/api/auth/guest", { method: "POST", timeout: 20000 });
          currentToken = profile.access_token;
          currentStudent = profile.student_id;
          localStorage.setItem(TOKEN_KEY, currentToken);
          localStorage.setItem(STUDENT_KEY, currentStudent);
        }
        if (cancelled) return;
        setToken(currentToken);
        setStudentId(currentStudent);
        setProfileReady(true);
        await loadSavedData(currentToken, currentStudent);
      } catch (reason) {
        if (!cancelled) { reportError(reason); setProfileReady(true); }
      }
    })();
    return () => { cancelled = true; };
  }, [loadSavedData]);

  useEffect(() => {
    if (!token) return;
    api("/api/admin/calendar", { token, timeout: 12000 }).then(setCalendar).catch(() => {});
  }, [token]);

  const saveRows = async (nextTimetable = timetable, nextAttendance = attendance) => {
    if (!token || !studentId) throw new Error("Your profile is not ready yet. Please wait a moment and try again.");
    const timetableSlots = [];
    for (const row of nextTimetable) {
      const code = String(row.course_code || "").trim().toUpperCase();
      if (!code) continue;
      for (const day of DAYS) {
        const units = Math.max(0, Math.floor(Number(row[day]) || 0));
        if (units) timetableSlots.push({ course_code: code, day_of_week: day, time_slot: "Weekly total", class_type: "L", attendance_units: units });
      }
    }
    const attendanceRecords = nextAttendance.flatMap((row) => {
      const code = String(row.course_code || "").trim().toUpperCase();
      if (!code) return [];
      const delivered = Math.max(0, Math.floor(Number(row.total_delivered) || 0));
      return [{
        course_code: code, course_name: String(row.course_name || "").trim(), total_delivered: delivered,
        total_attended: Math.min(delivered, Math.max(0, Math.floor(Number(row.total_attended) || 0))),
        duty_leave: Math.max(0, Math.floor(Number(row.duty_leave) || 0)),
        first_week_bonus: Math.max(0, Math.floor(Number(row.first_week_bonus) || 0)), reported_percentage: 0,
      }];
    });
    await api(`/api/student/${studentId}/verify-data`, { method: "PUT", token, body: { timetable_slots: timetableSlots, attendance_records: attendanceRecords } });
    setVerified(Boolean(timetableSlots.length && attendanceRecords.length));
    if (timetableSlots.length && attendanceRecords.length) {
      const result = await api(`/api/student/${studentId}/dashboard`, { token, timeout: 20000 });
      setDashboard(result);
    } else setDashboard(null);
  };

  const changeTimetable = (index, key, value) => setTimetable((rows) => rows.map((row, i) => i === index ? { ...row, [key]: value } : row));
  const changeAttendance = (index, key, value) => setAttendance((rows) => rows.map((row, i) => i === index ? { ...row, [key]: value } : row));

  const uploadTimetable = async () => {
    if (!timetableFile) return reportError(new Error("Choose a Schedule.xlsx file first."));
    clearNotice(); setBusy("timetable");
    try {
      const result = await api("/api/student/upload-timetable", { method: "POST", token, file: timetableFile, timeout: 120000 });
      const grid = timetableGrid(result.slots);
      setTimetable(grid); setVerified(false); setDashboard(null);
      setMessage(`Read ${result.slots.length} timetable entries across ${grid.length} courses. Review the grid, then save both tables.`);
    } catch (reason) { reportError(reason); }
    finally { setBusy(""); }
  };

  const uploadAttendance = async () => {
    if (!attendanceFile) return reportError(new Error("Choose an attendance summary image first."));
    clearNotice(); setBusy("attendance");
    try {
      const result = await api("/api/student/upload-attendance", { method: "POST", token, file: attendanceFile, timeout: 120000 });
      setAttendance(result.rows); setVerified(false); setDashboard(null);
      setMessage(`Read ${result.rows.length} course rows. Review the figures, then save both tables.`);
    } catch (reason) { reportError(reason); }
    finally { setBusy(""); }
  };

  const verifyData = async () => {
    clearNotice(); setBusy("save");
    try {
      await saveRows();
      setMessage("Your timetable and attendance figures are saved. Your dashboard is ready.");
      setPage("dashboard");
    } catch (reason) { reportError(reason); }
    finally { setBusy(""); }
  };

  const runSimulation = (courseCode, requestedCount) => {
    const course = dashboard?.courses?.find((item) => item.course_code === courseCode);
    const count = Math.max(0, Math.min(Number(requestedCount) || 0, course?.remaining_classes || 0));
    setSkips((current) => ({ ...current, [courseCode]: count }));
    if (!course || count === 0) {
      setProjections((current) => ({ ...current, [courseCode]: null }));
      return;
    }

    // The dashboard already contains the Azure-backed totals. Recalculate this
    // what-if locally so dragging the slider doesn't wait for a SQL round trip.
    const projectedPct = roundPercent(
      course.counted_attended + course.remaining_classes - count,
      course.total_delivered + course.remaining_classes,
    );
    setProjections((current) => ({
      ...current,
      [courseCode]: {
        course_code: courseCode,
        skipped_classes: count,
        projected_pct: projectedPct,
        projected_marks: pctMarks(projectedPct),
        status_badge: projectedPct < 75 ? "REAPPEAR" : projectedPct < 85 ? "BORDERLINE" : "SAFE",
      },
    }));
  };

  const nav = [
    { id: "dashboard", label: "Dashboard", icon: "dashboard" },
    { id: "setup", label: "Set up data", icon: "setup" },
    { id: "calendar", label: "Session calendar", icon: "calendar" },
  ];
  const activeTitle = nav.find((item) => item.id === page)?.label || "Dashboard";
  const courses = dashboard?.courses || [];
  const aggregate = dashboard?.aggregate;

  return (
    <div className="app-shell">
      <div className="notice-strip"><span className="notice-chevron">‹‹</span><span><Icon name="sparkle" size={16}/> A clearer view of your attendance starts here.</span><span className="notice-chevron">››</span></div>
      <header className="topbar">
        <button className="mobile-menu" aria-label="Open navigation" onClick={() => setMenuOpen((open) => !open)}><Icon name={menuOpen ? "close" : "bars"} size={23}/></button>
        <Brand />
        <div className="topbar-right"><span className={`connection-dot ${backend}`}/><span className="connection-label">{backend === "online" ? "Backend connected" : backend === "checking" ? "Connecting…" : "Connection issue"}</span><div className="profile-chip"><span className="profile-avatar">S</span><span>Student workspace</span></div></div>
      </header>

      <div className="layout">
        <aside className={`sidebar ${menuOpen ? "is-open" : ""}`}>
          <div className="sidebar-intro"><span className="eyebrow">ODD SEMESTER · 2026</span><h2>Your attendance,<br/>at a glance.</h2><p>Know where you stand and plan the sessions ahead.</p></div>
          <nav className="side-nav" aria-label="Main navigation">
            {nav.map((item) => <button key={item.id} className={`nav-item ${page === item.id ? "active" : ""}`} onClick={() => { setPage(item.id); setMenuOpen(false); }}><Icon name={item.icon}/><span>{item.label}</span>{page === item.id && <span className="nav-active-mark"/>}</button>)}
          </nav>
          <div className="calendar-mini"><div className="mini-label"><Icon name="calendar" size={17}/> Fixed semester</div><strong>Aug 10 – Dec 11</strong><span>Today · Nov 23, 2026</span><span>Mid-term tests · Oct 12–17</span><button onClick={() => { setPage("calendar"); setMenuOpen(false); }}>View calendar <Icon name="arrow" size={15}/></button></div>
          <div className="sidebar-footer"><span className={`status-pip ${backend}`}/><span>{backend === "online" ? "All systems ready" : backend === "checking" ? "Checking services" : "Check your connection"}</span></div>
        </aside>

        <main className="main-content">
          <div className="page-heading"><div><span className="eyebrow">ATTENDANCE SAVER <span className="crumb">/</span> {activeTitle.toUpperCase()}</span><h1>{page === "setup" ? "Set up your attendance" : page === "calendar" ? "Your semester calendar" : "Welcome to your dashboard"}</h1><p>{page === "setup" ? "Add your timetable and current attendance to get a personal plan." : page === "calendar" ? "The fixed dates used to calculate your remaining class sessions." : "See your current standing and how many sessions you can safely miss."}</p></div><span className="heading-badge"><Icon name={page === "setup" ? "upload" : page === "calendar" ? "calendar" : "book"} size={19}/></span></div>

          {(error || (backend === "offline" && !error)) && <div className="alert alert-error"><Icon name="alert"/><div><strong>{error ? "We couldn’t complete that request" : "Backend connection unavailable"}<span className="alert-dismiss" onClick={clearNotice} role="button" aria-label="Dismiss">×</span></strong><p>{error || backendMessage || "The app cannot reach the API. Check the backend address and try again."}</p></div></div>}
          {message && <div className="alert alert-success"><Icon name="check"/><div><strong>Done</strong><p>{message}</p></div><button className="alert-dismiss" onClick={() => setMessage("")} aria-label="Dismiss">×</button></div>}

          {page === "dashboard" && <DashboardView aggregate={aggregate} courses={courses} dashboard={dashboard} profileReady={profileReady} backend={backend} skips={skips} projections={projections} onSkip={runSimulation} onSetup={() => setPage("setup")}/>}
          {page === "setup" && <SetupView timetable={timetable} attendance={attendance} timetableFile={timetableFile} attendanceFile={attendanceFile} busy={busy} calendar={calendar} onTimetableFile={setTimetableFile} onAttendanceFile={setAttendanceFile} onUploadTimetable={uploadTimetable} onUploadAttendance={uploadAttendance} onTimetableChange={changeTimetable} onAttendanceChange={changeAttendance} onAddTimetable={() => setTimetable((rows) => [...rows, { course_code: "", ...Object.fromEntries(DAYS.map((day) => [day, 0])) }])} onAddAttendance={() => setAttendance((rows) => [...rows, { course_code: "", course_name: "", total_delivered: 0, total_attended: 0, duty_leave: 0, first_week_bonus: 0 }])} onRemoveTimetable={(index) => setTimetable((rows) => rows.filter((_, i) => i !== index))} onRemoveAttendance={(index) => setAttendance((rows) => rows.filter((_, i) => i !== index))} onVerify={verifyData}/>}
          {page === "calendar" && <CalendarView calendar={calendar} onSetup={() => setPage("setup")}/>}

          <footer className="page-footer"><span>Attendance Saver · Odd Semester 2026</span><span>Uploads go to Azure Blob Storage · Verified figures are saved in Azure SQL</span></footer>
        </main>
      </div>
    </div>
  );
}

function DashboardView({ aggregate, courses, dashboard, profileReady, backend, skips, projections, onSkip, onSetup }) {
  if (!profileReady) return <div className="empty-state loading-state"><div className="loader"/><h2>Opening your student workspace</h2><p>Connecting to the attendance service…</p></div>;
  if (!aggregate || !courses.length) return <div className="empty-state"><div className="empty-icon"><Icon name="book" size={28}/></div><span className="eyebrow">YOUR PERSONAL ATTENDANCE PLAN</span><h2>Your dashboard is ready when your data is</h2><p>Upload a weekly timetable and attendance summary. Your course breakdown and safe-miss plan will appear here once both are saved.</p><button className="button button-primary" onClick={onSetup}>Set up my data <Icon name="arrow" size={17}/></button><div className="empty-steps"><span><b>01</b> Add timetable</span><span><b>02</b> Add attendance</span><span><b>03</b> Review your plan</span></div></div>;
  const statusText = aggregate.current_pct < 75 ? "Reappear risk" : aggregate.current_pct < 85 ? "Needs attention" : "On track";
  return <>
    {backend !== "online" && <div className="inline-status"><span className="status-pip checking"/> Dashboard data is saved. Live connection status is being checked.</div>}
    <section className="section-block"><div className="section-title"><div><span className="eyebrow">ODD SEMESTER · AUG–DEC 2026</span><h2>Your semester at a glance</h2></div><span className={`status-pill ${aggregate.current_pct < 75 ? "danger" : aggregate.current_pct < 85 ? "warning" : "good"}`}><span/> {statusText}</span></div>
      <div className="metrics-grid">
        <article className="metric-card metric-primary"><div className="metric-top"><span>Current overall attendance</span><span className="metric-icon"><Icon name="dashboard" size={17}/></span></div><strong>{aggregate.current_pct}%</strong><div className="metric-bottom"><span className="marks-tag">Attendance marks · {aggregate.current_marks} / 5</span><span>{aggregate.total_attended} of {aggregate.total_delivered} counted</span></div><div className="metric-progress"><span style={{ width: `${Math.min(100, aggregate.current_pct)}%` }}/></div></article>
        <article className="metric-card"><div className="metric-top"><span>Remaining teaching days</span><span className="metric-icon"><Icon name="calendar" size={17}/></span></div><strong>{aggregate.remaining_teaching_days}</strong><div className="metric-bottom"><span>Until Dec 11, 2026</span></div></article>
        <article className="metric-card"><div className="metric-top"><span>Sessions you can miss</span><span className="target-tag">85% target</span></div><strong>{aggregate.slabs["85"]?.can_miss ?? 0}</strong><div className="metric-bottom"><span>Keep at least 4 / 5 marks</span></div></article>
        <article className="metric-card"><div className="metric-top"><span>Sessions you can miss</span><span className="target-tag target-soft">75% target</span></div><strong>{aggregate.slabs["75"]?.can_miss ?? 0}</strong><div className="metric-bottom"><span>Minimum exam eligibility target</span></div></article>
      </div>
    </section>
    <section className="section-block course-section"><div className="section-title"><div><span className="eyebrow">YOUR SUBJECTS</span><h2>Course breakdown</h2></div><span className="course-count">{courses.length} courses</span></div>
      <div className="course-list">{courses.map((course) => <CourseCard key={course.course_code} course={course} skip={skips[course.course_code] || 0} projection={projections[course.course_code]} onSkip={(value) => onSkip(course.course_code, Number(value))}/>)}</div>
    </section>
    <div className="dashboard-note"><Icon name="sparkle" size={18}/><div><strong>Your attendance plan updates with your inputs</strong><span>Future sessions are estimated from your weekly timetable and the fixed semester calendar.</span></div><button className="button button-quiet" onClick={onSetup}>Edit my data <Icon name="arrow" size={15}/></button></div>
  </>;
}

function CourseCard({ course, skip, projection, onSkip }) {
  const [expanded, setExpanded] = useState(true);
  const risky = course.current_pct < 75;
  const warning = course.current_pct >= 75 && course.current_pct < 85;
  const label = risky ? "Reappear risk" : warning ? "Borderline" : "Safe";
  const projectedIfAll = roundPercent(course.counted_attended + course.remaining_classes, course.total_delivered + course.remaining_classes);
  return <article className="course-card">
    <div className="course-head"><div className="course-title"><div className="course-avatar">{course.course_code.slice(0, 2)}</div><div><h3>{course.course_code}</h3><p>{course.course_name || "Course attendance"}</p></div></div><div className="course-current"><div className="course-current-percent"><span>Current attendance</span><strong>{course.current_pct}%</strong></div><div className="course-meta"><span>Attendance marks <b>{course.current_marks} / 5</b></span><span>{course.counted_attended} of {course.total_delivered} class sessions counted</span><span>{course.remaining_classes} class sessions remaining</span></div><span className={`status-pill ${risky ? "danger" : warning ? "warning" : "good"}`}><span/>{label}</span></div></div>
    {expanded && <><div className="course-table-wrap"><table className="plan-table"><thead><tr><th>Target and attendance marks</th><th>Sessions to attend</th><th>Sessions you can miss</th><th>Can reach target?</th></tr></thead><tbody>{TARGETS.map((target) => { const plan = course.slabs[String(target)]; return <tr key={target}><td><strong>{target}%</strong><span className="table-mark"> · {plan?.marks} marks</span></td><td>{plan?.must_attend ?? "—"}</td><td>{plan?.can_miss ?? "—"}</td><td><span className={`reachability ${plan?.is_reachable ? "reachable" : "unreachable"}`}><span/>{plan?.is_reachable ? "Yes" : "No"}</span></td></tr>; })}</tbody></table></div>
    <div className="simulator"><div className="simulator-head"><div><span className="eyebrow">WHAT-IF PLANNER</span><strong>Skip upcoming class sessions</strong></div><span className="skip-count">{skip} <small>skipped</small></span></div><input aria-label={`Number of upcoming sessions to skip for ${course.course_code}`} type="range" min="0" max={Math.max(1, course.remaining_classes)} value={Math.min(skip, Math.max(1, course.remaining_classes))} onChange={(event) => onSkip(event.target.value)} style={{ "--range-fill": `${Math.min(100, skip / Math.max(1, course.remaining_classes) * 100)}%` }}/><div className="range-labels"><span>Attend all</span><span>Skip up to {course.remaining_classes}</span></div><div className={`projection ${projection ? (projection.status_badge === "REAPPEAR" ? "projection-danger" : projection.status_badge === "BORDERLINE" ? "projection-warn" : "projection-good") : ""}`}><span className="projection-dot"/><span>{projection ? <>With this plan, projected attendance is <b>{projection.projected_pct}%</b> · Attendance marks <b>{projection.projected_marks} / 5</b>{projection.status_badge === "REAPPEAR" ? " · Reappear risk" : ""}</> : <>If you attend every remaining class session, projected attendance is <b>{projectedIfAll}% ({pctMarks(projectedIfAll)} / 5 marks)</b>.</>}</span></div></div></>}
    <button className="course-expand" onClick={() => setExpanded((value) => !value)} aria-expanded={expanded}>{expanded ? "Hide course plan" : "Show course plan"}<span>{expanded ? "−" : "+"}</span></button>
    {!expanded && null}
  </article>;
}

function FileHelpModal({ topic, onClose }) {
  const isTimetable = topic === "timetable";
  const title = isTimetable ? "Download your weekly timetable" : "Save your attendance summary";
  const steps = isTimetable
    ? [
        ["Open My Time Table", "Sign in to UMS and select the Time Table button on a course card."],
        ["Click Get Excel", "On the timetable page, use the blue Get Excel button near the upper-left corner."],
        ["Upload the workbook", "Save the downloaded .xlsx file, return here, and choose it in the Timetable card."],
      ]
    : [
        ["Open the attendance summary", "On My Courses, click the small info button beside ATTENDANCE at the bottom of the card."],
        ["Check the summary table", "The Student Attendance window opens. Keep the Attendance Summary tab selected and show the full table."],
        ["Save and upload a screenshot", "Capture the full table as PNG or JPG, then choose it in the Attendance summary card here."],
      ];
  return <div className="help-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="help-modal" role="dialog" aria-modal="true" aria-labelledby="file-help-title">
      <header className="help-modal-header"><div><span className="eyebrow">FILE DOWNLOAD GUIDE</span><h2 id="file-help-title">{title}</h2><p>Follow the screenshots from your UMS student portal.</p></div><button className="help-modal-close" onClick={onClose} aria-label="Close guide">×</button></header>
      <div className="help-modal-content">
        <div className="help-screenshots">{isTimetable ? <figure className="help-shot"><span className="help-shot-number">Screenshot 1 · Find Get Excel</span><img src="/help/timetable-excel-redacted.jpg" alt="UMS timetable page with the Get Excel button highlighted; schedule details blurred"/><figcaption>Click <b>Time Table</b> on a course, then click the highlighted <b>Get Excel</b> button.</figcaption></figure> : <><figure className="help-shot"><span className="help-shot-number">Screenshot 1 · Open attendance</span><img src="/help/attendance-info-redacted.jpg" alt="UMS My Courses card with the attendance information icon highlighted and personal details blurred"/><figcaption>On <b>My Courses</b>, click the info icon beside <b>ATTENDANCE</b>.</figcaption></figure><figure className="help-shot"><span className="help-shot-number">Screenshot 2 · Capture the summary</span><img src="/help/attendance-summary-redacted.jpg" alt="Student Attendance summary window with private course rows and values blurred"/><figcaption>Keep <b>Attendance Summary</b> selected and capture the complete table.</figcaption></figure></>}</div>
        <ol className="help-steps">{steps.map(([heading, detail], index) => <li key={heading}><span className="help-step-number">{index + 1}</span><div><strong>{heading}</strong><p>{detail}</p></div></li>)}</ol>
      </div>
      <div className="help-modal-note"><Icon name="help" size={17}/><span>Personal course, classroom, roll number, and attendance details are blurred in these guide screenshots. If you can’t get a file, use the editable tables instead.</span></div>
      <footer className="help-modal-footer"><span>Accepted file: <b>{isTimetable ? ".xlsx" : ".png or .jpg"}</b></span><button className="button button-primary" onClick={onClose}>Got it</button></footer>
    </section>
  </div>;
}

function UploadCard({ title, description, accept, file, onFile, onUpload, busy, icon, onHelp }) {
  const acceptFile = (candidate) => {
    if (!candidate) return;
    const isValid = accept.includes("xlsx") ? candidate.name.toLowerCase().endsWith(".xlsx") : candidate.type.startsWith("image/");
    if (isValid) onFile(candidate);
  };
  return <section className="upload-card"><div className="upload-card-title"><span className="upload-icon"><Icon name={icon}/></span><div className="upload-card-copy"><h3>{title}</h3><p>{description}</p></div><button type="button" className="file-help-button" onClick={onHelp}><Icon name="help" size={15}/> How to get this file?</button></div><label className={`dropzone ${file ? "has-file" : ""}`} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); acceptFile(event.dataTransfer.files?.[0]); }}><input type="file" accept={accept} onChange={(event) => acceptFile(event.target.files?.[0])}/><span className="drop-icon"><Icon name="upload" size={24}/></span><span className="drop-copy"><strong>{file ? file.name : "Choose a file or drag it here"}</strong><small>{accept.includes("xlsx") ? "Excel workbook · .xlsx" : "Image file · PNG or JPG"}</small></span><span className="browse-button">Browse</span></label>{file && <button className="remove-file" onClick={() => onFile(null)}><Icon name="close" size={15}/> Remove selected file</button>}<button className="button button-primary upload-action" disabled={!file || busy} onClick={onUpload}>{busy ? <><span className="button-spinner"/> Working…</> : <> {title.includes("Timetable") ? "Parse timetable" : "Read attendance with AI"}<Icon name="arrow" size={17}/></>}</button></section>;
}

function SetupView({ timetable, attendance, timetableFile, attendanceFile, busy, calendar, onTimetableFile, onAttendanceFile, onUploadTimetable, onUploadAttendance, onTimetableChange, onAttendanceChange, onAddTimetable, onAddAttendance, onRemoveTimetable, onRemoveAttendance, onVerify }) {
  const [calendarImage, setCalendarImage] = useState(false);
  const [helpTopic, setHelpTopic] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  useEffect(() => {
    if (!helpTopic) return undefined;
    const closeOnEscape = (event) => { if (event.key === "Escape") setHelpTopic(null); };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [helpTopic]);
  useEffect(() => {
    if (!attendanceFile) { setPreviewUrl(""); return undefined; }
    const url = URL.createObjectURL(attendanceFile);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [attendanceFile]);
  return <>
    <div className="setup-grid">
      <div className="setup-column"><UploadCard title="Timetable" description="Upload your weekly schedule. A two-hour practical counts as two class sessions." accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" file={timetableFile} onFile={onTimetableFile} onUpload={onUploadTimetable} busy={busy === "timetable"} icon="calendar" onHelp={() => setHelpTopic("timetable")}/><EditableTimetable rows={timetable} onChange={onTimetableChange} onAdd={onAddTimetable} onRemove={onRemoveTimetable}/></div>
      <div className="setup-column"><UploadCard title="Attendance summary" description="Upload a screenshot to read course attendance, or enter the figures below." accept="image/png,image/jpeg,.png,.jpg,.jpeg" file={attendanceFile} onFile={onAttendanceFile} onUpload={onUploadAttendance} busy={busy === "attendance"} icon="book" onHelp={() => setHelpTopic("attendance")}/>{attendanceFile && <div className="file-preview"><img src={previewUrl} alt="Selected attendance summary preview"/><span>Selected attendance summary</span></div>}<EditableAttendance rows={attendance} onChange={onAttendanceChange} onAdd={onAddAttendance} onRemove={onRemoveAttendance}/></div>
    </div>
    {helpTopic && <FileHelpModal topic={helpTopic} onClose={() => setHelpTopic(null)}/>}
    <section className="calendar-panel"><div className="calendar-panel-copy"><div className="calendar-icon"><Icon name="calendar" size={23}/></div><div><span className="eyebrow">FIXED PROJECT CALENDAR</span><h3>{calendar?.session_name || "Odd Semester Aug–Dec 2026"}</h3><p>{showDate(calendar?.start_date || "2026-08-10")} – {showDate(calendar?.end_date || "2026-12-11")} · Today {showDate(calendar?.reference_today || "2026-11-23")}</p></div></div><div className="calendar-panel-actions"><span className="calendar-note">Sundays, holidays, and mid-term test dates are excluded from teaching sessions.</span><button className="button button-quiet" onClick={() => setCalendarImage((value) => !value)}>{calendarImage ? "Hide calendar" : "View calendar"}</button></div>{calendarImage && <CalendarImage/>}</section>
    <div className="save-bar"><div><strong>Ready to see your attendance plan?</strong><span>Review your figures, then save both tables to your profile.</span></div><button className="button button-primary" disabled={busy === "save"} onClick={onVerify}>{busy === "save" ? <><span className="button-spinner"/> Saving…</> : <>Save and view dashboard <Icon name="arrow" size={17}/></>}</button></div>
  </>;
}

function EditableTimetable({ rows, onChange, onAdd, onRemove }) {
  return <section className="data-card"><div className="data-card-head"><div><span className="eyebrow">WEEKLY CLASSES</span><h3>Review your timetable</h3></div><button className="add-row" onClick={onAdd}>＋ Add course</button></div><div className="editable-wrap"><table className="editable-table timetable-table"><thead><tr><th>Course code</th>{DAYS.map((day) => <th key={day}>{day.slice(0, 3)}</th>)}<th aria-label="Actions"/></tr></thead><tbody>{rows.map((row, index) => <tr key={`tt-${index}`}><td><input aria-label="Course code" value={row.course_code} placeholder="CSB204" onChange={(event) => onChange(index, "course_code", event.target.value)}/></td>{DAYS.map((day) => <td key={day}><input aria-label={`${day} sessions`} type="number" min="0" max="20" value={row[day] ?? 0} onChange={(event) => onChange(index, day, event.target.value)}/></td>)}<td><button className="icon-button" aria-label="Remove course" onClick={() => onRemove(index)}><Icon name="close" size={16}/></button></td></tr>)}</tbody></table></div><p className="table-help">Enter the number of class sessions for each weekday. Leave days with no class at 0.</p></section>;
}

function EditableAttendance({ rows, onChange, onAdd, onRemove }) {
  const cols = [["total_delivered", "Delivered"], ["total_attended", "Attended"], ["duty_leave", "Duty leave"], ["first_week_bonus", "Bonus"]];
  return <section className="data-card attendance-editor"><div className="data-card-head"><div><span className="eyebrow">CURRENT COURSE FIGURES</span><h3>Review attendance</h3></div><button className="add-row" onClick={onAdd}>＋ Add course</button></div><div className="editable-wrap"><table className="editable-table attendance-table"><thead><tr><th>Course code</th><th>Course name</th>{cols.map(([, label]) => <th key={label}>{label}</th>)}<th aria-label="Actions"/></tr></thead><tbody>{rows.map((row, index) => <tr key={`att-${index}`}><td><input aria-label="Course code" value={row.course_code} placeholder="CSB204" onChange={(event) => onChange(index, "course_code", event.target.value)}/></td><td><input aria-label="Course name" value={row.course_name} placeholder="Course name" onChange={(event) => onChange(index, "course_name", event.target.value)}/></td>{cols.map(([key, label]) => <td key={key}><input aria-label={label} type="number" min="0" value={row[key] ?? 0} onChange={(event) => onChange(index, key, event.target.value)}/></td>)}<td><button className="icon-button" aria-label="Remove course" onClick={() => onRemove(index)}><Icon name="close" size={16}/></button></td></tr>)}</tbody></table></div><p className="table-help">Duty leave and first-week bonus are included in your counted attendance.</p></section>;
}

function CalendarImage() {
  return <div className="calendar-image"><img src="/Session_Calendar.png" alt="Fixed semester session calendar" onError={(event) => { event.currentTarget.style.display = "none"; }}/><p>Calendar dates are fixed for this project and cannot be replaced by student uploads.</p></div>;
}

function CalendarView({ calendar, onSetup }) {
  const days = calendar?.days || [];
  const holidays = days.filter((day) => ["HOLIDAY", "MTT", "WEEKEND"].includes(day.day_type));
  const summary = calendar?.summary || {};
  return <div className="calendar-page-grid"><section className="calendar-detail-card"><div className="calendar-detail-head"><div className="calendar-icon"><Icon name="calendar" size={23}/></div><div><span className="eyebrow">FIXED SEMESTER</span><h2>{calendar?.session_name || "Odd Semester Aug–Dec 2026"}</h2><p>{showDate(calendar?.start_date || "2026-08-10")} — {showDate(calendar?.end_date || "2026-12-11")}</p></div></div><div className="calendar-stats"><div><strong>{summary.TEACHING ?? "—"}</strong><span>Teaching days</span></div><div><strong>{summary.HOLIDAY ?? "—"}</strong><span>Holidays</span></div><div><strong>{summary.MTT ?? 6}</strong><span>Test days</span></div><div><strong>{summary.WEEKEND ?? "—"}</strong><span>Weekend days</span></div></div><CalendarImage/></section><section className="calendar-dates-card"><div className="data-card-head"><div><span className="eyebrow">IMPORTANT DATES</span><h3>Holidays and test days</h3></div><span className="course-count">{holidays.length || 9} dates</span></div>{holidays.length ? <div className="date-list">{holidays.map((day) => <div className="date-row" key={day.date}><span className={`date-type ${day.day_type.toLowerCase()}`}>{day.day_type === "MTT" ? "MTT" : day.day_type === "WEEKEND" ? "SUN" : "OFF"}</span><div><strong>{showDate(day.date)}</strong><span>{day.day_of_week}{day.description ? ` · ${day.description}` : ""}</span></div><span className="date-excluded">No class sessions</span></div>)}</div> : <div className="date-list"><div className="date-row"><span className="date-type holiday">OFF</span><div><strong>15 Aug, 2026</strong><span>Independence Day</span></div><span className="date-excluded">No class sessions</span></div><div className="date-row"><span className="date-type mtt">MTT</span><div><strong>12–17 Oct, 2026</strong><span>Mid-term tests</span></div><span className="date-excluded">No class sessions</span></div><div className="date-row"><span className="date-type holiday">OFF</span><div><strong>24 Nov, 2026</strong><span>Holiday</span></div><span className="date-excluded">No class sessions</span></div></div>}<div className="calendar-info"><Icon name="alert" size={18}/><span>Only teaching days after Nov 23 and on or before Dec 11 count toward your remaining sessions.</span></div><button className="button button-primary" onClick={onSetup}>Continue to set up my data <Icon name="arrow" size={17}/></button></section></div>;
}

export default App;
