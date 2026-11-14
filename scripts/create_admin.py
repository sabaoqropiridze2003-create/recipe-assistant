import asyncio
import getpass
import sys

from sqlalchemy import select

from app.db.models import User
from app.db.session import SessionLocal
from app.services.security import hash_password


async def main(email: str, full_name: str) -> None:
    password = getpass.getpass("Password: ")
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email.lower()))
        if user:
            user.role = "admin"
            print(f"Promoted existing user {email} to admin")
        else:
            db.add(
                User(
                    email=email.lower(),
                    full_name=full_name,
                    hashed_password=hash_password(password),
                    role="admin",
                )
            )
            print(f"Created admin {email}")
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))