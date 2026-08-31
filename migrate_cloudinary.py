"""
migrate_cloudinary.py
======================
One-time migration script.

What it does:
1. Adds the new `url` column to the existing `photo` table
   (if it doesn't already exist).
2. Finds every Photo row that still only has a local `filename`
   (no Cloudinary `url` yet).
3. Uploads that file from static/uploads/ to Cloudinary.
4. Saves the returned secure_url into the Photo's `url` column.

Run this ONCE, from the same folder as app.py:

    python migrate_cloudinary.py

Safe to re-run: it skips photos that already have a `url`,
and skips files that no longer exist on disk (prints a warning
instead of crashing).
"""

import os
import sqlite3

from dotenv import load_dotenv
load_dotenv()

# IMPORTANT: import bare `cloudinary` and call config() with the
# proxy BEFORE importing cloudinary.uploader. Per Cloudinary's own
# docs, the proxy is only picked up correctly if config() runs
# before that submodule is first imported anywhere in the process.
import cloudinary

cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
    secure=True,
    # Only set on PythonAnywhere via .env — required there so
    # uploads reach api.cloudinary.com through their proxy.
    api_proxy=os.environ.get("PYTHONANYWHERE_PROXY") or None
)

import cloudinary.uploader

from app import app, db, Photo, UPLOAD_FOLDER, BASE_DIR


DB_PATH = os.path.join(BASE_DIR, "site.db")


def ensure_url_column():
    """
    Adds the `url` column to the `photo` table if it's missing.
    Safe to run multiple times.
    """

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(photo)")
    columns = [row[1] for row in cursor.fetchall()]

    if "url" not in columns:
        print("Adding 'url' column to photo table...")
        cursor.execute("ALTER TABLE photo ADD COLUMN url VARCHAR(500)")
        conn.commit()
        print("Done.")
    else:
        print("'url' column already exists — skipping.")

    conn.close()


def migrate_photos():
    """
    Uploads every local photo (that doesn't have a Cloudinary
    url yet) to Cloudinary, and stores the resulting url.
    """

    with app.app_context():

        photos = Photo.query.filter(
            (Photo.url.is_(None)) & (Photo.filename.isnot(None))
        ).all()

        if not photos:
            print("No photos need migrating. Everything is already on Cloudinary.")
            return

        print(f"Found {len(photos)} photo(s) to migrate...")

        migrated = 0
        skipped = 0

        for photo in photos:

            local_path = os.path.join(UPLOAD_FOLDER, photo.filename)

            if not os.path.exists(local_path):
                print(f"  [SKIP] Photo id={photo.id} — file not found: {photo.filename}")
                skipped += 1
                continue

            try:
                result = cloudinary.uploader.upload(
                    local_path,
                    folder="merrychristmasmina",
                    quality="auto",
                    fetch_format="auto",
                    transformation=[
                        {"width": 1600, "crop": "limit"}
                    ]
                )

                photo.url = result["secure_url"]
                db.session.commit()

                migrated += 1
                print(f"  [OK] Photo id={photo.id} -> {photo.url}")

            except Exception as e:
                db.session.rollback()
                print(f"  [ERROR] Photo id={photo.id} failed: {e}")

        print()
        print(f"Migration complete. Migrated: {migrated}, Skipped: {skipped}")


if __name__ == "__main__":

    print("=" * 60)
    print("Cloudinary migration for merrychristmasmina")
    print("=" * 60)
    print()

    ensure_url_column()
    print()
    migrate_photos()

    print()
    print("You can now safely re-run app.py.")