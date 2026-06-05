# Test Evaluations Tracker — Flask + DB

## Setup

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000

---

## Database

By default the app uses **SQLite** — no config needed.  
A file `tracker.db` is created automatically next to `app.py`.

To use a different database, set the `DATABASE_URI` environment variable
**before** running the app:

| Database   | URI format                                      |
|------------|-------------------------------------------------|
| SQLite     | `sqlite:///tracker.db`  ← default              |
| PostgreSQL | `postgresql://user:pass@localhost/tracker`      |
| MySQL      | `mysql+pymysql://user:pass@localhost/tracker`   |

**Linux / Mac:**
```bash
export DATABASE_URI="postgresql://user:pass@localhost/tracker"
python app.py
```

**Windows (cmd):**
```cmd
set DATABASE_URI=postgresql://user:pass@localhost/tracker
python app.py
```

Tables are **created automatically** on first run — no migrations needed.

---

## Project structure

```
tracker/
├── app.py               ← Flask app + DB model + API routes
├── requirements.txt
└── templates/
    └── index.html       ← Full frontend (unchanged design)
```

## API endpoints

| Method | URL                    | Description          |
|--------|------------------------|----------------------|
| GET    | `/api/entries`         | List all entries     |
| POST   | `/api/entries`         | Add a new entry      |
| DELETE | `/api/entries/<id>`    | Delete one entry     |
| DELETE | `/api/entries/all`     | Delete all entries   |
