# Attendance Saver

Attendance Saver is a full-stack student attendance planner. The project calendar is fixed in `sample_data/Session_Calendar.png`. Each student can upload their own `Schedule.xlsx` and attendance summary image; the timetable is parsed with `openpyxl`, and the attendance image is read through Azure AI Document Intelligence when configured. Both uploads can be corrected in Streamlit before analytics are saved.

## Project folders

- `frontend/streamlit_app.py` — Streamlit upload, review, dashboard, and what-if experience.
- `backend/app/` — FastAPI endpoints, SQLAlchemy models, parsers, Azure storage/OCR services, and attendance math.
- `backend/tests/` — parser, calendar, and math unit tests.
- `sample_data/` — fixed session calendar and example student uploads.

## Run locally

Use Python 3.11 or newer. From the project root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Start the API in the first terminal:

```powershell
uvicorn --app-dir backend --reload app.main:app
```

Start Streamlit in a second terminal:

```powershell
streamlit run frontend/streamlit_app.py
```

Open `http://localhost:8501`. The API docs are at `http://localhost:8000/docs`. Azure SQL Database and Azure Blob Storage are required; the backend does not fall back to SQLite or local upload folders. Attendance OCR uses Azure Document Intelligence when configured; extracted rows can be reviewed and corrected before saving. Authentication is skipped in this prototype; the app creates an internal guest profile as needed.

Install test tools with `python -m pip install -r requirements-dev.txt`, then run the unit suite from the project root with `python -m pytest backend/tests`.

To run the two apps in containers, configure any desired settings in `.env` and run:

```powershell
docker compose up --build
```

## Fixed session calendar

The backend seeds the 2026 odd-semester calendar on startup: Aug 10 through Dec 11, reference date Nov 23, MTT Oct 12–17, and the holidays shown in the checked-in image. Sundays are weekends. Students cannot upload or replace this calendar.

## Azure setup when ready

The application can use local development services or Azure services through environment variables. Keep real credentials in `.env`; `.env` is ignored by Git.

1. **Azure AI Document Intelligence** — Create a Document Intelligence resource in the Azure portal. Open **Keys and Endpoint**, then set `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` and `AZURE_DOCUMENT_INTELLIGENCE_KEY` in `.env`. The attendance screenshot upload uses the `prebuilt-layout` model.
2. **Azure Blob Storage** — Create a Storage Account and set its connection string as `AZURE_STORAGE_CONNECTION_STRING`. This setting is required. The app creates `student-timetables` and `attendance-summaries` containers when first used.
3. **Azure SQL Database** — Create an Azure SQL logical server and database. In the server's networking page, allow your development IP while working locally. Set `AZURE_SQL_SERVER` to the `*.database.windows.net` hostname, plus `AZURE_SQL_DATABASE`, `AZURE_SQL_USERNAME`, and `AZURE_SQL_PASSWORD`. Install Microsoft ODBC Driver 18 on a local host. The application creates its SQLAlchemy tables and seeds the fixed calendar at startup.

When you are ready to connect Azure, I can walk through each resource in the portal and tell you exactly which endpoint, key, and connection settings to place in `.env`. You do not need to commit or publish any secrets.

## API routes

- `GET /api/admin/calendar` — fixed semester calendar and day classifications.
- `POST /api/auth/guest` — create an internal guest profile for the current prototype session.
- `GET /api/auth/me` — return the current guest profile.
- `POST /api/student/upload-timetable` — parse and save a user's `.xlsx` timetable.
- `POST /api/student/upload-attendance` — OCR and save a user's attendance image.
- `PUT /api/student/{student_id}/verify-data` — save edits made in the review tables.
- `GET /api/student/{student_id}/dashboard` — course and aggregate attendance plans.
- `POST /api/student/{student_id}/simulate` — simulate skipped dates or additional course bunks.

The math engine applies half-up integer percentage rounding, a 100% cap, strict target thresholds by default, and the 5-mark slabs in `AGENTS.md`.
