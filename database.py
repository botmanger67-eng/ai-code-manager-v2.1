import datetime
from typing import AsyncGenerator, Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Boolean, JSON
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# ------------------------------------------------------------------
# Database engine and session factory
# ------------------------------------------------------------------
DATABASE_URL = "sqlite+aiosqlite:///./project_planner.db"

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# ------------------------------------------------------------------
# Models
# ------------------------------------------------------------------
class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="New Chat Session")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )

    # relationships
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    project = relationship("Project", back_populates="session", uselist=False, cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    files_plan: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)   # JSON object for file plans

    session = relationship("ChatSession", back_populates="messages")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    files: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)        # JSON object describing project files
    repo_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    pushed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )

    session = relationship("ChatSession", back_populates="project")


# ------------------------------------------------------------------
# Helper: create tables
# ------------------------------------------------------------------
async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ------------------------------------------------------------------
# Dependency: get async database session (for FastAPI / Starlette)
# ------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()