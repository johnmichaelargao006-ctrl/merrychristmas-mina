"""
fix_photo_schema.py
=====================
Fixes the `photo` table so that `filename` allows NULL values.

Why this is needed:
  SQLite's `ALTER TABLE ... ADD COLUMN` (used in migrate_cloudinary.py)
  can add a new column, but it CANNOT change an existing column's
  NOT NULL constraint. The original `filename` column was created
  as NOT NULL, so new Cloudinary-only photos (which have no local
  filename) fail to insert with:

      IntegrityError: NOT NULL constraint failed: photo.filename

  This script rebuilds the `photo` table with `filename` now
  nullable, copying all existing rows (including any already-
  migrated Cloudinary urls) across safely.

Run this ONCE, from the same folder as app.py:

    python fix_photo_schema.py

Safe to re-run — it checks whether the fix is already applied
before doing anything.
"""

import os
import sqlite3

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "site.db")


def filename_is_nullable(cursor):
    cursor.execute("PRAGMA table_info(photo)")
    for cid, name, coltype, notnull, dflt, pk in cursor.fetchall():
        if name == "filename":
            # notnull == 1 means NOT NULL is still enforced
            return notnull == 0
    return False


def fix_schema():

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if filename_is_nullable(cursor):
        print("photo.filename is already nullable — nothing to do.")
        conn.close()
        return

    print("Rebuilding photo table so filename allows NULL...")

    cursor.execute("PRAGMA foreign_keys=off")

    # 1. Create the new table with the corrected schema.
    cursor.execute("""
        CREATE TABLE photo_new (
            id INTEGER PRIMARY KEY,
            filename VARCHAR(300),
            url VARCHAR(500),
            memory_id INTEGER NOT NULL,
            FOREIGN KEY (memory_id) REFERENCES memory (id)
        )
    """)

    # 2. Copy all existing data across.
    cursor.execute("""
        INSERT INTO photo_new (id, filename, url, memory_id)
        SELECT id, filename, url, memory_id FROM photo
    """)

    # 3. Swap the tables.
    cursor.execute("DROP TABLE photo")
    cursor.execute("ALTER TABLE photo_new RENAME TO photo")

    cursor.execute("PRAGMA foreign_keys=on")

    conn.commit()

    # Sanity check.
    cursor.execute("SELECT COUNT(*) FROM photo")
    count = cursor.fetchone()[0]

    conn.close()

    print(f"Done. photo table rebuilt — {count} row(s) preserved.")
    print("filename is now nullable. You can re-run app.py.")


if __name__ == "__main__":
    print("=" * 60)
    print("Fixing photo.filename NOT NULL constraint")
    print("=" * 60)
    print()
    fix_schema()