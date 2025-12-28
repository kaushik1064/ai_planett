from datetime import datetime
from typing import Optional, List
from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel, create_engine, Session, select, Relationship

from .config import settings

# --- DATABASE MODELS ---

class ChatSession(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    title: str = Field(default="New Chat")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    messages: List["ChatMessage"] = Relationship(back_populates="session")


class ChatMessage(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    session_id: UUID = Field(foreign_key="chatsession.id")
    role: str  # "user" or "assistant"
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    session: Optional[ChatSession] = Relationship(back_populates="messages")


# --- ENGINE & DEPENDENCY ---

# We need to make sure we have the DATABASE_URL
database_url = settings.database_url
if not database_url:
    # Fallback for dev if not set (though implementation_plan requires it)
    database_url = "sqlite:///./local_chat.db"

# Supabase (Postgres) needs "postgresql://" but sometimes comes as "postgres://"
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(database_url, echo=False)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
