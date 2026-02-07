import sqlite3

HISTORY_DB_PATH = "data/history.db"


def init_history_db(db_path=HISTORY_DB_PATH):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS history(
            id INTEGER PRIMARY KEY,
            timestamp TEXT,
            stock_number TEXT,
            material_code TEXT,
            material_width REAL,
            useful_width REAL,
            big_roll_length REAL,
            roll_width REAL,
            roll_length REAL,
            main_count INTEGER,
            additional_width REAL,
            total_rolls INTEGER,
            used_length_m REAL,
            surplus_rolls INTEGER,
            surplus_main_rolls INTEGER,
            surplus_additional_rolls INTEGER,
            total_area REAL,
            useful_area REAL,
            waste_area REAL,
            waste_percent REAL
        )
        """
    )
    cur.execute("PRAGMA table_info(history)")
    existing = {row[1] for row in cur.fetchall()}
    if "big_roll_length" not in existing:
        cur.execute("ALTER TABLE history ADD COLUMN big_roll_length REAL")
    if "stock_number" not in existing:
        cur.execute("ALTER TABLE history ADD COLUMN stock_number TEXT")
    if "material_code" not in existing:
        cur.execute("ALTER TABLE history ADD COLUMN material_code TEXT")
    if "surplus_rolls" not in existing:
        cur.execute("ALTER TABLE history ADD COLUMN surplus_rolls INTEGER")
    if "surplus_main_rolls" not in existing:
        cur.execute("ALTER TABLE history ADD COLUMN surplus_main_rolls INTEGER")
    if "surplus_additional_rolls" not in existing:
        cur.execute("ALTER TABLE history ADD COLUMN surplus_additional_rolls INTEGER")
    if "used_length_m" not in existing:
        cur.execute("ALTER TABLE history ADD COLUMN used_length_m REAL")
    conn.commit()
    conn.close()


def insert_history(record, db_path=HISTORY_DB_PATH):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO history(
            timestamp, stock_number, material_code,
            material_width, useful_width, big_roll_length, roll_width, roll_length,
            main_count, additional_width, total_rolls, used_length_m, surplus_rolls,
            surplus_main_rolls, surplus_additional_rolls, total_area,
            useful_area, waste_area, waste_percent
        )
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            record["timestamp"],
            record["stock_number"],
            record["material_code"],
            record["material_width"],
            record["useful_width"],
            record["big_roll_length"],
            record["roll_width"],
            record["roll_length"],
            record["main_count"],
            record["additional_width"],
            record["total_rolls"],
            record["used_length_m"],
            record["surplus_rolls"],
            record["surplus_main_rolls"],
            record["surplus_additional_rolls"],
            record["total_area"],
            record["useful_area"],
            record["waste_area"],
            record["waste_percent"],
        ),
    )
    conn.commit()
    conn.close()


def fetch_history(limit=50, db_path=HISTORY_DB_PATH):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT timestamp, stock_number, material_code,
               material_width, roll_width, useful_area, waste_percent,
               surplus_main_rolls, surplus_additional_rolls, used_length_m
        FROM history
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def count_history(db_path=HISTORY_DB_PATH):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM history")
    count = cur.fetchone()[0]
    conn.close()
    return count


def clear_history(db_path=HISTORY_DB_PATH):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM history")
    conn.commit()
    conn.close()
