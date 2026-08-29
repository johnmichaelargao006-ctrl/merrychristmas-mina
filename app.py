"""
merrychristmasmina — backend
=============================
Flask app for the memory gallery.

Features:
- Mina gallery
- Admin dashboard
- Upload memories
- Hide/unhide memories
- Persistent likes
- Persistent comments
- Visitor logs
- Admin/Mina messages
"""

import os
import uuid
from datetime import datetime

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    abort,
    jsonify
)

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash


# ============================================================
# CONFIG
# ============================================================

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "static",
    "uploads"
)

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp"
}

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "dev-change-me"
)

app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///" +
    os.path.join(BASE_DIR, "site.db")
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

app.config["MAX_CONTENT_LENGTH"] = (
    16 * 1024 * 1024
)

GALLERY_PASSWORD = os.environ.get(
    "GALLERY_PASSWORD",
    "Ma'am_Carmina"
)

ADMIN_USERNAME = os.environ.get(
    "ADMIN_USERNAME",
    "cafemocha"
)

ADMIN_PASSWORD_PLAIN = os.environ.get(
    "ADMIN_PASSWORD",
    "ianargao"
)

ADMIN_PASSWORD_HASH = os.environ.get(
    "ADMIN_PASSWORD_HASH",
    generate_password_hash(
        ADMIN_PASSWORD_PLAIN
    )
)

db = SQLAlchemy(app)

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)


# ============================================================
# MODELS
# ============================================================

