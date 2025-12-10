# URL Shortener Service with Analytics

A FastAPI service to shorten long URLs, generate unique short codes, and track analytics (clicks, IP, User-Agent).

## Tech Stack

- **Backend**: FastAPI (Python)
- **Database**: SQLite with SQLAlchemy ORM
- **Server**: Uvicorn
- **Python**: 3.10+

## Project Structure

```
url-shortener/
├── app/
│   ├── __init__.py
│   └── main.py          (All API code and database models)
├── venv/                (Virtual environment)
├── requirements.txt
├── README.md
├── postman_collection.json
├── .gitignore
└── url_shortener.db     