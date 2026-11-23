# AGENTS.md — Attendance Saver (Full-Stack Azure Project Blueprint)

## 1. Project Identity & Agent Objective

* **Project Name:** Attendance Saver
* **Objective:** Build a full-stack web application that predicts student attendance outcomes and internal assessment marks. The system ingests:
  1. **Fixed Project Calendar:** `sample_data/Session_Calendar.png` is the authoritative semester calendar. Students do not upload or change it.
  2. **Client/Student Side:** `Schedule.xlsx` (Weekly class timetable) and `Attendance_Summary.png` (Screenshot of current course-wise attendance).
* **Core Output:** For every enrolled course and for aggregate attendance, calculate the exact number of remaining classes a student **must attend** or **can safely miss** to hit target thresholds ($90\%$, $85\%$, $80\%$, and $75\%$), map those percentages to a $5$-mark internal grading slab, and warn if the student risks falling below $75\%$ (**Exam Debarment / Reappear**).
* **Agent Instruction:** Follow this specification strictly. Build modular, strongly typed code, write unit tests for all parsers and math engines, and ensure seamless integration with Microsoft Azure services.

---

## 2. Microsoft Azure Architecture & Tech Stack

### 2.1 Core Stack

* **Frontend (prototype):** Streamlit. Keep the interface in Python for rapid iteration; the UI can be replaced with React or another frontend later without changing the backend API.
* **Backend:** Python 3.11+ with FastAPI, Uvicorn, Pydantic v2.
* **Database (Mandatory):** **Azure SQL Database** (Serverless or General Purpose tier) accessed via `SQLAlchemy` + `pyodbc` (`ODBC Driver 18 for SQL Server`).

### 2.2 Required Azure Services & SDKs

1. **Azure SQL Database (`pyodbc`, `sqlalchemy`):**
   * Primary relational store for parsed academic calendars, holidays, student timetables, and extracted attendance summaries.
2. **Azure Blob Storage (`azure-storage-blob`):**
   * Stores student-uploaded files across two containers:
     * `student-timetables` (Client uploads of `Schedule.xlsx`)
     * `attendance-summaries` (Client uploads of `Attendance_Summary.png`)
3. **Azure AI Document Intelligence (`azure-ai-documentintelligence`):**
   * Uses the **`prebuilt-layout`** model to extract structured rows, columns, and cell text from `Attendance_Summary.png` with high tabular accuracy.
4. **Azure Communication Services SMS (`azure-communication-sms`):**
   * Sends one-time phone verification codes for account creation and sign-in. Sender availability and registration depend on the user's country; use Messaging Connect or another configured provider for destinations not supported by a direct ACS sender.
5. **Fixed Calendar Data:**
   * `calendar_parser.py` seeds the known dates and day types from the checked-in calendar image; no OCR service or calendar upload is needed.
6. **Azure App Service (Linux):**
   * Hosts the FastAPI backend API and Streamlit prototype as separate web apps or containers. The frontend calls the FastAPI API and can be replaced later.

### 2.3 Environment Variables (`.env.example`)

```env
# Azure SQL Database
AZURE_SQL_SERVER=your-server.database.windows.net
AZURE_SQL_DATABASE=AttendanceSaverDB
AZURE_SQL_USERNAME=sqladmin
AZURE_SQL_PASSWORD=YourStrongPassword123!
AZURE_SQL_DRIVER={ODBC Driver 18 for SQL Server}

# Azure Blob Storage
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net

# Azure AI Document Intelligence
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://your-doc-intel.cognitiveservices.azure.com/
AZURE_DOCUMENT_INTELLIGENCE_KEY=your_doc_intel_key

# Azure Communication Services SMS
AZURE_COMMUNICATION_SERVICES_CONNECTION_STRING=endpoint=...;accesskey=...
AZURE_COMMUNICATION_SMS_SENDER=+1...
OTP_SIGNING_SECRET=generate-a-random-secret-at-least-32-characters

```

---

