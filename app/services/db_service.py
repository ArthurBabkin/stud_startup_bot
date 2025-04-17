import sqlite3
from contextlib import contextmanager
from typing import Optional, Tuple

# Путь к файлу SQLite. Меняйте при необходимости
DB_PATH = "messages.db"

# -------------------------------------------------
#  Базовый helper
# -------------------------------------------------

@contextmanager
def get_db():
    """Context manager для безопасной работы с соединением."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# -------------------------------------------------
#  Инициализация (создание таблиц)
# -------------------------------------------------

def init_db() -> None:
    """Создаёт все необходимые таблицы, если их ещё нет."""
    with get_db() as conn:
        cur = conn.cursor()

        # Пользователи Telegram
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY,
                username   TEXT,
                first_name TEXT,
                last_name  TEXT
            )
            """
        )

        # Сохранённые сообщения бота ↔ пользователь
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id           INTEGER PRIMARY KEY,
                user_id      INTEGER,
                message_text TEXT,
                timestamp    DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            """
        )

        # Mapping Telegram‑user → OpenAI‑thread
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS threads (
                user_id   INTEGER PRIMARY KEY,
                thread_id TEXT NOT NULL
            )
            """
        )

        conn.commit()

# -------------------------------------------------
#  CRUD‑функции для users / messages
# -------------------------------------------------

def add_user(user_id: int, username: Optional[str] = None, first_name: Optional[str] = None, last_name: Optional[str] = None) -> None:
    """Добавляет/обновляет запись о пользователе."""
    with get_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO users (id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, username, first_name, last_name),
        )
        conn.commit()

def save_message(user_id: int, message_text: str) -> None:
    """Логирует сообщение пользователя или бота."""
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO messages (user_id, message_text) VALUES (?, ?)
            """,
            (user_id, message_text),
        )
        conn.commit()

def get_message_stats() -> Tuple[int, int]:
    """Возвращает (total_messages, unique_users)."""
    with get_db() as conn:
        cur = conn.cursor()
        total_messages = cur.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        unique_users = cur.execute("SELECT COUNT(DISTINCT user_id) FROM messages").fetchone()[0]
        return total_messages, unique_users

# -------------------------------------------------
#  Threads helpers (OpenAI Assistants API)
# -------------------------------------------------

def get_thread(user_id: int) -> Optional[str]:
    """Вернуть сохранённый thread_id (если уже есть)."""
    with get_db() as conn:
        cur = conn.execute("SELECT thread_id FROM threads WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return row["thread_id"] if row else None

def save_thread(user_id: int, thread_id: str) -> None:
    """Сохраняет сопоставление Telegram‑user → OpenAI‑thread."""
    with get_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO threads (user_id, thread_id) VALUES (?, ?)
            """,
            (user_id, thread_id),
        )
        conn.commit()

# -------------------------------------------------
#  Сервисная функция: вызов при запуске бота
# -------------------------------------------------

# Вызывайте init_db() в app/main.py, чтобы гарантировать существование таблиц
