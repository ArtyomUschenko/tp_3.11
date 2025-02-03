import asyncpg
from date.config import POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB

async def create_connection():
    """Создает подключение к базе данных."""
    return await asyncpg.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        database=POSTGRES_DB,
    )

async def create_tables():
    """Создает таблицы в базе данных, если они не существуют."""
    conn = await create_connection()
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS support_requests (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            name TEXT NOT NULL,
            email TEXT NULL,
            message TEXT NOT NULL,
            admin_id BIGINT NULL,
            admin_name TEXT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    await conn.close()