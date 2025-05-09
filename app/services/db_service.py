import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timedelta
import math
import os

# Constants for limits
LIMIT_RESET_DAYS = 2  # Number of days before limit reset
ASK_LIMIT = 5         # Limit for /ask command usage
PDF_LIMIT = 100       # Limit for PDF checks (1 = allowed once)

# -------------------------------------------------
#  Basic helper
# -------------------------------------------------

@contextmanager
def get_db():
    """Context manager for safe PostgreSQL connection handling."""
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME", "stud_startup"),
        user=os.getenv("DB_USER", "studuser"),
        password=os.getenv("DB_PASSWORD", "studpass"),
        host=os.getenv("DB_HOST", "db"),
        port=os.getenv("DB_PORT", "5432")
    )
    conn.autocommit = False
    try:
        yield conn
    finally:
        conn.close()

# -------------------------------------------------
#  Initialization (table creation)
# -------------------------------------------------

def init_db() -> None:
    """Creates all required tables if they do not exist yet."""
    with get_db() as conn:
        cur = conn.cursor()

        # Telegram users
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id                BIGINT PRIMARY KEY,
                username          TEXT,
                first_name        TEXT,
                last_name         TEXT,
                ask_count         INTEGER DEFAULT 0,
                pdf_check_done    INTEGER DEFAULT 0,
                limits_reset_at   TIMESTAMP DEFAULT NULL
            )
            """
        )

        # Messages between bot and user
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                message_id     SERIAL PRIMARY KEY,
                user_id        BIGINT,
                timestamp      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                message_input  TEXT,
                message_answer TEXT,
                is_feedback    BOOLEAN DEFAULT FALSE,
                feedback_text  TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            """
        )

        # Checked PDF applications of the user
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS pdfs (
                pdf_id         SERIAL PRIMARY KEY,
                user_id        BIGINT,
                timestamp      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                pdf_input      BYTEA,
                message_answer TEXT,
                is_feedback    BOOLEAN DEFAULT FALSE,
                feedback_text  TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            """
        )

        # Mapping Telegram user → OpenAI thread
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS threads (
                user_id   BIGINT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            """
        )

        conn.commit()

# -------------------------------------------------
#  CRUD functions for users / messages / threads
# -------------------------------------------------

def add_user(user_id: int, username: Optional[str] = None, first_name: Optional[str] = None, last_name: Optional[str] = None) -> None:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE id = %s", (user_id,))
        exists = cur.fetchone()

        if exists:
            # Update name and username, but DO NOT touch limits
            cur.execute(
                """
                UPDATE users SET username = %s, first_name = %s, last_name = %s
                WHERE id = %s
                """,
                (username, first_name, last_name, user_id)
            )
        else:
            # Create with default limits
            cur.execute(
                """
                INSERT INTO users (id, username, first_name, last_name, ask_count, pdf_check_done, limits_reset_at)
                VALUES (%s, %s, %s, %s, 0, 0, %s)
                """,
                (user_id, username, first_name, last_name, datetime.now())
            )

        conn.commit()

def save_message(user_id: int, message_input: str, message_answer: str = None) -> int:
    """Saves the user's message and the bot's reply (if any)."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO messages (user_id, message_input, message_answer)
            VALUES (%s, %s, %s) RETURNING message_id
            """,
            (user_id, message_input, message_answer),
        )
        message_id = cur.fetchone()[0]
        conn.commit()
        return message_id

def get_message_stats() -> Tuple[int, int]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM messages")
        total_messages = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT user_id) FROM messages")
        unique_users = cur.fetchone()[0]
        return total_messages, unique_users

def get_thread(user_id: int) -> Optional[str]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT thread_id FROM threads WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        return row["thread_id"] if row else None

def save_thread(user_id: int, thread_id: str) -> None:
    with get_db() as conn:
        cur = conn.cursor()
        # ON CONFLICT DO UPDATE is equivalent to INSERT OR REPLACE in SQLite
        cur.execute(
            """
            INSERT INTO threads (user_id, thread_id) 
            VALUES (%s, %s)
            ON CONFLICT (user_id) DO UPDATE SET thread_id = EXCLUDED.thread_id
            """,
            (user_id, thread_id),
        )
        conn.commit()

