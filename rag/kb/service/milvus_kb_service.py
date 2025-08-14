import os
from typing import Dict, List, Optional

from langchain.schema import Document
from langchain_milvus import Milvus

from config.config import Configs
from rag.embedding.embedding import get_embeddings
from rag.kb.base import KBService, SupportedVSType
from rag.kb.repository.knowledge_file_repository import (
    list_file_num_docs_id_by_kb_name_and_file_name,
    delete_docs_from_db_by_ids,
)
from rag.kb.utils.kb_utils import KnowledgeFile
from rag.retriever.milvus_vectorstore import MilvusVectorstoreRetrieverService
from utils.log_common import build_logger

logger = build_logger()


class MilvusKBService(KBService):
    milvus: Milvus

    @staticmethod
    def get_collection(milvus_name):
        from pymilvus import Collection

        return Collection(milvus_name)

    def get_doc_by_ids(self, ids: List[str]) -> List[Document]:
        result = []
        if self.milvus.col and ids:
            data_list = self.milvus.col.query(
                expr=f"pk in {[int(_id) for _id in ids]}", output_fields=["*"]
            )
            for data in data_list:
                text = data.pop("text", "")  # Use .get for safety
                pk = data.pop("pk")  # pk is the id
                result.append(Document(page_content=text, metadata={"id": pk, **data}))
        return result

    def del_doc_by_ids(self, ids: List[str]) -> bool:
        if self.milvus.col and ids:
            # Cast IDs to integers for the query, which is crucial.
            int_ids = [int(_id) for _id in ids]
            self.milvus.col.delete(expr=f"pk in {int_ids}")
            # Also delete from the relational database for consistency
            delete_docs_from_db_by_ids(self.kb_name, ids)
            logger.info(
                f"Deleted {len(ids)} docs from Milvus and DB for kb '{self.kb_name}'."
            )
        return True

    def do_create_kb(self):
        pass

    def vs_type(self) -> str:
        return SupportedVSType.MILVUS

    def _load_milvus(self):
        self.milvus = Milvus(
            embedding_function=get_embeddings(self.embed_model),
            collection_name=self.kb_name,
            connection_args=Configs.kb_config.milvus,
            index_params=Configs.kb_config.index_params,
            search_params=Configs.kb_config.search_params,
            enable_dynamic_field=True,
            auto_id=True,
            primary_field="pk",
        )

    def do_init(self):
        self._load_milvus()

    def do_drop_kb(self):
        if self.milvus.col:
            try:
                self.milvus.col.release()
                self.milvus.col.drop()
                logger.info(f"Dropped Milvus collection: {self.kb_name}")
            except Exception as e:
                logger.error(f"Failed to drop Milvus collection {self.kb_name}: {e}")

    def do_search(self, query: str, top_k: int, score_threshold: float):
        # self._load_milvus()

        retriever = MilvusVectorstoreRetrieverService.from_vectorstore(
            self.milvus,
            top_k=top_k,
            score_threshold=score_threshold,
        )
        docs = retriever.get_relevant_documents(query)
        return docs

    def do_add_doc(self, docs: List[Document], **kwargs) -> List[Dict]:
        for doc in docs:
            for k, v in doc.metadata.items():
                doc.metadata[k] = str(v)
            for field in self.milvus.fields:
                doc.metadata.setdefault(field, "")
            if "pk" in doc.metadata:
                doc.metadata.pop("pk")
            doc.metadata.pop(self.milvus._text_field, None)
            doc.metadata.pop(self.milvus._vector_field, None)
        ids = self.milvus.add_documents(docs)
        doc_infos = [{"id": id, "metadata": doc.metadata} for id, doc in zip(ids, docs)]
        return doc_infos

    def do_delete_doc(self, kb_file: KnowledgeFile, **kwargs):
        id_list = list_file_num_docs_id_by_kb_name_and_file_name(
            kb_file.kb_name, kb_file.filename
        )
        if self.milvus.col and id_list:
            self.milvus.col.delete(expr=f"pk in {id_list}")
            logger.info(
                f"Deleted docs for file '{kb_file.filename}' from Milvus collection '{self.kb_name}'."
            )

    def do_clear_vs(self):
        if self.milvus.col:
            self.do_drop_kb()
            self.do_create_kb()
            self.do_init()
