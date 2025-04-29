-- Миграция базы данных: изменение типа ID с INTEGER на BIGINT
-- Данный скрипт выполняет миграцию с сохранением данных

-- Создаем временные таблицы для хранения данных
BEGIN;

-- Создаем временную таблицу для users
CREATE TABLE users_temp (
    id                BIGINT PRIMARY KEY,
    username          TEXT,
    first_name        TEXT,
    last_name         TEXT,
    ask_count         INTEGER DEFAULT 0,
    pdf_check_done    INTEGER DEFAULT 0,
    limits_reset_at   TIMESTAMP DEFAULT NULL
);

-- Создаем временную таблицу для messages
CREATE TABLE messages_temp (
    message_id     SERIAL PRIMARY KEY,
    user_id        BIGINT,
    timestamp      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    message_input  TEXT,
    message_answer TEXT,
    is_feedback    BOOLEAN DEFAULT FALSE,
    feedback_text  TEXT,
    FOREIGN KEY (user_id) REFERENCES users_temp (id)
);

-- Создаем временную таблицу для pdfs
CREATE TABLE pdfs_temp (
    pdf_id         SERIAL PRIMARY KEY,
    user_id        BIGINT,
    timestamp      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pdf_input      BYTEA,
    message_answer TEXT,
    is_feedback    BOOLEAN DEFAULT FALSE,
    feedback_text  TEXT,
    FOREIGN KEY (user_id) REFERENCES users_temp (id)
);

-- Создаем временную таблицу для threads
CREATE TABLE threads_temp (
    user_id   BIGINT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users_temp (id)
);

-- Переносим данные в временные таблицы
INSERT INTO users_temp (id, username, first_name, last_name, ask_count, pdf_check_done, limits_reset_at)
SELECT id, username, first_name, last_name, ask_count, pdf_check_done, limits_reset_at FROM users;

INSERT INTO messages_temp (message_id, user_id, timestamp, message_input, message_answer, is_feedback, feedback_text)
SELECT message_id, user_id, timestamp, message_input, message_answer, is_feedback, feedback_text FROM messages;

INSERT INTO pdfs_temp (pdf_id, user_id, timestamp, pdf_input, message_answer, is_feedback, feedback_text)
SELECT pdf_id, user_id, timestamp, pdf_input, message_answer, is_feedback, feedback_text FROM pdfs;

INSERT INTO threads_temp (user_id, thread_id)
SELECT user_id, thread_id FROM threads;

-- Удаляем старые таблицы
DROP TABLE threads;
DROP TABLE pdfs;
DROP TABLE messages;
DROP TABLE users;

-- Переименовываем временные таблицы
ALTER TABLE users_temp RENAME TO users;
ALTER TABLE messages_temp RENAME TO messages;
ALTER TABLE pdfs_temp RENAME TO pdfs;
ALTER TABLE threads_temp RENAME TO threads;

-- Восстанавливаем последовательности для SERIAL полей
SELECT setval(pg_get_serial_sequence('messages', 'message_id'), coalesce(max(message_id), 1), max(message_id) IS NOT NULL) FROM messages;
SELECT setval(pg_get_serial_sequence('pdfs', 'pdf_id'), coalesce(max(pdf_id), 1), max(pdf_id) IS NOT NULL) FROM pdfs;

COMMIT; 