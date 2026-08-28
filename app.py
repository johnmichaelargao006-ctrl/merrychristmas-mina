"""
merrychristmasmina — backend
=============================
A small Flask app with two sides:

  Mina's side   -> welcome page -> password gate -> gallery of memories
  Admin side    -> username/password login -> dashboard (visitor logs,
                   uploaded memories, upload form)

Storage: SQLite via Flask-SQLAlchemy (one file, "site.db", created
automatically on first run). Photos are saved to /static/uploads.

Run locally:
    pip install -r requirements.txt
    python app.py
    -> http://127.0.0.1:5000

Deploying to PythonAnywhere: see README.md.
"""

import os
import uuid
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, abort
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

app = Flask(__name__)

# --- secrets & credentials -------------------------------------------
# Set these as real environment variables before deploying. The
# fallbacks below are only so the app runs out of the box locally —
# change them before you ever put this on the internet.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "site.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB per request

GALLERY_PASSWORD = os.environ.get("GALLERY_PASSWORD", "Ma'am_Carmina")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "cafemocha")
# Hash of the admin password — generated once from ADMIN_PASSWORD_PLAIN
# below purely so the app has *something* to check on first run.
# Prefer setting ADMIN_PASSWORD_HASH directly in your environment.
ADMIN_PASSWORD_PLAIN = os.environ.get("ADMIN_PASSWORD", "ianargao")
ADMIN_PASSWORD_HASH = os.environ.get(
    "ADMIN_PASSWORD_HASH", generate_password_hash(ADMIN_PASSWORD_PLAIN)
)

db = SQLAlchemy(app)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ----------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------

class Memory(db.Model):
    """One 'memory' card in the gallery — a short caption plus one or
    more photos."""
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(300), default="A special memory")
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    photos = db.relationship(
        "Photo", backref="memory", cascade="all, delete-orphan",
        order_by="Photo.id"
    )

    @property
    def cover_photo(self):
        return self.photos[0] if self.photos else None


class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(300), nullable=False)
    memory_id = db.Column(db.Integer, db.ForeignKey("memory.id"), nullable=False)


class VisitorSession(db.Model):
    """One row per time Mina unlocks the gallery — used for the
    'Visitor Activity Logs' table on the admin dashboard."""
    id = db.Column(db.Integer, primary_key=True)
    login_time = db.Column(db.DateTime, default=datetime.utcnow)
    logout_time = db.Column(db.DateTime, nullable=True)
    ip_address = db.Column(db.String(64))
    pictures_viewed = db.Column(db.Integer, default=0)

    @property
    def duration_display(self):
        if not self.logout_time:
            return "Active"
        delta = self.logout_time - self.login_time
        minutes, seconds = divmod(int(delta.total_seconds()), 60)
        return f"{minutes}m {seconds}s"


class Message(db.Model):
    """One chat message in the shared conversation thread between
    Mina and the admin."""
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(10), nullable=False)  # 'mina' or 'admin'
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


