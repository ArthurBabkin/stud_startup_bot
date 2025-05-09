# StudStartupBot

**Startup Bot** is a Telegram bot built to support student startup projects by helping users navigate grant applications and improve their chances of success. It leverages advanced AI services (OpenAI, Deepseek, Mistral) and OCR capabilities to analyze and provide feedback on grant applications.A Telegram bot for startup-related tasks, leveraging AI services (OpenAI, Deepseek, Mistral) and OCR capabilities. The bot uses PostgreSQL for data storage and is designed for easy deployment with Docker Compose.

The bot is backed by a PostgreSQL database and is easily deployable using Docker Compose.

## What You Can Do with Startup Bot

- Ask questions about startup grants, eligibility, and application details.
- Submit your grant application for AI-powered review and feedback.
- Analyze scanned documents using OCR (powered by Mistral).
- Use the admin interface to manage users, review interactions, and track activity.

## Features

- Telegram bot with AI-powered responses.
- Supports multiple AI providers (OpenAI, Deepseek, Mistral OCR).
- Mistral OCR support for document processing.
- Admin management.
- PostgreSQL database backend.
- Telegram bot with AI-generated responses.
- Supports multiple AI providers:
  - OpenAI
  - Deepseek
  - Mistral (including OCR for document processing)
- PostgreSQL database backend.
- Proxy configuration to access OpenAI LLM models from Russia.
- Easy deployment with Docker Compose.

## Prerequisites

- [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/) (recommended)
- Alternatively: Python 3.11+ and PostgreSQL if running locally without Docker

## Setup & Deployment

### 1. Clone the Repository

```bash
git clone https://github.com/ArthurBabkin/stud_startup_bot.git
cd <your-project-directory>
```

### 2. Configure Environment Variables

Create a `.env` file in the project root with the following variables:

```
bot_token=YOUR_TELEGRAM_BOT_TOKEN
openai_key=YOUR_OPENAI_API_KEY
deepseek_key=YOUR_DEEPSEEK_API_KEY
assistant_id=YOUR_ASSISTANT_ID
mistral_key=YOUR_MISTRAL_API_KEY
mistral_key_backup=YOUR_MISTRAL_API_KEY_BACKUP
proxy_url=YOUR_PROXY_URL  # optional, to access OpenAI LLM models from Russia
admin_ids_str=1110163898  # comma-separated admin Telegram IDs
openai_model=gpt-4o-mini
deepseek_model=deepseek-chat
use_mistral_ocr=False
db_host=db
db_port=5432
db_name=stud_startup
db_user=studuser
db_password=studpass
```

> **Note:** If you use Docker Compose, the database variables should match those in `docker-compose.yml`.

### 3. Build and Start with Docker Compose

```bash
docker-compose up --build -d
```

- This will start both the PostgreSQL database and the bot.
- The bot will automatically run migrations on startup.

### 4. Check Logs

To see the bot logs:

```bash
docker logs stud_startup_bot
```

### 5. Stopping and Restarting

To stop the services:

```bash
docker-compose down
```

To restart:

```bash
docker-compose up -d
```
