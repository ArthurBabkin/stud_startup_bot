import sqlite3
from contextlib import contextmanager
from typing import Optional, Tuple
from datetime import datetime, timedelta
import math

# Путь к файлу SQLite. Меняйте при необходимости
DB_PATH = "messages.db"

# Константы для лимитов
LIMIT_RESET_DAYS = 0.01  # Количество дней до сброса лимита
ASK_LIMIT = 100  # Лимит использования /ask команды
PDF_LIMIT = 100  # Лимит проверки PDF (1 = один раз разрешено)

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
                id                INTEGER PRIMARY KEY,
                username          TEXT,
                first_name        TEXT,
                last_name         TEXT,
                ask_count         INTEGER DEFAULT 0,
                pdf_check_done    INTEGER DEFAULT 0,
                limits_reset_at   TEXT DEFAULT NULL
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
#  CRUD‑функции для users / messages / threads
# -------------------------------------------------

def add_user(user_id: int, username: Optional[str] = None, first_name: Optional[str] = None, last_name: Optional[str] = None) -> None:
    with get_db() as conn:
        cur = conn.cursor()
        exists = cur.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone()

        if exists:
            # обновим имя и username, но НЕ трогаем лимиты
            cur.execute(
                """
                UPDATE users SET username = ?, first_name = ?, last_name = ?
                WHERE id = ?
                """,
                (username, first_name, last_name, user_id)
            )
        else:
            # создаём с лимитами по умолчанию
            cur.execute(
                """
                INSERT INTO users (id, username, first_name, last_name, ask_count, pdf_check_done, limits_reset_at)
                VALUES (?, ?, ?, ?, 0, 0, ?)
                """,
                (user_id, username, first_name, last_name, datetime.now().isoformat())
            )

        conn.commit()

def save_message(user_id: int, message_text: str) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO messages (user_id, message_text) VALUES (?, ?)
            """,
            (user_id, message_text),
        )
        conn.commit()

def get_message_stats() -> Tuple[int, int]:
    with get_db() as conn:
        cur = conn.cursor()
        total_messages = cur.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        unique_users = cur.execute("SELECT COUNT(DISTINCT user_id) FROM messages").fetchone()[0]
        return total_messages, unique_users

def get_thread(user_id: int) -> Optional[str]:
    with get_db() as conn:
        row = conn.execute("SELECT thread_id FROM threads WHERE user_id = ?", (user_id,)).fetchone()
        return row["thread_id"] if row else None

def save_thread(user_id: int, thread_id: str) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO threads (user_id, thread_id) VALUES (?, ?)
            """,
            (user_id, thread_id),
        )
        conn.commit()

# -------------------------------------------------
#  Ограничения по использованию
# -------------------------------------------------

def get_user_limits(user_id: int) -> Tuple[int, int]:
    now = datetime.now()

    with get_db() as conn:
        row = conn.execute(
            "SELECT ask_count, pdf_check_done, limits_reset_at FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if not row:
            return (0, 0)

        # если поле пустое — сбрасываем лимиты
        last_reset_str = row["limits_reset_at"]
        if not last_reset_str:
            conn.execute("""
                UPDATE users
                SET ask_count = 0,
                    pdf_check_done = 0,
                    limits_reset_at = ?
                WHERE id = ?
            """, (now.isoformat(), user_id))
            conn.commit()
            return (0, 0)

        # сравниваем дату последнего сброса с текущей
        last_reset = datetime.fromisoformat(last_reset_str)
        if now - last_reset > timedelta(days=LIMIT_RESET_DAYS):
            conn.execute("""
                UPDATE users
                SET ask_count = 0,
                    pdf_check_done = 0,
                    limits_reset_at = ?
                WHERE id = ?
            """, (now.isoformat(), user_id))
            conn.commit()
            return (0, 0)

        return (row["ask_count"], row["pdf_check_done"])

def increment_ask(user_id: int):
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET ask_count = ask_count + 1 WHERE id = ?",
            (user_id,)
        )
        conn.commit()

def mark_pdf_used(user_id: int):
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET pdf_check_done = pdf_check_done + 1 WHERE id = ?",
            (user_id,)
        )
        conn.commit()

# -------------------------------------------------
#  Поиск по username
# -------------------------------------------------

def get_user_by_username(username: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username.lstrip("@"),)  # убираем @ на случай если передали с ним
        ).fetchone()
        return dict(row) if row else None

def delete_user(user_id: int) -> bool:
    """Удаляет пользователя и все связанные с ним данные."""
    with get_db() as conn:
        try:
            # Проверяем, существует ли пользователь
            user_exists = conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone()
            if not user_exists:
                return False
                
            # Удаляем связанные сообщения
            conn.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
            
            # Удаляем связанный thread
            conn.execute("DELETE FROM threads WHERE user_id = ?", (user_id,))
            
            # Удаляем пользователя
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False

def get_time_until_reset(user_id: int) -> Optional[int]:
    """Возвращает количество часов до сброса лимитов или None если лимиты уже сброшены."""
    now = datetime.now()
    
    with get_db() as conn:
        row = conn.execute(
            "SELECT limits_reset_at FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        
        if not row or not row["limits_reset_at"]:
            return None
        
        last_reset = datetime.fromisoformat(row["limits_reset_at"])
        next_reset = last_reset + timedelta(days=LIMIT_RESET_DAYS)
        
        if now >= next_reset:
            return None  # Лимиты уже должны быть сброшены
        
        hours_remaining = (next_reset - now).total_seconds() / 3600
        return math.ceil(hours_remaining)  # Округляем вверх до ближайшего часа
