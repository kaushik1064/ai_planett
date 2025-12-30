from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, desc

from ..db import get_session, ChatSession, ChatMessage

router = APIRouter(prefix="/history", tags=["history"])

@router.get("/sessions", response_model=List[dict])
def list_sessions(session: Session = Depends(get_session)):
    """List all chat sessions sorted by creation time."""
    statement = select(ChatSession).order_by(desc(ChatSession.created_at))
    results = session.exec(statement).all()
    # Return simple dicts to avoid circular reference issues in automatic Pydantic serialization
    return [{"id": str(s.id), "title": s.title, "created_at": s.created_at} for s in results]

@router.post("/sessions", response_model=dict)
def create_session(title: str = "New Chat", session: Session = Depends(get_session)):
    """Create a new chat session."""
    try:
        new_session = ChatSession(title=title)
        session.add(new_session)
        session.commit()
        session.refresh(new_session)
        return {"id": str(new_session.id), "title": new_session.title, "created_at": new_session.created_at}
    except Exception as e:
        print(f"DB Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/messages")
def get_session_messages(session_id: UUID, session: Session = Depends(get_session)):
    """Get all messages for a specific session."""
    statement = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
    results = session.exec(statement).all()
    
    # Map to frontend Message format
    return [
        {
            "id": str(msg.id),
            "role": msg.role,
            "content": msg.content,
            "created_at": msg.created_at
        }
        for msg in results
    ]

from pydantic import BaseModel

class MessageCreate(BaseModel):
    role: str
    content: str

@router.post("/sessions/{session_id}/messages")
def add_message(session_id: UUID, message: MessageCreate, session: Session = Depends(get_session)):
    """Add a message to a session."""
    try:
        new_msg = ChatMessage(session_id=session_id, role=message.role, content=message.content)
        session.add(new_msg)
        session.commit()
        return {"status": "ok", "id": str(new_msg.id)}
    except Exception as e:
        print(f"DB Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}")
def delete_session(session_id: UUID, session: Session = Depends(get_session)):
    """Delete a session and all its messages."""
    statement = select(ChatSession).where(ChatSession.id == session_id)
    result = session.exec(statement).first()
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session.delete(result)
    session.commit()
    return {"status": "ok"}
