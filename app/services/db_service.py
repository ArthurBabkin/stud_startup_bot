import sqlite3
from app.config import config

# Создание подключения к базе данных
def get_db_connection():
    conn = sqlite3.connect('messages.db')
    conn.row_factory = sqlite3.Row  # Для удобства работы с результатами
    return conn

# Создание таблиц (если еще не созданы)
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Создаем таблицу для хранения пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT
        )
    ''')

    # Создаем таблицу для истории сообщений
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            message_text TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    conn.commit()
    conn.close()

# Добавление нового пользователя в базу данных
def add_user(user_id, username, first_name, last_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (id, username, first_name, last_name) 
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, first_name, last_name))
    conn.commit()
    conn.close()

# Сохранение сообщений
def save_message(user_id, message_text):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO messages (user_id, message_text)
        VALUES (?, ?)
    ''', (user_id, message_text))
    conn.commit()
    conn.close()

# Получение статистики по сообщениям
def get_message_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM messages')
    total_messages = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(DISTINCT user_id) FROM messages')
    unique_users = cursor.fetchone()[0]
    conn.close()
    return total_messages, unique_users
