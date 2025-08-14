from fastapi import APIRouter
from pydantic import BaseModel
from server.chat.chat import _chat
from server.utils.utils import BaseResponse

chat_router = APIRouter(prefix="/chat", tags=["Chat Management"])

class KBQuery(BaseModel):
    knowledge_base_name: str
    query: str
    history_len: int = 5 # Optional: You can add more parameters if needed

@chat_router.post("/kb_chat", response_model=BaseResponse, summary="Chat with a specific Knowledge Base")
def kb_chat(request: KBQuery):
    # We use the existing _chat function which is powerful
    # We can create a new conversation for each test query or manage it
    response_text = _chat(
        query=request.query,
        kb_name=request.knowledge_base_name,
        kb_query=request.query, # Use the same query for KB search
        conversation_id=None, # Create a new conversation for each test
        summary=False # Don't save test chats to DB
    )
    return BaseResponse(code=200, msg="Success", data=response_text)