## 3. Recommended Repository Structure

```text
Attendance_Saver/
├── AGENTS.md
├── frontend/
│   ├── streamlit_app.py             # Rapid-prototype upload, dashboard, and what-if UI
│   └── requirements.txt
├── requirements.txt                # Streamlit and Python app dependencies
├── README.md                       # Local prototype setup and Azure roadmap
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entry point & CORS config
│   │   ├── config.py                # Pydantic settings loading .env
│   │   ├── database.py              # Azure SQL SQLAlchemy engine & session
│   │   ├── models.py                # SQLAlchemy ORM models matching T-SQL schema
│   │   ├── schemas.py               # Pydantic request/response DTOs
│   │   ├── routers/
│   │   │   ├── admin.py             # Server-side calendar upload & management
│   │   │   ├── student.py           # Client timetable & attendance upload endpoints
│   │   │   └── analytics.py         # Slab calculations & What-If simulator endpoints
│   │   ├── services/
│   │   │   ├── blob_service.py      # Azure Blob Storage upload helper
│   │   │   ├── calendar_parser.py   # Fixed semester date and teaching-day data
│   │   │   ├── excel_parser.py      # openpyxl parser for Schedule.xlsx
│   │   │   ├── attendance_parser.py # Azure Document Intelligence for user attendance uploads
│   │   │   └── math_engine.py       # Core attendance & 5-mark slab calculator
│   ├── tests/
│   │   ├── test_math_engine.py      # Unit tests verified against sample course data
│   │   └── test_excel_parser.py     # Unit tests for merged-cell lab hours
│   └── requirements.txt
├── Dockerfile.backend
├── Dockerfile.streamlit
├── docker-compose.yml
└── sample_data/
    ├── Schedule.xlsx
    ├── Session_Calendar.png
    └── Attendance_Summary.png
```

---

## 4. Azure SQL Database Schema (T-SQL)

Execute the following T-SQL schema on **Azure SQL Database** during initialization:

