import sqlite3
from typing import List, Dict

DB_PATH = "bot_database.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Пользователи
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            data TEXT
        )
    """)

    # Задания
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            creator_id INTEGER,
            data TEXT
        )
    """)

    # Замороженные задания
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS frozen_tasks (
            id TEXT PRIMARY KEY,
            data TEXT
        )
    """)

    # Админские задания
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_tasks (
            id TEXT PRIMARY KEY,
            data TEXT
        )
    """)

    # Донаты
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal TEXT,
            amount TEXT,
            description TEXT,
            donors TEXT,
            reports TEXT
        )
    """)

    # Жалобы пользователей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_reports (
            user_id INTEGER PRIMARY KEY,
            last_report_time TEXT
        )
    """)

    # Подписчики анонсов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS announcement_subscribers (
            user_id INTEGER PRIMARY KEY
        )
    """)

    conn.commit()
    conn.close()


# ------------------ Пользователи ------------------

def get_user(user_id: int) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT data FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return eval(row[0]) if row else None

def create_user(user_id: int, data: dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (user_id, data) VALUES (?, ?)", (user_id, str(data)))
    conn.commit()
    conn.close()

def update_user(user_id: int, updates: dict):
    user = get_user(user_id)
    if user:
        user.update(updates)
        create_user(user_id, user)

def get_all_users() -> Dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, data FROM users")
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: eval(row[1]) for row in rows}

# ------------------ Задания ------------------

def add_task(task: dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tasks (id, creator_id, data) VALUES (?, ?, ?)",
                   (task['id'], task['creator_id'], str(task)))
    conn.commit()
    conn.close()

def remove_task(task_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

def get_task(task_id: str) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT data FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()
    return eval(row[0]) if row else None

def get_available_tasks(user_id: int, limit: int = 10) -> List:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT data FROM tasks WHERE creator_id != ? LIMIT ?", (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [eval(row[0]) for row in rows]

# ------------------ Замороженные задания ------------------

def freeze_task(task_id: str, data: dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO frozen_tasks (id, data) VALUES (?, ?)", (task_id, str(data)))
    conn.commit()
    conn.close()

def unfreeze_task(task_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM frozen_tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

def get_frozen_task(task_id: str) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT data FROM frozen_tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()
    return eval(row[0]) if row else None

# ------------------ Ежедневная очистка ------------------

def clear_daily_data():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks")
    conn.commit()
    cursor.execute("SELECT user_id, data FROM users")
    rows = cursor.fetchall()
    for user_id, data_str in rows:
        data = eval(data_str)
        data['daily_claimed'] = False
        data['trixiki'] = 0
        data['daily_tasks_created'] = {'likes': 0, 'comments': 0, 'follows': 0}
        cursor.execute("UPDATE users SET data = ? WHERE user_id = ?", (str(data), user_id))
    conn.commit()
    conn.close()

# ------------------ Инициализация ------------------

if __name__ == "__main__":
    init_db()
