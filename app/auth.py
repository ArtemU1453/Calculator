import sqlite3

def check_user(login,password):
    conn = sqlite3.connect("data/users.db")
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE login=? AND password=?",
                (login,password))

    return cur.fetchone() is not None