```sql
-- 1. Academic Sessions (Seeded from the fixed project calendar)
CREATE TABLE AcademicSessions (
    session_id INT IDENTITY(1,1) PRIMARY KEY,
    session_name NVARCHAR(100) NOT NULL,          -- e.g., 'Odd Semester Aug-Dec 2026'
    start_date DATE NOT NULL,                     -- e.g., '2026-08-10'
    end_date DATE NOT NULL,                       -- e.g., '2026-12-11'
    reference_today DATE NOT NULL,                -- e.g., '2026-11-23' (from green box or system date)
    calendar_blob_url NVARCHAR(500) NULL,
    is_active BIT NOT NULL DEFAULT 1,
    created_at DATETIME2 DEFAULT SYSUTCDATETIME()
);

-- 2. Calendar Days Breakdown (Every date from start_date to end_date)
CREATE TABLE CalendarDays (
    day_id INT IDENTITY(1,1) PRIMARY KEY,
    session_id INT NOT NULL FOREIGN KEY REFERENCES AcademicSessions(session_id) ON DELETE CASCADE,
    calendar_date DATE NOT NULL,
    day_of_week NVARCHAR(15) NOT NULL,            -- 'Monday', 'Tuesday', ..., 'Sunday'
    day_type NVARCHAR(20) NOT NULL,               -- 'TEACHING', 'HOLIDAY', 'MTT', 'WEEKEND'
    description NVARCHAR(100) NULL,
    CONSTRAINT UQ_Session_Date UNIQUE (session_id, calendar_date)
);

-- 3. Student Profiles
CREATE TABLE StudentProfiles (
    student_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    student_name NVARCHAR(100) NULL,
    session_id INT NOT NULL FOREIGN KEY REFERENCES AcademicSessions(session_id),
    timetable_blob_url NVARCHAR(500) NULL,
    attendance_blob_url NVARCHAR(500) NULL,
    updated_at DATETIME2 DEFAULT SYSUTCDATETIME()
);

-- Phone number is the user-facing sign-in identity; UUID remains an internal database key.
CREATE TABLE StudentLogins (
    student_id UNIQUEIDENTIFIER PRIMARY KEY FOREIGN KEY REFERENCES StudentProfiles(student_id) ON DELETE CASCADE,
    phone_number NVARCHAR(20) NOT NULL UNIQUE,
    created_at DATETIME2 DEFAULT SYSUTCDATETIME()
);

CREATE TABLE OtpChallenges (
    challenge_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    phone_number NVARCHAR(20) NOT NULL,
    code_digest NVARCHAR(64) NOT NULL,
    created_at DATETIME2 DEFAULT SYSUTCDATETIME(),
    expires_at DATETIME2 NOT NULL,
    attempts INT NOT NULL DEFAULT 0,
    consumed BIT NOT NULL DEFAULT 0
);

-- 4. Student Weekly Timetable (Extracted from Schedule.xlsx)
CREATE TABLE TimetableSlots (
    slot_id INT IDENTITY(1,1) PRIMARY KEY,
    student_id UNIQUEIDENTIFIER NOT NULL FOREIGN KEY REFERENCES StudentProfiles(student_id) ON DELETE CASCADE,
    day_of_week NVARCHAR(15) NOT NULL,            -- 'Monday' through 'Saturday'
    time_slot NVARCHAR(30) NOT NULL,              -- e.g., '09-10 AM' or '10-12 PM'
    course_code NVARCHAR(20) NOT NULL,            -- e.g., 'CSB204'
    class_type NVARCHAR(15) NOT NULL,             -- 'L' (Lecture), 'T' (Tutorial), 'P' (Practical)
    attendance_units INT NOT NULL DEFAULT 1       -- 1 for 1-hr L/T, 2 for 2-hr merged Practical blocks
);

-- 5. Current Attendance Summary (Extracted from Attendance_Summary.png)
CREATE TABLE AttendanceRecords (
    record_id INT IDENTITY(1,1) PRIMARY KEY,
    student_id UNIQUEIDENTIFIER NOT NULL FOREIGN KEY REFERENCES StudentProfiles(student_id) ON DELETE CASCADE,
    course_code NVARCHAR(20) NOT NULL,            -- e.g., 'CSB204'
    course_name NVARCHAR(150) NOT NULL,           -- e.g., 'AZURE DATA FUNDAMENTALS'
    total_delivered INT NOT NULL,                 -- D
    total_attended INT NOT NULL,                  -- A_raw
    duty_leave INT NOT NULL DEFAULT 0,            -- DL
    first_week_bonus INT NOT NULL DEFAULT 0,      -- B
    reported_percentage INT NOT NULL              -- Rounded integer from summary sheet
);
```

---

## 5. Input File Specifications & Parsing Rules

### 5.1 Fixed Project Calendar: `sample_data/Session_Calendar.png`

* This calendar is checked into the project and is not an end-user upload. The API seeds its known dates at startup.

* **Visual Structure:** 18-week calendar grid (`Week 1 (Aug)` through `Week 18 (Dec)`), columns `Mon` to `Sun`.
* **Color-Coding Legend Rules:**
  * **Yellow/Orange Outline Box:** Marks `Commencement of Classes` (`Aug 10`) and final teaching day (`Dec 11`).
  * **Solid Green Box:** Marks `Today` (`Nov 23`). Note: Allow an API toggle to use either the calendar's green box date or `datetime.date.today()` (whichever is later/active).
  * **Red Outline Box:** Marks `Mid Term Test (MTT)` (`Oct 12` to `Oct 17`) $\rightarrow$ Classify as `day_type = 'MTT'` (0 regular classes).
  * **Solid Blue Box:** Marks `Holiday` (e.g., `Aug 15`, `Oct 2`, `Oct 20`, `Oct 26`, `Nov 7`, `Nov 8`, `Nov 9`, `Nov 10`, `Nov 24`) $\rightarrow$ Classify as `day_type = 'HOLIDAY'`.
  * **Sundays:** Always classify as `day_type = 'WEEKEND'`.
  * **All Other Dates within Start–End Range:** Classify as `day_type = 'TEACHING'`.

