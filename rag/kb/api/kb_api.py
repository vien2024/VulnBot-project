import urllib
import re  # Thêm import re
from fastapi import Body
from pydantic import BaseModel, Field

from rag.kb.base import KBServiceFactory
from rag.kb.repository.kb_repository import list_kbs_from_db
from rag.kb.utils.kb_utils import validate_kb_name
from server.utils.utils import ListResponse, BaseResponse

# === BẮT ĐẦU PHẦN SỬA ĐỔI ===


def check_kb_name(name: str) -> bool:
    """
    Kiểm tra tên knowledge base có hợp lệ theo quy tắc của Milvus hay không.
    Chỉ cho phép chữ cái, số và dấu gạch dưới.
    """
    # Milvus 2.2.11: Tên phải bắt đầu bằng chữ cái hoặc dấu gạch dưới,
    # và chỉ chứa chữ cái, số, và dấu gạch dưới.
    return re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name) is not None


# === KẾT THÚC PHẦN SỬA ĐỔI ===


class CreateKBBody(BaseModel):
    knowledge_base_name: str
    vector_store_type: str
    embed_model: str
    kb_info: str = ""


class DeleteKBBody(BaseModel):
    knowledge_base_name: str


def list_kbs():
    return ListResponse(data=list_kbs_from_db())


def create_kb(body: CreateKBBody) -> BaseResponse:
    knowledge_base_name = body.knowledge_base_name
    vector_store_type = body.vector_store_type
    embed_model = body.embed_model
    kb_info = body.kb_info

    # === BẮT ĐẦU PHẦN SỬA ĐỔI ===
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=403, msg="Don't attack me")

    # THÊM BƯỚC KIỂM TRA TÊN HỢP LỆ
    if not check_kb_name(knowledge_base_name):
        return BaseResponse(
            code=400,
            msg="Invalid knowledge base name. The name can only contain letters, numbers, and underscores, and must start with a letter or an underscore.",
        )
    # === KẾT THÚC PHẦN SỬA ĐỔI ===

    if knowledge_base_name is None or knowledge_base_name.strip() == "":
        return BaseResponse(
            code=404,
            msg="Knowledge base name cannot be empty, please re-fill the knowledge base name",
        )

    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    if kb is not None:
        return BaseResponse(
            code=404, msg=f"Knowledge base {knowledge_base_name} already exists"
        )

    kb = KBServiceFactory.get_service(
        knowledge_base_name, vector_store_type, embed_model, kb_info=kb_info
    )
    try:
        kb.create_kb()
    except Exception as e:
        msg = f"Failed to create knowledge base: {e}"
        return BaseResponse(code=500, msg=msg)

    return BaseResponse(
        code=200, msg=f"Successfully created knowledge base {knowledge_base_name}"
    )


def delete_kb(body: DeleteKBBody) -> BaseResponse:
    knowledge_base_name = body.knowledge_base_name

    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=403, msg="Don't attack me")

    # THÊM BƯỚC KIỂM TRA TÊN HỢP LỆ
    if not check_kb_name(knowledge_base_name):
        return BaseResponse(
            code=400,
            msg="Invalid knowledge base name. The name can only contain letters, numbers, and underscores, and must start with a letter or an underscore.",
        )

    knowledge_base_name = urllib.parse.unquote(knowledge_base_name)
    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)

    if kb is None:
        return BaseResponse(
            code=404, msg=f"Knowledge base {knowledge_base_name} not found"
        )

    try:
        status = kb.clear_vs()
        status = kb.drop_kb()
        if status:
            return BaseResponse(
                code=200,
                msg=f"Successfully deleted knowledge base {knowledge_base_name}",
            )
    except Exception as e:
        msg = f"Failed to delete knowledge base: {e}"
        return BaseResponse(code=500, msg=msg)

    return BaseResponse(
        code=500, msg=f"Failed to delete knowledge base {knowledge_base_name}"
    )
