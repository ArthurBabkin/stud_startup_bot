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
- Easy deployment with Docker Compose.

## Prerequisites

- [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/) (recommended)
- Alternatively: Python 3.11+ and PostgreSQL if running locally without Docker

## Project Structure

```text
stud_startup_bot/
├── app/                       # Main application code
│   ├── main.py                # Entry point for the bot
│   ├── router.py              # Telegram bot routing and command registration
│   ├── config.py              # Configuration and environment variable management
│   ├── handlers/              # Telegram bot handlers
│   │   ├── user.py            # User interaction handlers
│   │   ├── admin.py           # Admin command handlers
│   │   ├── startup.py         # Startup-specific logic and handlers
│   │   └── states.py          # State management for conversations
│   └── services/              # Service modules
│       ├── db_service.py      # Database access and queries
│       ├── openai_service.py  # Integration with OpenAI API (ChatGPT and DeepSeek models)
│       ├── ocr.py             # Mistral OCR logic
│       └── constants.py       # Constants
├── application_files/         # Uploaded and processed application documents (PDFs, etc.)
├── static/                    # Static files
│   ├── privacy/               # Privacy policy and user agreement PDFs
│   └── photos/                # Images and screenshots for the bot
├── keys/                      # Key files for deployment or encryption
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Docker build instructions
├── docker-compose.yml         # Docker Compose configuration
├── .env                       # Environment variables (not committed)
├── .gitignore                 # Git ignore rules
├── .dockerignore              # Docker ignore rules
└── README.md                  # Project documentation (this file)
```

**Descriptions:**

- **app/**: Main source code for the bot, including entry point, configuration, handlers, and service modules.
- **application_files/**: User-uploaded and processed documents (e.g., grant applications).
- **static/**: Static resources, including privacy documents and images.
- **keys/**: Key files for deployment or encryption (do not share publicly).
- **requirements.txt**: Python dependencies.
- **Dockerfile** and **docker-compose.yml**: For containerized deployment.
- **.env**: Environment variables (should be created by the user, not committed).
- **.gitignore** and **.dockerignore**: Ignore rules for Git and Docker.
- **README.md**: Project documentation.

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
proxy_url=YOUR_PROXY_URL  # optional
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