### 5.2 Client-Side: `Schedule.xlsx`

* **Parser Library:** Use `openpyxl` in Python (**do not use OCR** on `.xlsx` files).
* **Extraction Rules:**
  1. Locate the grid where rows/columns represent weekdays (`Monday` to `Saturday`) and hourly time slots (`09-10 AM`, `10-11 AM`, etc.).
  2. **Merged Cell Handling (CRITICAL):** Practical (`P`) classes span 2 consecutive hourly slots (e.g., `10-12 PM`). Inspect `sheet.merged_cells.ranges` in `openpyxl`. If a cell spans 2 time slots, record `attendance_units = 2` (since `Total Delivered (L,T,P)` in `Attendance_Summary.png` counts each hour of Lecture, Tutorial, and Practical as $1$ unit).
  3. **Regex Parsing:** Extract Course Code using `r"\b([A-Z]{3}\d{3})\b"` and Class Type (`Lecture` $\rightarrow$ `'L'`, `Tutorial` $\rightarrow$ `'T'`, `Practical` $\rightarrow$ `'P'`). Ignore empty cells or `"Lunch"` / `"Break"` cells.

### 5.3 Client-Side: `Attendance_Summary.png`

* **Parser Service:** **Azure AI Document Intelligence (`prebuilt-layout`)**.
* **Table Column Mapping:**
  * Column 0: `Course` $\rightarrow$ Split on `:` into `course_code` (trim) and `course_name` (trim).
  * Column 1: `Total Delivered (L,T,P)` $\rightarrow$ `total_delivered` (`int`)
  * Column 2: `Total Attended (L,T,P)` $\rightarrow$ `total_attended` (`int`)
  * Column 3: `Duty Leave` $\rightarrow$ `duty_leave` (`int`)
  * Column 4: `First week bonus (L,T,P)` $\rightarrow$ `first_week_bonus` (`int`)
  * Column 5: `Total Percentage` $\rightarrow$ `reported_percentage` (`int`)
* **Exclusion Rule:** Skip the bottom summary row starting with `* Aggregate Attendance` when saving individual course records (compute aggregate dynamically by summing across all courses).

---

## 6. Mathematical Engine & Marking Slab Specification

### 6.1 Definitions

For each course $i$:
* $D_i = \text{total\_delivered}$
* $A_i = \text{total\_attended} + \text{duty\_leave} + \text{first\_week\_bonus}$
* $R_i = \sum_{d \in \text{RemainingTeachingDays}} \text{ScheduledUnits}(i, \text{DayOfWeek}(d))$
  * Where $\text{RemainingTeachingDays}$ are all dates $d$ in `CalendarDays` such that $\text{reference\_today} < d \le \text{end\_date}$ AND $\text{day\_type} = \text{'TEACHING'}$.
* $T_i = D_i + R_i$ (Total classes delivered by the end of the semester).

### 6.2 Percentage & Rounding Rule

University attendance percentages are rounded to the nearest integer (standard half-up rounding, verified against sample data where $41 / 49 = 83.673\% \rightarrow 84\%$ and $53 / 60 = 88.333\% \rightarrow 88\%$):

$$P_{\text{current}} = \text{RoundHalfUp}\left(\frac{A_i}{D_i} \times 100\right)$$

Note: Cap $P$ at $100\%$ if $A_i > D_i$.

### 6.3 Internal Assessment Marking Slabs (Max 5 Marks)

Marks decrease by $1$ mark for every $5\%$ drop below $90\%$. Below $75\%$, the student is ineligible for exams (**Reappear**):

