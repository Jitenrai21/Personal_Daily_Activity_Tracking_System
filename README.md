# Personal Daily Activity Tracking System

## Purpose

A lightweight system to track daily personal activities, routines, and time use. The project helps users observe patterns, measure consistency, and improve life-balance through simple, explainable metrics.

## Abstract

This backend-first application stores activity definitions and session logs, materializes schedules for short horizons, and calculates core metrics such as completion rate, time-on-target, and streaks. The initial focus is on a robust, testable foundation to enable iterative addition of analytics and UI features.

## Core principles

- Simplicity: minimal models and clear behavior.
- Privacy: avoid committing secrets and keep data control local.
- Iterative value: prioritize a testable foundation and CI to support rapid additions.

## Quick start (Windows PowerShell)

1. Create and activate a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2. Install dependencies

```powershell
pip install -r requirements.txt -r dev-requirements.txt
```

3. Configure environment

```powershell
Copy-Item .env.example .env
notepad .env   # set DB and DJANGO_SECRET_KEY
```

4. Run migrations and start the server

```powershell
python manage.py migrate
python manage.py runserver
```

Visit http://localhost:8000/ to verify the health endpoint.