def save_pdf(user_id: int, pdf_input: bytes, message_answer: str = None) -> int:
    """Saves the user's PDF and the bot's reply (if any)."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO pdfs (user_id, pdf_input, message_answer)
            VALUES (%s, %s, %s) RETURNING pdf_id
            """,
            (user_id, psycopg2.Binary(pdf_input), message_answer),
        )
        pdf_id = cur.fetchone()[0]
        conn.commit()
        return pdf_id

def update_message_feedback(message_id: int, is_feedback: bool, feedback_text: str) -> None:
    """Updates feedback for a message."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE messages SET is_feedback = %s, feedback_text = %s WHERE message_id = %s
            """,
            (is_feedback, feedback_text, message_id),
        )
        conn.commit()

def update_pdf_feedback(pdf_id: int, is_feedback: bool, feedback_text: str) -> None:
    """Updates feedback for a PDF record."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE pdfs SET is_feedback = %s, feedback_text = %s WHERE pdf_id = %s
            """,
            (is_feedback, feedback_text, pdf_id),
        )
        conn.commit()

# -------------------------------------------------
#  Usage limits
# -------------------------------------------------

def get_user_limits(user_id: int) -> Tuple[int, int]:
    now = datetime.now()

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT ask_count, pdf_check_done, limits_reset_at FROM users WHERE id = %s",
            (user_id,)
        )
        row = cur.fetchone()

        if not row:
            return (0, 0)

        # If the field is empty — reset limits
        last_reset_str = row["limits_reset_at"]
        if not last_reset_str:
            cur = conn.cursor()
            cur.execute("""
                UPDATE users
                SET ask_count = 0,
                    pdf_check_done = 0,
                    limits_reset_at = %s
                WHERE id = %s
            """, (now, user_id))
            conn.commit()
            return (0, 0)

        # Compare last reset date with current date
        last_reset = last_reset_str
        if now - last_reset > timedelta(days=LIMIT_RESET_DAYS):
            cur = conn.cursor()
            cur.execute("""
                UPDATE users
                SET ask_count = 0,
                    pdf_check_done = 0,
                    limits_reset_at = %s
                WHERE id = %s
            """, (now, user_id))
            conn.commit()
            return (0, 0)

        return (row["ask_count"], row["pdf_check_done"])

def increment_ask(user_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET ask_count = ask_count + 1 WHERE id = %s",
            (user_id,)
        )
        conn.commit()

def mark_pdf_used(user_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET pdf_check_done = pdf_check_done + 1 WHERE id = %s",
            (user_id,)
        )
        conn.commit()

# -------------------------------------------------
#  Search by username
# -------------------------------------------------

def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT * FROM users WHERE username = %s",
            (username.lstrip("@"),)  # remove @ in case it was provided
        )
        row = cur.fetchone()
        return dict(row) if row else None

def delete_user(user_id: int) -> bool:
    """Deletes a user and all related data."""
    with get_db() as conn:
        try:
            cur = conn.cursor()
            # Check if user exists
            cur.execute("SELECT 1 FROM users WHERE id = %s", (user_id,))
            user_exists = cur.fetchone()
            if not user_exists:
                return False
                
            # Delete related messages
            cur.execute("DELETE FROM messages WHERE user_id = %s", (user_id,))
            
            # Delete related thread
            cur.execute("DELETE FROM threads WHERE user_id = %s", (user_id,))
            
            # Delete PDF records
            cur.execute("DELETE FROM pdfs WHERE user_id = %s", (user_id,))
            
            # Delete user
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            return False

def get_time_until_reset(user_id: int) -> Optional[int]:
    """Returns the number of hours until limits reset, or None if limits are already reset."""
    now = datetime.now()
    
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT limits_reset_at FROM users WHERE id = %s",
            (user_id,)
        )
        row = cur.fetchone()
        
        if not row or not row["limits_reset_at"]:
            return None
        
        last_reset = row["limits_reset_at"]
        next_reset = last_reset + timedelta(days=LIMIT_RESET_DAYS)
        
        if now >= next_reset:
            return None  # Limits should already be reset
        
        hours_remaining = (next_reset - now).total_seconds() / 3600
        return math.ceil(hours_remaining)  # Round up to the nearest hour
