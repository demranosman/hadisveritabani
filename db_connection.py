import os

import psycopg2


def load_dotenv(dotenv_path: str = ".env") -> None:
    if not os.path.exists(dotenv_path):
        return

    with open(dotenv_path, encoding="utf-8") as dotenv_file:
        for raw_line in dotenv_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key and key not in os.environ:
                os.environ[key] = value


def get_connection():
    load_dotenv()

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url)

    password = os.getenv("PGPASSWORD")
    if not password:
        raise RuntimeError(
            "PostgreSQL şifresi bulunamadı. .env içine PGPASSWORD yazın veya DATABASE_URL ayarlayın."
        )

    return psycopg2.connect(
        dbname=os.getenv("PGDATABASE", "hadisdb"),
        user=os.getenv("PGUSER", "postgres"),
        password=password,
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
    )