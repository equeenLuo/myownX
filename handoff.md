# myownX Handoff

## Project Rules

- Local classroom demo social network inspired by X.com.
- Backend stack is fixed: Python 3, Flask, Flask-SQLAlchemy, Flask-Login, SQLite, Jinja2, Bootstrap 5.
- Do not use Vue, React, Node.js, npm, MySQL, Docker, Redis, WebSocket, third-party login, cloud storage, or complex ML.
- Work one task at a time. Do not implement future tasks early.
- Backend/frontend alignment must be maintained in `docs/CONTRACT.md`.
- All backend flash/error/success/validation messages shown to the frontend must be in English.
- After each task, update `docs/CONTRACT.md`, `docs/TASK_BOARD.md`, and give run, test, and Git commit commands.

## Current Progress

Completed through TASK-7:

- Flask app skeleton, config, requirements, base pages, `/health`.
- Auth: register, login, logout.
- Profile view/edit/avatar upload.
- Text posts and feed.
- Image posts, including up to 4 images per post.
- Follow/unfollow and discover recommendations.
- Likes and comments.
- Reposts, including clicking repost again to cancel repost.

Do not redo these unless fixing bugs.

## Current Important Behavior

- Empty/static routes still exist for unfinished areas such as messages and notification UI.
- `Notification` model exists and minimal notifications are already created for like/comment/repost.
- Repost rows use `Post.repost_from_id`.
- Existing SQLite databases are patched at startup by `ensure_schema_updates(app)` if `posts.repost_from_id` is missing.
- Post images are stored under `static/uploads/posts`.
- Avatar images are stored under `static/uploads/avatars`.

## Likely Next Task

Next task should probably be TASK-8, depending on `docs/TASK_BOARD.md`.

Before implementing, read:

- `AGENTS.md`
- `docs/CONTRACT.md`
- `docs/TASK_BOARD.md`
- Current `app.py`, `models.py`, and relevant templates

For TASK-8, likely scope is notification page and mark-read behavior. Keep it minimal and do not implement private messages unless the task explicitly asks for that.

## Useful Commands

Run app:

```powershell
.\.venv\Scripts\python.exe app.py
```

Compile check:

```powershell
.\.venv\Scripts\python.exe -m compileall app.py config.py models.py
```

Git status:

```powershell
git status --short --ignored
```

Docs are ignored by `.gitignore`, so when committing docs use:

```powershell
git add app.py models.py templates static
git add -f docs/CONTRACT.md docs/TASK_BOARD.md README.md
git commit -m "Complete task 8"
```

## Current Caution

There may be uncommitted changes from TASK-7. Do not reset or overwrite user/frontend-agent changes. Inspect diffs before editing shared template/static files.