with app.app_context():
    db.create_all()


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def gallery_required(view):
    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("gallery_authed"):
            return redirect(url_for("gallery_login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)

    return wrapped


# ----------------------------------------------------------------------
# Mina's side
# ----------------------------------------------------------------------

@app.route("/")
def welcome():
    return render_template("welcome.html")


@app.route("/gallery-login", methods=["GET", "POST"])
def gallery_login():
    error = None
    if request.method == "POST":
        entered = request.form.get("password", "")
        if entered == GALLERY_PASSWORD:
            visit = VisitorSession(
                ip_address=request.headers.get("X-Forwarded-For", request.remote_addr)
            )
            db.session.add(visit)
            db.session.commit()

            session["gallery_authed"] = True
            session["visit_id"] = visit.id
            return redirect(url_for("gallery"))
        error = "That password isn't quite right — try again."
    return render_template("gallery-login.html", error=error)


@app.route("/gallery")
@gallery_required
def gallery():
    memories = Memory.query.order_by(Memory.uploaded_at.desc()).all()
    return render_template("gallery.html", memories=memories)


@app.route("/memory/<int:memory_id>")
@gallery_required
def memory_detail(memory_id):
    memory = Memory.query.get_or_404(memory_id)

    # count this as a "picture viewed" for the current visitor session
    visit_id = session.get("visit_id")
    if visit_id:
        visit = VisitorSession.query.get(visit_id)
        if visit:
            visit.pictures_viewed = (visit.pictures_viewed or 0) + 1
            db.session.commit()

    return render_template("memory.html", memory=memory)


@app.route("/gallery-logout")
def gallery_logout():
    visit_id = session.get("visit_id")
    if visit_id:
        visit = VisitorSession.query.get(visit_id)
        if visit and not visit.logout_time:
            visit.logout_time = datetime.utcnow()
            db.session.commit()
    session.pop("gallery_authed", None)
    session.pop("visit_id", None)
    return redirect(url_for("welcome"))


@app.route("/messages", methods=["GET", "POST"])
@gallery_required
def mina_messages():
    if request.method == "POST":
        body = request.form.get("body", "").strip()
        if body:
            db.session.add(Message(sender="mina", body=body))
            db.session.commit()
        return redirect(url_for("mina_messages"))

    thread = Message.query.order_by(Message.created_at.asc()).all()
    return render_template("messages.html", thread=thread)


# ----------------------------------------------------------------------
# Admin side
# ----------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
        error = "Incorrect username or password."
    return render_template("login.html", error=error)


@app.route("/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    visits = VisitorSession.query.order_by(VisitorSession.login_time.desc()).all()
    memories = Memory.query.order_by(Memory.uploaded_at.desc()).all()
    return render_template("admin.html", visits=visits, memories=memories)


@app.route("/upload", methods=["GET", "POST"])
@admin_required
def upload():
    if request.method == "POST":
        description = request.form.get("description", "").strip() or "A special memory"
        files = request.files.getlist("photos")

        saved_any = False
        memory = Memory(description=description)
        db.session.add(memory)
        db.session.flush()  # get memory.id before adding photos

        for f in files:
            if f and f.filename and allowed_file(f.filename):
                ext = f.filename.rsplit(".", 1)[1].lower()
                unique_name = f"{uuid.uuid4().hex}.{ext}"
                f.save(os.path.join(app.config["UPLOAD_FOLDER"], unique_name))
                db.session.add(Photo(filename=unique_name, memory_id=memory.id))
                saved_any = True

        if not saved_any:
            db.session.rollback()
            flash("Please choose at least one valid image (png, jpg, jpeg, gif, webp).")
            return redirect(url_for("upload"))

        db.session.commit()
        return redirect(url_for("admin_dashboard"))

    return render_template("upload.html")


@app.route("/admin/edit/<int:memory_id>", methods=["GET", "POST"])
@admin_required
def edit_memory(memory_id):
    memory = Memory.query.get_or_404(memory_id)

    if request.method == "POST":
        # 1. update the caption
        memory.description = request.form.get("description", "").strip() or memory.description

        # 2. remove any photos the admin checked for deletion
        remove_ids = {int(i) for i in request.form.getlist("remove_photos")}
        for photo in list(memory.photos):
            if photo.id in remove_ids:
                path = os.path.join(app.config["UPLOAD_FOLDER"], photo.filename)
                if os.path.exists(path):
                    os.remove(path)
                db.session.delete(photo)

        # 3. add any newly uploaded photos
        for f in request.files.getlist("new_photos"):
            if f and f.filename and allowed_file(f.filename):
                ext = f.filename.rsplit(".", 1)[1].lower()
                unique_name = f"{uuid.uuid4().hex}.{ext}"
                f.save(os.path.join(app.config["UPLOAD_FOLDER"], unique_name))
                db.session.add(Photo(filename=unique_name, memory_id=memory.id))

        db.session.commit()
        flash("Memory updated.")
        return redirect(url_for("admin_dashboard"))

    return render_template("edit.html", memory=memory)


@app.route("/admin/delete/<int:memory_id>", methods=["POST"])
@admin_required
def delete_memory(memory_id):
    memory = Memory.query.get_or_404(memory_id)
    for photo in memory.photos:
        path = os.path.join(app.config["UPLOAD_FOLDER"], photo.filename)
        if os.path.exists(path):
            os.remove(path)
    db.session.delete(memory)
    db.session.commit()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/messages", methods=["GET", "POST"])
@admin_required
def admin_messages():
    if request.method == "POST":
        body = request.form.get("body", "").strip()
        if body:
            db.session.add(Message(sender="admin", body=body))
            db.session.commit()
        return redirect(url_for("admin_messages"))

    thread = Message.query.order_by(Message.created_at.asc()).all()
    return render_template("admin_messages.html", thread=thread)


@app.route("/admin/messages/delete/<int:message_id>", methods=["POST"])
@admin_required
def delete_message(message_id):
    msg = Message.query.get_or_404(message_id)
    db.session.delete(msg)
    db.session.commit()
    return redirect(url_for("admin_messages"))


# ----------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)