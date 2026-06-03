import aiosqlite
from config import settings

class AsyncDatabase:
    def __init__(self):
        self.db_path = settings.DATABASE_URL

    async def fetch_one(self, query, params=()):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            return await cursor.fetchone()

    async def fetch_all(self, query, params=()):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            return await cursor.fetchall()

    async def execute(self, query, params=()):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(query, params)
            await db.commit()

db = AsyncDatabase()