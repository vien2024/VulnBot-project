from __future__ import annotations

from typing import List

from fastapi import APIRouter
from rag.kb.api.kb_api import create_kb, delete_kb, list_kbs
from rag.kb.api.kb_doc_api import (
    delete_docs,
    list_files,
    search_docs,
    update_info,
    upload_docs, download_doc, update_docs,
)
from server.utils.utils import ListResponse, BaseResponse

kb_router = APIRouter(prefix="/knowledge_base", tags=["Knowledge Base Management"])



kb_router.get(
    "/list_knowledge_bases", response_model=ListResponse, summary="Get Knowledge Base List"
)(list_kbs)

kb_router.post(
    "/create_knowledge_base", response_model=BaseResponse, summary="Create Knowledge Base"
)(create_kb)

kb_router.post(
    "/delete_knowledge_base", response_model=BaseResponse, summary="Delete Knowledge Base"
)(delete_kb)

kb_router.get(
    "/list_files", response_model=ListResponse, summary="Get Files in Knowledge Base"
)(list_files)

kb_router.post("/search_docs", response_model=List[dict], summary="Search Knowledge Base")(
    search_docs
)

kb_router.post(
    "/upload_docs",
    response_model=BaseResponse,
    summary="Upload Files to Knowledge Base and/or Vectorize",
)(upload_docs)

kb_router.post(
    "/delete_docs", response_model=BaseResponse, summary="Delete Files in Knowledge Base"
)(delete_docs)

kb_router.post("/update_info", response_model=BaseResponse, summary="Update Knowledge Base Description")(
    update_info
)

kb_router.post(
    "/update_docs", response_model=BaseResponse, summary="Update Existing Files in Knowledge Base"
)(update_docs)

kb_router.get("/download_doc", summary="Download Knowledge File")(download_doc)




