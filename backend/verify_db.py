"""
End-to-end DB verification — confirms persistence is working.
"""
import asyncio
from sqlalchemy import text
from app.database import AsyncSessionLocal


async def verify():
    async with AsyncSessionLocal() as s:
        # Count rows in each table
        print("\n--- Row Counts ---")
        for table in ["conversation_sessions", "conversation_messages", "tool_execution_logs"]:
            r = await s.execute(text(f"SELECT count(*) FROM {table}"))
            print(f"  {table}: {r.scalar()} rows")

        # Show recent sessions
        r = await s.execute(text(
            "SELECT id::text, user_id::text, title, message_count, tools_used, created_at "
            "FROM conversation_sessions ORDER BY created_at DESC LIMIT 5"
        ))
        print("\n--- Recent Sessions ---")
        for row in r.fetchall():
            print(f"  id={str(row[0])[:8]}... user={str(row[1])[:8]}... title={row[2]} msgs={row[3]} tools={row[4]}")

        # Show recent messages
        r = await s.execute(text(
            "SELECT id::text, session_id::text, role, LEFT(content, 60) as content_preview, tool_used, created_at "
            "FROM conversation_messages ORDER BY created_at DESC LIMIT 10"
        ))
        print("\n--- Recent Messages ---")
        for row in r.fetchall():
            print(f"  [{row[2]:9s}] content={row[3][:50]:<50s} tool={row[4]}")

        # Show recent tool logs
        r = await s.execute(text(
            "SELECT id::text, message_id::text, tool_name, success, execution_time_ms, created_at "
            "FROM tool_execution_logs ORDER BY created_at DESC LIMIT 5"
        ))
        print("\n--- Recent Tool Logs ---")
        for row in r.fetchall():
            msg_link = str(row[1])[:8] + "..." if row[1] else "NULL"
            print(f"  tool={row[2]} success={row[3]} time={row[4]}ms msg_id={msg_link}")

        # Check dev user exists in auth.users
        r = await s.execute(text("SELECT id::text, email FROM auth.users WHERE email = 'dev@localhost'"))
        dev = r.fetchone()
        if dev:
            print(f"\n--- Dev user: id={dev[0]} email={dev[1]} ---")
        else:
            print("\n--- No dev user in auth.users yet ---")


print("=" * 60)
print("DATABASE VERIFICATION")
print("=" * 60)
asyncio.run(verify())
print("\nDONE")