class Memory(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    description = db.Column(
        db.String(300),
        default="A special memory"
    )

    uploaded_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    is_hidden = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    photos = db.relationship(
        "Photo",
        backref="memory",
        cascade="all, delete-orphan",
        order_by="Photo.id"
    )

    likes = db.relationship(
        "Like",
        backref="memory",
        cascade="all, delete-orphan"
    )

    comments = db.relationship(
        "Comment",
        backref="memory",
        cascade="all, delete-orphan",
        order_by="Comment.created_at"
    )

    @property
    def cover_photo(self):

        return (
            self.photos[0]
            if self.photos
            else None
        )

    @property
    def like_count(self):

        return Like.query.filter_by(
            memory_id=self.id
        ).count()

    @property
    def comment_count(self):

        return Comment.query.filter_by(
            memory_id=self.id
        ).count()


class Photo(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    filename = db.Column(
        db.String(300),
        nullable=False
    )

    memory_id = db.Column(
        db.Integer,
        db.ForeignKey("memory.id"),
        nullable=False
    )


class VisitorSession(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    login_time = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    logout_time = db.Column(
        db.DateTime,
        nullable=True
    )

    ip_address = db.Column(
        db.String(64)
    )

    pictures_viewed = db.Column(
        db.Integer,
        default=0
    )

    @property
    def duration_display(self):

        if not self.logout_time:
            return "Active"

        delta = (
            self.logout_time -
            self.login_time
        )

        minutes, seconds = divmod(
            int(delta.total_seconds()),
            60
        )

        return f"{minutes}m {seconds}s"


# ============================================================
# LIKE MODEL
# ============================================================

class Like(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    memory_id = db.Column(
        db.Integer,
        db.ForeignKey("memory.id"),
        nullable=False
    )

    visit_id = db.Column(
        db.Integer,
        db.ForeignKey("visitor_session.id"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    __table_args__ = (
        db.UniqueConstraint(
            "memory_id",
            "visit_id",
            name="unique_memory_visit_like"
        ),
    )


# ============================================================
# COMMENT MODEL
# ============================================================

class Comment(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    memory_id = db.Column(
        db.Integer,
        db.ForeignKey("memory.id"),
        nullable=False
    )

    body = db.Column(
        db.Text,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# ============================================================
# MESSAGE MODEL
# ============================================================

class Message(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    sender = db.Column(
        db.String(10),
        nullable=False
    )

    body = db.Column(
        db.Text,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# ============================================================
# CREATE DATABASE TABLES
# ============================================================

with app.app_context():

    db.create_all()


# ============================================================
# HELPERS
# ============================================================

def allowed_file(filename):

    return (
        "." in filename
        and
        filename.rsplit(
            ".",
            1
        )[1].lower()
        in ALLOWED_EXTENSIONS
    )


def gallery_required(view):

    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):

        if not session.get(
            "gallery_authed"
        ):

            return redirect(
                url_for("gallery_login")
            )

        return view(*args, **kwargs)

    return wrapped


def admin_required(view):

    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):

        if not session.get(
            "is_admin"
        ):

            return redirect(
                url_for("admin_login")
            )

        return view(*args, **kwargs)

    return wrapped


# ============================================================
# HOME
# ============================================================

@app.route("/")
def welcome():

    return render_template(
        "welcome.html"
    )


# ============================================================
# GALLERY LOGIN
# ============================================================

@app.route(
    "/gallery-login",
    methods=["GET", "POST"]
)
def gallery_login():

    error = None

    if request.method == "POST":

        entered = request.form.get(
            "password",
            ""
        )

        if entered == GALLERY_PASSWORD:

            visit = VisitorSession(
                ip_address=request.headers.get(
                    "X-Forwarded-For",
                    request.remote_addr
                )
            )

            db.session.add(visit)

            db.session.commit()

            session["gallery_authed"] = True

            session["visit_id"] = visit.id

            return redirect(
                url_for("gallery")
            )

        error = (
            "That password isn't quite right "
            "— try again."
        )

    return render_template(
        "gallery-login.html",
        error=error
    )


# ============================================================
# GALLERY
# ============================================================

@app.route("/gallery")
@gallery_required
def gallery():

    memories = (
        Memory.query
        .filter_by(
            is_hidden=False
        )
        .order_by(
            Memory.uploaded_at.desc()
        )
        .all()
    )

    visit_id = session.get(
        "visit_id"
    )

    liked_memory_ids = set()

    if visit_id:

        liked_rows = Like.query.filter_by(
            visit_id=visit_id
        ).all()

        liked_memory_ids = {
            like.memory_id
            for like in liked_rows
        }

    return render_template(
        "gallery.html",
        memories=memories,
        liked_memory_ids=liked_memory_ids
    )


# ============================================================
# LIKE MEMORY
# ============================================================

@app.route(
    "/gallery/like/<int:memory_id>",
    methods=["POST"]
)
@gallery_required
def like_memory(memory_id):

    memory = Memory.query.get_or_404(
        memory_id
    )

    if memory.is_hidden:

        return jsonify({
            "success": False,
            "error": "Memory not available."
        }), 404

    visit_id = session.get(
        "visit_id"
    )

    if not visit_id:

        return jsonify({
            "success": False,
            "error": "Gallery session expired."
        }), 401

    existing_like = Like.query.filter_by(
        memory_id=memory.id,
        visit_id=visit_id
    ).first()

    if existing_like:

        db.session.delete(
            existing_like
        )

        liked = False

    else:

        new_like = Like(
            memory_id=memory.id,
            visit_id=visit_id
        )

        db.session.add(
            new_like
        )

        liked = True

    db.session.commit()

    total_likes = Like.query.filter_by(
        memory_id=memory.id
    ).count()

    return jsonify({
        "success": True,
        "liked": liked,
        "like_count": total_likes
    })


# ============================================================
# ADD COMMENT
# ============================================================

@app.route(
    "/gallery/comment/<int:memory_id>",
    methods=["POST"]
)
@gallery_required
def add_comment(memory_id):

    memory = Memory.query.get_or_404(
        memory_id
    )

    if memory.is_hidden:

        return jsonify({
            "success": False,
            "error": "Memory not available."
        }), 404

    data = request.get_json(
        silent=True
    ) or {}

    comment_text = str(
        data.get(
            "comment",
            ""
        )
    ).strip()

    if not comment_text:

        comment_text = request.form.get(
            "comment",
            ""
        ).strip()

    if not comment_text:

        return jsonify({
            "success": False,
            "error": "Comment cannot be empty."
        }), 400

    if len(comment_text) > 500:

        return jsonify({
            "success": False,
            "error": "Comment is too long."
        }), 400

    new_comment = Comment(
        memory_id=memory.id,
        body=comment_text
    )

    db.session.add(
        new_comment
    )

    db.session.commit()

    total_comments = Comment.query.filter_by(
        memory_id=memory.id
    ).count()

    return jsonify({
        "success": True,
        "comment_count": total_comments,
        "comment": {
            "id": new_comment.id,
            "body": new_comment.body,
            "created_at": new_comment.created_at.strftime(
                "%B %d, %Y %I:%M %p"
            )
        }
    })


# ============================================================
# MEMORY DETAIL
# ============================================================

@app.route(
    "/memory/<int:memory_id>"
)
@gallery_required
def memory_detail(memory_id):

    memory = Memory.query.get_or_404(
        memory_id
    )

    # ========================================================
    # IMPORTANT FIX
    #
    # If a memory was hidden by the admin, do not show
    # a 404 / URL error to the visitor.
    #
    # Send the visitor back to the gallery instead.
    # ========================================================

    if memory.is_hidden:

        flash(
            "This memory is no longer available."
        )

        return redirect(
            url_for("gallery")
        )

    # ========================================================
    # COUNT PICTURE VIEW
    # ========================================================

    visit_id = session.get(
        "visit_id"
    )

    if visit_id:

        visit = VisitorSession.query.get(
            visit_id
        )

        if visit:

            visit.pictures_viewed = (
                visit.pictures_viewed or 0
            ) + 1

            db.session.commit()

    return render_template(
        "memory.html",
        memory=memory
    )


# ============================================================
# GALLERY LOGOUT
# ============================================================

@app.route("/gallery-logout")
def gallery_logout():

    visit_id = session.get(
        "visit_id"
    )

    if visit_id:

        visit = VisitorSession.query.get(
            visit_id
        )

        if visit and not visit.logout_time:

            visit.logout_time = (
                datetime.utcnow()
            )

            db.session.commit()

    session.pop(
        "gallery_authed",
        None
    )

    session.pop(
        "visit_id",
        None
    )

    return redirect(
        url_for("welcome")
    )


# ============================================================
# MINA MESSAGES
# ============================================================

@app.route(
    "/messages",
    methods=["GET", "POST"]
)
@gallery_required
def mina_messages():

    if request.method == "POST":

        body = request.form.get(
            "body",
            ""
        ).strip()

        if body:

            db.session.add(
                Message(
                    sender="mina",
                    body=body
                )
            )

            db.session.commit()

        return redirect(
            url_for("mina_messages")
        )

    thread = (
        Message.query
        .order_by(
            Message.created_at.asc()
        )
        .all()
    )

    return render_template(
        "messages.html",
        thread=thread
    )


# ============================================================
# ADMIN LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def admin_login():

    error = None

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        )

        password = request.form.get(
            "password",
            ""
        )

        if (
            username == ADMIN_USERNAME
            and
            check_password_hash(
                ADMIN_PASSWORD_HASH,
                password
            )
        ):

            session["is_admin"] = True

            return redirect(
                url_for("admin_dashboard")
            )

        error = (
            "Incorrect username or password."
        )

    return render_template(
        "login.html",
        error=error
    )


# ============================================================
# ADMIN LOGOUT
# ============================================================

@app.route("/logout")
def admin_logout():

    session.pop(
        "is_admin",
        None
    )

    return redirect(
        url_for("admin_login")
    )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route("/admin")
@admin_required
def admin_dashboard():

    visits = (
        VisitorSession.query
        .order_by(
            VisitorSession.login_time.desc()
        )
        .all()
    )

    memories = (
        Memory.query
        .order_by(
            Memory.uploaded_at.desc()
        )
        .all()
    )

    comments = (
        Comment.query
        .order_by(
            Comment.created_at.desc()
        )
        .all()
    )

    likes = (
        Like.query
        .order_by(
            Like.created_at.desc()
        )
        .all()
    )

    return render_template(
        "admin.html",
        visits=visits,
        memories=memories,
        comments=comments,
        likes=likes
    )


# ============================================================
# ADMIN DELETE COMMENT
# ============================================================

@app.route(
    "/admin/comment/delete/<int:comment_id>",
    methods=["POST"]
)
@admin_required
def delete_comment(comment_id):

    comment = Comment.query.get_or_404(
        comment_id
    )

    db.session.delete(
        comment
    )

    db.session.commit()

    flash(
        "Comment deleted."
    )

    return redirect(
        url_for("admin_dashboard")
    )


# ============================================================
# ADMIN HIDE / UNHIDE
# ============================================================

@app.route(
    "/admin/memory/<int:memory_id>/toggle-hide",
    methods=["POST"]
)
@admin_required
def toggle_hide_memory(memory_id):

    memory = Memory.query.get_or_404(
        memory_id
    )

    memory.is_hidden = not memory.is_hidden

    db.session.commit()

    flash(
        "✅ Hide status updated!"
    )

    return redirect(
        url_for("admin_dashboard")
    )


# ============================================================
# UPLOAD
# ============================================================

@app.route(
    "/upload",
    methods=["GET", "POST"]
)
@admin_required
def upload():

    if request.method == "POST":

        description = (
            request.form.get(
                "description",
                ""
            ).strip()
            or
            "A special memory"
        )

        files = request.files.getlist(
            "photos"
        )

        saved_any = False

        memory = Memory(
            description=description
        )

        db.session.add(
            memory
        )

        db.session.flush()

        for f in files:

            if (
                f
                and f.filename
                and allowed_file(
                    f.filename
                )
            ):

                ext = (
                    f.filename
                    .rsplit(
                        ".",
                        1
                    )[1]
                    .lower()
                )

                unique_name = (
                    f"{uuid.uuid4().hex}.{ext}"
                )

                f.save(
                    os.path.join(
                        app.config[
                            "UPLOAD_FOLDER"
                        ],
                        unique_name
                    )
                )

                db.session.add(
                    Photo(
                        filename=unique_name,
                        memory_id=memory.id
                    )
                )

                saved_any = True

        if not saved_any:

            db.session.rollback()

            flash(
                "Please choose at least one valid "
                "image (png, jpg, jpeg, gif, webp)."
            )

            return redirect(
                url_for("upload")
            )

        db.session.commit()

        return redirect(
            url_for("admin_dashboard")
        )

    return render_template(
        "upload.html"
    )


# ============================================================
# EDIT MEMORY
# ============================================================

@app.route(
    "/admin/edit/<int:memory_id>",
    methods=["GET", "POST"]
)
@admin_required
def edit_memory(memory_id):

    memory = Memory.query.get_or_404(
        memory_id
    )

    if request.method == "POST":

        memory.description = (
            request.form.get(
                "description",
                ""
            ).strip()
            or
            memory.description
        )

        remove_ids = {
            int(i)
            for i in request.form.getlist(
                "remove_photos"
            )
        }

        for photo in list(
            memory.photos
        ):

            if photo.id in remove_ids:

                path = os.path.join(
                    app.config[
                        "UPLOAD_FOLDER"
                    ],
                    photo.filename
                )

                if os.path.exists(path):

                    os.remove(path)

                db.session.delete(
                    photo
                )

        for f in request.files.getlist(
            "new_photos"
        ):

            if (
                f
                and f.filename
                and allowed_file(
                    f.filename
                )
            ):

                ext = (
                    f.filename
                    .rsplit(
                        ".",
                        1
                    )[1]
                    .lower()
                )

                unique_name = (
                    f"{uuid.uuid4().hex}.{ext}"
                )

                f.save(
                    os.path.join(
                        app.config[
                            "UPLOAD_FOLDER"
                        ],
                        unique_name
                    )
                )

                db.session.add(
                    Photo(
                        filename=unique_name,
                        memory_id=memory.id
                    )
                )

        db.session.commit()

        flash(
            "Memory updated."
        )

        return redirect(
            url_for("admin_dashboard")
        )

    return render_template(
        "edit.html",
        memory=memory
    )


# ============================================================
# DELETE MEMORY
# ============================================================

@app.route(
    "/admin/delete/<int:memory_id>",
    methods=["POST"]
)
@admin_required
def delete_memory(memory_id):

    memory = Memory.query.get_or_404(
        memory_id
    )

    for photo in memory.photos:

        path = os.path.join(
            app.config[
                "UPLOAD_FOLDER"
            ],
            photo.filename
        )

        if os.path.exists(path):

            os.remove(path)

        db.session.delete(
            photo
        )

    db.session.delete(
        memory
    )

    db.session.commit()

    return redirect(
        url_for("admin_dashboard")
    )


# ============================================================
# ADMIN MESSAGES
# ============================================================

@app.route(
    "/admin/messages",
    methods=["GET", "POST"]
)
@admin_required
def admin_messages():

    if request.method == "POST":

        body = request.form.get(
            "body",
            ""
        ).strip()

        if body:

            db.session.add(
                Message(
                    sender="admin",
                    body=body
                )
            )

            db.session.commit()

        return redirect(
            url_for("admin_messages")
        )

    thread = (
        Message.query
        .order_by(
            Message.created_at.asc()
        )
        .all()
    )

    return render_template(
        "admin_messages.html",
        thread=thread
    )


# ============================================================
# DELETE MESSAGE
# ============================================================

@app.route(
    "/admin/messages/delete/<int:message_id>",
    methods=["POST"]
)
@admin_required
def delete_message(message_id):

    msg = Message.query.get_or_404(
        message_id
    )

    db.session.delete(
        msg
    )

    db.session.commit()

    return redirect(
        url_for("admin_messages")
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )