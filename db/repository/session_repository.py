import uuid
from typing import List

from db.models.session_model import Session, SessionModel
from utils.session import with_session
import time

@with_session
def add_session_to_db(session, session_data):
    if not hasattr(session_data, 'name') or not session_data.name:
        session_data.name = f"Session_{int(time.time())}"
    new_task = SessionModel(
        id=uuid.uuid4().hex,
        name=session_data.name,
        current_role_name=session_data.current_role_name,
        init_description=session_data.init_description,
        current_planner_id=session_data.current_planner_id,
        history_planner_ids=','.join(session_data.history_planner_ids)
    )

    session.add(new_task)


@with_session
def fetch_all_sessions(session) -> List[Session]:

    result = session.query(SessionModel).all()

    result = [Session.model_validate(r) for r in result]

    return result

@with_session
def update_session_in_db(session, session_data):
    """
    Update an existing session in the database
    
    Args:
        session: SQLAlchemy session (injected by decorator)
        session_data: Session object to update
    """
    try:
        # Convert Pydantic model to SQLAlchemy model for database operations
        session_model = SessionModel(
            id=session_data.id,
            name=session_data.name or "",
            current_role_name=session_data.current_role_name or "",
            init_description=session_data.init_description or "",
            current_planner_id=session_data.current_planner_id or "",
            history_planner_ids=",".join(session_data.history_planner_ids) if session_data.history_planner_ids else ""
        )
        
        # Find existing session in database
        existing_session = session.query(SessionModel).filter_by(id=session_data.id).first()
        
        if existing_session:
            # Update existing session fields
            existing_session.name = session_model.name
            existing_session.current_role_name = session_model.current_role_name
            existing_session.init_description = session_model.init_description
            existing_session.current_planner_id = session_model.current_planner_id
            existing_session.history_planner_ids = session_model.history_planner_ids
            
            session.commit()
            
            return session_data
        else:
            # If session doesn't exist, create it
            session.add(session_model)
            session.commit()
            
            return session_data
            
    except Exception as e:
        session.rollback()
        print(f"Error updating session: {e}")
        raise e