| Attendance Percentage ($P$) | Marks Awarded | Eligibility Status |
| :--- | :--- | :--- |
| $P \ge 90\%$ | $5 / 5$ | Safe (Maximum Marks) |
| $85\% \le P < 90\%$ | $4 / 5$ | Safe |
| $80\% \le P < 85\%$ | $3 / 5$ | Safe |
| $75\% \le P < 80\%$ | $2 / 5$ | Borderline Safe |
| $P < 75\%$ | $0 / 5$ | **Debarred / Reappear** |

### 6.4 Target Threshold Formulas

For each target threshold $X \in \{0.90, 0.85, 0.80, 0.75\}$:

1. **Minimum Total Classes Required by Semester End ($A_{\text{req}}$):**
   *(Accounting for nearest-integer rounding where $X - 0.005$ rounds up to $X \times 100\%$):*

   $$A_{\text{req}}(X) = \lceil (X - 0.005) \times (D_i + R_i) \rceil$$

   *(Note: Provide both exact strict threshold $\lceil X \times (D_i + R_i) \rceil$ and rounded threshold in API response; default UI to strict $\lceil X \times (D_i + R_i) \rceil$ as a safe buffer).*

2. **Future Classes Student Must Attend ($N_{\text{attend}}$):**

   $$N_{\text{attend}}(X) = \max\left(0, \; A_{\text{req}}(X) - A_i\right)$$

   * **Reachability Flag:** If $N_{\text{attend}}(X) > R_i$, mark slab $X$ as `is_reachable = false` (impossible to achieve even with $100\%$ attendance in remaining classes).

3. **Future Classes Student Can Afford to Miss ($N_{\text{miss}}$):**
   * If `is_reachable == false`: $N_{\text{miss}}(X) = 0$.
   * Otherwise:

   $$N_{\text{miss}}(X) = \max\left(0, \; R_i - N_{\text{attend}}(X)\right)$$

### 6.5 Verification Dataset (From `sample_data/Attendance_Summary.png`)

Use these exact values in `tests/test_math_engine.py`:
* `CSB204`: $D = 49, A = 41 \rightarrow P = 84\%$ ($3$ marks)
* `CSB207`: $D = 47, A = 44 \rightarrow P = 94\%$ ($5$ marks)
* `CSB213`: $D = 60, A = 53 \rightarrow P = 88\%$ ($4$ marks)
* `CSB215`: $D = 60, A = 52 \rightarrow P = 87\%$ ($4$ marks)
* `CSB314`: $D = 49, A = 44 \rightarrow P = 90\%$ ($5$ marks)
* `CSE214`: $D = 46, A = 41 \rightarrow P = 89\%$ ($4$ marks)
* `CSE234`: $D = 61, A = 51 \rightarrow P = 84\%$ ($3$ marks)
* **Aggregate:** $D = 372, A = 326 \rightarrow P = 88\%$ ($4$ marks)

---

## 7. Backend REST API Specification

1. **`POST /api/auth/request-otp`** and **`POST /api/auth/verify-otp`**
   * Request a short-lived SMS code and verify it. A verified new phone number creates a profile; a returning number signs into its existing profile. Student routes require the resulting signed session token.

2. **`GET /api/admin/calendar`**
   * **Action:** Returns the fixed session dates, day types, holidays, and teaching-day summary.
3. **`POST /api/student/upload-timetable`**
   * **Input:** `multipart/form-data` (`file: Schedule.xlsx`, optional `student_id: UUID`).
   * **Action:** Uploads `.xlsx` to Azure Blob Storage, runs `excel_parser.py`, saves `TimetableSlots` in Azure SQL, returns structured weekly schedule JSON for frontend preview/editing.
4. **`POST /api/student/upload-attendance`**
   * **Input:** `multipart/form-data` (`file: Attendance_Summary.png`, `student_id: UUID`).
   * **Action:** Uploads `.png` to Azure Blob Storage, calls Azure AI Document Intelligence (`prebuilt-layout`), saves `AttendanceRecords` in Azure SQL, returns extracted rows so user can confirm/edit before viewing analytics.
