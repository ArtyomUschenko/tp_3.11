import asyncpg
from date.config import POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
from contextlib import asynccontextmanager

#Создает подключение к базе данных
async def create_connection():
    return await asyncpg.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        database=POSTGRES_DB,
    )

# Добавляем контекстный менеджер для соединения с БД
@asynccontextmanager
async def get_connection():
    # Контекстный менеджер для работы с БД
    conn = await create_connection()
    try:
        yield conn
    finally:
        await conn.close()

#Создает таблицы в базе данных, если они не существуют
async def create_tables():
    async with get_connection() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS support_requests (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NULL,
                user_username TEXT NULL,
                name TEXT NULL,
                email TEXT NULL,
                message TEXT NULL,
                admin_id BIGINT NULL,
                admin_name TEXT NULL,
                document_id TEXT,
                photo_id TEXT,
                document_path TEXT,
                photo_path TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS support_responses (
                id SERIAL PRIMARY KEY,
                request_id INT REFERENCES support_requests(id),
                admin_id BIGINT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)