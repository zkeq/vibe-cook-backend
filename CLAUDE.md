# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Vibe Cook Backend (Vibe Cook Backend) is a minimalist backend built on one guiding
principle: **极致简单，不容易出错** (Extremely simple, hard to make mistakes).

It started from a clean vertical slice — **JWT auth + user management** — and now also
serves **recipes**. The architecture stays flat: add modules by following the same pattern.

- **Flat architecture**: core files at the root, no deep nesting
- **No ORM**: direct SQL via PyMySQL with parameterized queries
- **No service layer**: router calls business functions directly
- **Explicit transactions & logging**: what you see is what you get

## The Three-Layer Pattern

```
Request → router.py → auth middleware → business/*.py → SQL → Response
```

1. **router.py** — receives request, validates params (Pydantic), calls business
2. **auth.py** — authenticates via JWT, checks role (user / editor / admin)
3. **business/*.py** — executes business logic with direct SQL
4. **Returns** — a plain dict / list back to the client

## File Structure

```
main.py         → FastAPI app, middleware, startup
router.py       → All route definitions (calls business layer)
auth.py         → JWT, password hashing/verify, Redis-based SMS code
db.py           → MySQL connection pool + Redis client
logger.py       → Logging configuration
exceptions.py   → Custom exception classes + handlers
init_admin.py   → Create/reset the admin account
business/
  ├── __init__.py → Re-exports business functions
  └── user.py     → User management (the canonical pattern)
sql/init.sql    → Schema (users table only)
```

## The Template Pattern: business/user.py

All business logic should follow `business/user.py`:

```python
def function_name(param):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT col FROM table WHERE x = %s", (param,))
        result = cursor.fetchone()   # or fetchall()
        return result
    except Exception as e:
        conn.rollback()
        business_logger.error(f"failed: {param}, error={e}")
        raise
    finally:
        cursor.close()
        conn.close()
```

Key points:
- Use `get_db_connection()` from `db.py`
- Parameterized queries (`%s`) to prevent SQL injection
- DictCursor (default) returns dict rows
- Writes use `conn.commit()` / `conn.rollback()`
- Always close cursor and connection in `finally`
- Log errors with context

## Authentication

`auth.py` provides FastAPI dependencies:

```python
from auth import get_current_user, require_editor, require_admin

@api.get("/me")
async def me(user: dict = Depends(get_current_user)):
    user_id = user["user_id"]   # decoded JWT payload
```

- `get_current_user` — any authenticated user
- `require_editor` — role in (editor, admin)
- `require_admin` — role == admin

Login flows: password (admin/editor) and SMS code (users, auto-register).
SMS sending is stubbed via Redis — wire a real provider in `send_sms_code`.

## Error Handling

Raise exceptions from `exceptions.py`; handlers in `main.py` map them to HTTP:

```python
from exceptions import (
    AuthException, PermissionException,
    NotFoundException, ValidationException,
)
```

## Common Commands

```bash
pip install -r requirements.txt        # install deps
mysql -u root -p < sql/init.sql        # init database
python init_admin.py                   # create admin / admin123
python main.py                         # run server
uvicorn main:app --reload --port 8000  # run with reload
pytest -v                              # run tests
```

## Adding a New Module

1. Create `business/<name>.py` following the `user.py` pattern
2. Re-export its functions in `business/__init__.py`
3. Add routes in `router.py` (Pydantic models + thin handlers)
4. Add tables to `sql/init.sql` if needed
5. Test via `/docs`

## Configuration

Copy `config.example.yaml` to `config.yaml`. Sections: `SERVER`, `MYSQL`,
`REDIS`, `JWT`. For production: set a random `JWT.secret_key`,
`SERVER.debug: false`, and restrict CORS `allow_origins` in `main.py`.
