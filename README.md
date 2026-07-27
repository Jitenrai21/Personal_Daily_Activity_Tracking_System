# Personal Daily Activity Tracking System

A Django application for tracking daily personal activities, planning schedules, and measuring time-use consistency through explainable metrics.

## Features

### Activity management
- Define activities under customizable categories (e.g., Fitness, Work, Learning)
- Set weight/priority (1–5) and notes per activity
- Optional recurrence rules (daily/weekly/monthly) for automatic planning
- Full CRUD via dedicated pages or inline editing on the planner

### Daily planning
- **Schedule blocks**: Add planned activity blocks to any date with category, activity, date, time range, and duration
- **Edit blocks**: Inline editing of any schedule block field — click the pencil icon on any block to swap to an editable form, then Save or Cancel
- **Copy from yesterday**: One-click button to duplicate the previous day's plan (all activities and durations) to the current day
- **Timer integration**: Start, pause, resume, and stop timers directly from each schedule block
- **Inline management**: Add, edit, and delete categories and activities without leaving the planner page

### Session tracking
- Timer-based sessions with pause/resume support
- Manual session logging
- Sessions are linked to planned blocks via metadata for accurate completion tracking
- CSV and JSON export

### Analytics & dashboard
- Daily KPIs: total minutes, planned minutes, completion rate, sessions count
- Daily scores: discipline, balance, recovery, and composite (v1 algorithm)
- Interactive charts using Chart.js (planned vs actual by category)
- Yearly heatmap for at-a-glance consistency
- Daily reflections with mood tagging and text prompts
- Signal-driven automatic recomputation on session/plan changes

## Architecture

### Project structure

```
pdat/                    # Django project settings (base.py, dev.py, prod.py)
activities/              # Activity & category definitions + recurrence rules
planner/                 # Daily scheduling: ScheduleBlock, inline CRUD, timer ops
tracking/                # Session tracking: timer, manual logging, export
analytics/               # Dashboard, KPIs, scores, reflections, heatmap
users/                   # Auth, signup, profile (timezone, wake/sleep targets)
templates/               # HTML templates with HTMX dynamic interactions
static/                  # Static assets
tests/                   # Test suite
```

### Key models

| Model | App | Purpose |
|-------|-----|---------|
| `ActivityCategory` | activities | User-defined categories (e.g., Fitness, Work) |
| `Activity` | activities | Activity definitions with weight, category, notes |
| `RecurrenceRule` | activities | Optional recurrence schedule for activities |
| `ScheduleBlock` | planner | A planned activity block on a specific date/time |
| `Session` | tracking | An actual tracked session (timer or manual) |
| `AggregatedDaily` | analytics | Daily aggregated metrics |
| `DailyScore` | analytics | Computed discipline/balance/recovery scores |
| `DailyReflection` | analytics | Daily journal entry with mood |
| `UserProfile` | users | Per-user timezone, wake/sleep preferences |

### Frontend

- Server-rendered Django templates
- **HTMX** for dynamic partial swaps (no page reloads for CRUD, timer, filtering)
- **Chart.js** for analytics visualizations
- All JavaScript is inlined in templates; no separate JS bundle

## Quick start (Windows PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r dev-requirements.txt
Copy-Item .env.example .env
# Edit .env to set DJANGO_SECRET_KEY and database settings
python manage.py migrate
python manage.py runserver
```

Visit http://localhost:8000/ — the health endpoint returns `OK`.

## URL reference

### Main pages
| URL | View | Description |
|-----|------|-------------|
| `/` | health_view | Health check |
| `/planner/` | daily_plan_view | Daily planner (date query param) |
| `/tracking/` | session_list_view | Session history + manual log |
| `/activities/` | activity_list_view | Activity definitions |
| `/categories/` | category_list_view | Category management |
| `/dashboard/` | dashboard_view | Analytics dashboard |
| `/accounts/login/` | Login | Django auth login |
| `/accounts/signup/` | signup_view | User registration |
| `/accounts/profile/` | profile_view | User profile settings |

### Planner — schedule blocks
| URL | Method | Description |
|-----|--------|-------------|
| `/planner/create/` | POST | Create a schedule block |
| `/planner/<pk>/edit/` | GET | Get inline edit form |
| `/planner/<pk>/update/` | POST | Save edited schedule block |
| `/planner/<pk>/row/` | GET | Get single block row (for cancel) |
| `/planner/<pk>/delete/` | POST | Delete a schedule block |
| `/planner/<pk>/start/` | POST | Start timer for block |
| `/planner/<pk>/pause/` | POST | Pause timer for block |
| `/planner/<pk>/resume/` | POST | Resume timer for block |
| `/planner/<pk>/stop/` | POST | Stop timer for block |
| `/planner/copy-previous/` | POST | Copy yesterday's plan to today |

### Planner — inline CRUD
| URL | Method | Description |
|-----|--------|-------------|
| `/planner/categories/create/` | POST | Create category |
| `/planner/categories/<pk>/update/` | POST | Update category |
| `/planner/categories/<pk>/delete/` | POST | Delete category |
| `/planner/activities/create/` | POST | Create activity |
| `/planner/activities/<pk>/update/` | POST | Update activity |
| `/planner/activities/<pk>/delete/` | POST | Delete activity |

### Tracking
| URL | Method | Description |
|-----|--------|-------------|
| `/tracking/start/` | POST | Start manual timer |
| `/tracking/stop/` | POST | Stop timer |
| `/tracking/log/` | POST | Log manual session |
| `/tracking/<pk>/edit/` | GET/POST | Edit session |
| `/tracking/<pk>/delete/` | POST | Delete session |
| `/tracking/export/csv/` | GET | Export sessions as CSV |
| `/tracking/export/json/` | GET | Export sessions as JSON |

## Testing

```powershell
python -m pytest tests/
```

All tests use SQLite in-memory database with pytest-django. Tests cover models, forms, views, services, and analytics computations.

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DJANGO_SECRET_KEY` | Yes | — | Django secret key |
| `DATABASE_URL` | No | SQLite | Database connection string |
| `DEBUG` | No | False | Debug mode |
| `ALLOWED_HOSTS` | No | `*` | Allowed hostnames |