5. **`PUT /api/student/{student_id}/verify-data`**
   * **Input:** JSON payload allowing the user to manually tweak any OCR-extracted numbers or timetable slots before locking calculations.
6. **`GET /api/student/{student_id}/dashboard`**
   * **Action:** Executes `math_engine.py` against Azure SQL records and returns:
     * Aggregate summary (`current_pct`, `current_marks`, `remaining_classes`, `slabs: {90, 85, 80, 75}`)
     * List of per-course objects with `current_pct`, `current_marks`, `status_badge`, `remaining_classes`, and `slabs` (`must_attend`, `can_miss`, `is_reachable`).
7. **`POST /api/student/{student_id}/simulate`**
   * **Input:** `{ "skipped_dates": ["2026-11-25", "2026-11-26"] }` or `{ "extra_bunks_per_course": { "CSB204": 2 } }`.
   * **Action:** Recalculates projected end-of-semester percentages, mark drops, and Reappear alerts in real time.

---

## 8. Frontend UI/UX Requirements

1. **Upload & Data Verification Wizard (Streamlit prototype):**
   * **Card 1 — Timetable Upload:** Drag-and-drop zone for `Schedule.xlsx` (plus a "Manual Entry / Edit Grid" button so users can add/remove slots directly in the browser).
   * **Card 2 — Attendance Summary Upload:** Drag-and-drop zone for `Attendance_Summary.png` with an inline editable confirmation table showing the Azure Document Intelligence output (`Course`, `Delivered`, `Attended`, `Duty Leave`, `Bonus`).
   * **Fixed Calendar Panel:** View the session dates, holidays, and MTT period; students cannot replace this calendar.
2. **Main Analytics Dashboard (Streamlit prototype):**
   * **Top KPI Banner:** Aggregate Attendance %, Current Marks ($X / 5$), Remaining Teaching Days, and Aggregate Safe Bunks for $75\%$ and $85\%$.
   * **Course Cards Grid:** One card per subject displaying:
     * Color-coded header badge (Green $\ge 85\%$, Amber $75\%\text{--}84\%$, Red $< 75\%$ Reappear Warning).
     * Current ratio ($A / D$) and Remaining classes ($R$).
     * Compact 4-row slab table (`90% [5 Marks]`, `85% [4 Marks]`, `80% [3 Marks]`, `75% [2 Marks]`) clearly showing **"Attend $N$ more"** and **"Can miss $M$"** (or **"Unreachable"**).
3. **Interactive "What-If Bunk" Simulator (Streamlit prototype):**
   * Allows students to click upcoming teaching dates on a mini-calendar or adjust a "Classes to Skip" slider per subject to immediately see if skipping a day drops them from $4 \rightarrow 3$ marks or triggers a $< 75\%$ Reappear alert.

---

## 9. Step-by-Step Execution Order for AI Agent

1. **Step 1 (Database & Config):** Set up `backend/app/config.py`, `database.py`, and `models.py` with full Azure SQL (`pyodbc`) support and Alembic/SQL initialization scripts.
2. **Step 2 (Parsers & Azure Integrations):** Implement `excel_parser.py` (with merged-cell practical detection), `attendance_parser.py` (Azure AI Document Intelligence `prebuilt-layout`), and `calendar_parser.py` (fixed date data).
3. **Step 3 (Math Engine & Unit Tests):** Implement `math_engine.py` and run `pytest` against the 7 courses in Section 6.5 to verify $100\%$ precision.
4. **Step 4 (FastAPI Endpoints):** Build `admin.py`, `student.py`, and `analytics.py` routers with proper error handling and Swagger docs.
5. **Step 5 (Streamlit Prototype):** Build the upload wizard (with editable verification tables for timetable and attendance summary), dashboard, and What-If simulator. Keep calculations and API-facing logic outside UI rendering where practical so the interface can be replaced later.
6. **Step 6 (Deployment Config):** Generate `Dockerfile` / Azure App Service startup commands (`gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app`) and README setup guide.
