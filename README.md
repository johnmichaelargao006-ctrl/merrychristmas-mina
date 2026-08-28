# New theme — integration guide

Three files, two "moods":

- `welcome.html` + `gallery-login.html` → **Mina's side** ("Snowlight Keepsake" theme: blush/wine palette, falling snow, gift-tag card)
- `admin-login.html` → **your side** ("Control Ledger" theme: dark, brass, monospace — deliberately doesn't look like a Christmas gift, so it reads as a private tool)

## 1. Drop them into your Flask templates folder

Your app is on PythonAnywhere, so likely structured like:

```
merrychristmasmina/
├── app.py
├── templates/
│   ├── welcome.html
│   ├── gallery-login.html   (or gallery_login.html)
│   └── login.html           (admin login)
└── static/
```

Copy the content of each file into the matching template. Keep your existing Flask `render_template()` calls pointing at the same filenames — you're only replacing what's inside the file, not the route logic.

## 2. Reconnect your existing error messages

Each file has a commented-out line like:

```html
<!-- {% if error %}<div class="error">{{ error }}</div>{% endif %} -->
```

If your current `login.html` / `gallery-login.html` already passes an `error` variable on a wrong password (check your `app.py` — something like `return render_template('login.html', error="Wrong password")`), just uncomment that line in the new template. That's the only backend-aware part of these files; everything else is static.

## 3. Form actions

I set the `<form action="...">` values to match what your screenshots show (`/gallery-login`, `/login`). Double check these against your actual `app.py` routes — if they differ, just edit the `action` attribute.

## 4. Fonts

Both themes pull fonts from Google Fonts via `@import` in the `<style>` block:
- Mina's side: **Playfair Display** (headings) + **Cormorant Garamond** (body)
- Admin side: **Fraunces** (headings) + **JetBrains Mono** (everything else)

This needs internet access at page-load time, which PythonAnywhere's free tier allows for outbound font requests from the *browser* (not the server), so it'll work fine as-is.

## 5. What changed, design-wise

**Mina's theme** — kept the pink/Christmas heart of the original but moved it from "generic pink gradient" to something with more intention:
- Deeper wine/rose palette instead of bright pink, so it reads romantic rather than like a marketing page
- A gift-tag ribbon clipped to the top of the card — it's a memory site, so the card itself looks like a wrapped keepsake
- Gentle falling snow (pure CSS/JS, no libraries) instead of static sparkle emojis
- Serif italic headings for a handwritten, personal feel

**Admin theme** — deliberately the opposite mood: dark, quiet, ledger-like, with a stitched left edge (like a logbook spine) and a brass keyhole icon. The idea is that when *you're* looking at visitor logs, it should feel like a private control panel, not compete with the gift aesthetic Mina sees.

## 6. Backend: app.py

I also built the full Flask backend (`app.py`) that these templates plug into — download `merrychristmasmina.zip` for the whole runnable project. It's SQLite-based (no separate database server needed) and covers everything your screenshots show:

**Mina's side**
- `/` — welcome page
- `/gallery-login` — password check, and it logs a new `VisitorSession` row (login time + IP) the moment she gets in
- `/gallery` — grid of memory cards with photo-count badges
- `/memory/<id>` — single memory, counts as a "picture viewed" on her session
- `/gallery-logout` — records her logout time

**Your side**
- `/login` — admin sign-in (username/password, hashed)
- `/admin` — the two tables from your screenshot: visitor sessions and uploaded memories, with a delete button per memory
- `/upload` — add a new memory (caption + one or more photos)

**Before you run it**, set these as real environment variables (don't leave the defaults in `app.py` once this is live):

```bash
export SECRET_KEY="something-long-and-random"
export GALLERY_PASSWORD="the password you send Mina"
export ADMIN_USERNAME="your-username"
export ADMIN_PASSWORD="your-password"
```

On PythonAnywhere, set these under **Web → Environment variables** on your app's config page, then in a Bash console:

```bash
cd merrychristmasmina
pip install -r requirements.txt --user
```

Point your WSGI file at `app` (the Flask instance in `app.py`), reload the web app, and it's live.

Locally, to try it before deploying:
```bash
pip install -r requirements.txt
python app.py
```
then open `http://127.0.0.1:5000`.

## 7. One thing worth reconsidering

Your admin dashboard logs Mina's IP address per session. If she doesn't know that's being tracked, it's worth flagging to yourself — worth a quick mention to her, or dropping that column, depending on how you want the surprise to land.
