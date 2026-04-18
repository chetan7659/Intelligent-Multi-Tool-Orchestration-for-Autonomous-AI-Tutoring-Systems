"""Quick test to check auth.users and FK."""
import asyncio
from sqlalchemy import text
from app.database import AsyncSessionLocal

async def test():
    async with AsyncSessionLocal() as s:
        # Check auth.users
        try:
            r = await s.execute(text("SELECT id, email FROM auth.users LIMIT 5"))
            users = r.fetchall()
            print(f"auth.users found: {len(users)}")
            for u in users:
                print(f"  id={u[0]}  email={u[1]}")
        except Exception as e:
            print(f"Cannot read auth.users: {e}")

        # Check existing rows in conversation_sessions
        try:
            r2 = await s.execute(text("SELECT count(*) FROM conversation_sessions"))
            print(f"conversation_sessions rows: {r2.scalar()}")
        except Exception as e:
            print(f"Cannot read sessions: {e}")

        # Check FK constraint
        try:
            r3 = await s.execute(text("""
                SELECT conname, confrelid::regclass 
                FROM pg_constraint 
                WHERE conrelid = 'public.conversation_sessions'::regclass 
                  AND contype = 'f'
            """))
            for row in r3.fetchall():
                print(f"FK constraint: {row[0]} -> {row[1]}")
        except Exception as e:
            print(f"Cannot check constraints: {e}")

asyncio.run(test())
