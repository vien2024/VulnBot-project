import warnings

from langchain.vectorstores import VectorStore
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import VectorStoreRetriever


from langchain.docstore.document import Document
from langchain_core.callbacks.manager import (
    AsyncCallbackManagerForRetrieverRun,
    CallbackManagerForRetrieverRun,
)

from typing import List

from rag.retriever.base import BaseRetrieverService


class MilvusRetriever(VectorStoreRetriever):
    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        if self.search_type == "similarity":
            docs = self.vectorstore.similarity_search(query, **self.search_kwargs)
        elif self.search_type == "similarity_score_threshold":
            try:
                # Cách 1: Sử dụng similarity_search_with_relevance_scores
                docs_and_similarities = (
                    self.vectorstore.similarity_search_with_relevance_scores(
                        query, **self.search_kwargs
                    )
                )
                score_threshold = self.search_kwargs.get("score_threshold", 0.0)

                if any(
                    similarity < 0.0 or similarity > 1.0
                    for _, similarity in docs_and_similarities
                ):
                    warnings.warn(
                        "Relevance scores must be between"
                        f" 0 and 1, got {docs_and_similarities}"
                    )

                if score_threshold is not None:  # can be 0, but not None
                    docs_and_similarities = [
                        (doc, similarity)
                        for doc, similarity in docs_and_similarities
                        if similarity >= score_threshold
                    ]

                if len(docs_and_similarities) == 0:
                    warnings.warn(
                        "No relevant docs were retrieved using the relevance score"
                        f" threshold {score_threshold}"
                    )

                # Trả về chỉ documents, không có scores
                return [doc for doc, _ in docs_and_similarities]

            except (ValueError, AttributeError) as e:
                # Fallback: Nếu không thể sử dụng relevance scores, dùng similarity search thường
                warnings.warn(
                    f"Could not use relevance scores ({str(e)}). "
                    "Falling back to regular similarity search."
                )
                search_kwargs_fallback = self.search_kwargs.copy()
                # Loại bỏ score_threshold vì similarity_search không hỗ trợ
                search_kwargs_fallback.pop("score_threshold", None)
                docs = self.vectorstore.similarity_search(
                    query, **search_kwargs_fallback
                )
                return docs

        elif self.search_type == "mmr":
            docs = self.vectorstore.max_marginal_relevance_search(
                query, **self.search_kwargs
            )
        else:
            raise ValueError(f"search_type of {self.search_type} not allowed.")
        return docs

    async def _aget_relevant_documents(
        self, query: str, *, run_manager: AsyncCallbackManagerForRetrieverRun
    ) -> List[Document]:
        if self.search_type == "similarity":
            docs = await self.vectorstore.asimilarity_search(
                query, **self.search_kwargs
            )
        elif self.search_type == "similarity_score_threshold":
            try:
                # Cách 1: Sử dụng asimilarity_search_with_score
                docs_and_similarities = (
                    await self.vectorstore.asimilarity_search_with_score(
                        query, **self.search_kwargs
                    )
                )
                score_threshold = self.search_kwargs.get("score_threshold", 0.0)

                if any(
                    similarity < 0.0 or similarity > 1.0
                    for _, similarity in docs_and_similarities
                ):
                    warnings.warn(
                        "Relevance scores must be between"
                        f" 0 and 1, got {docs_and_similarities}"
                    )

                if score_threshold is not None:  # can be 0, but not None
                    docs_and_similarities = [
                        (doc, similarity)
                        for doc, similarity in docs_and_similarities
                        if similarity >= score_threshold
                    ]

                if len(docs_and_similarities) == 0:
                    warnings.warn(
                        "No relevant docs were retrieved using the relevance score"
                        f" threshold {score_threshold}"
                    )

                # Trả về chỉ documents, không có scores
                return [doc for doc, _ in docs_and_similarities]

            except (ValueError, AttributeError) as e:
                # Fallback: Nếu không thể sử dụng relevance scores, dùng similarity search thường
                warnings.warn(
                    f"Could not use relevance scores ({str(e)}). "
                    "Falling back to regular similarity search."
                )
                search_kwargs_fallback = self.search_kwargs.copy()
                # Loại bỏ score_threshold vì asimilarity_search không hỗ trợ
                search_kwargs_fallback.pop("score_threshold", None)
                docs = await self.vectorstore.asimilarity_search(
                    query, **search_kwargs_fallback
                )
                return docs

        elif self.search_type == "mmr":
            docs = await self.vectorstore.amax_marginal_relevance_search(
                query, **self.search_kwargs
            )
        else:
            raise ValueError(f"search_type of {self.search_type} not allowed.")
        return docs


class MilvusVectorstoreRetrieverService(BaseRetrieverService):
    def do_init(
        self,
        retriever: BaseRetriever = None,
        top_k: int = 5,
    ):
        self.vs = None
        self.top_k = top_k
        self.retriever = retriever

    @staticmethod
    def from_vectorstore(
        vectorstore: VectorStore,
        top_k: int,
        score_threshold: float = 0.0,  # Đặt default value
    ):
        # Kiểm tra xem vectorstore có hỗ trợ relevance scores không
        try:
            # Test với một query đơn giản để xem có lỗi không
            test_docs = vectorstore.similarity_search("test", k=1)
            if test_docs:
                # Nếu similarity_search hoạt động, thử với relevance scores
                try:
                    vectorstore.similarity_search_with_relevance_scores("test", k=1)
                    search_type = "similarity_score_threshold"
                    search_kwargs = {"score_threshold": score_threshold, "k": top_k}
                except:
                    # Nếu không hỗ trợ relevance scores, dùng similarity thường
                    search_type = "similarity"
                    search_kwargs = {"k": top_k}
            else:
                search_type = "similarity"
                search_kwargs = {"k": top_k}
        except:
            # Fallback an toàn
            search_type = "similarity"
            search_kwargs = {"k": top_k}

        retriever = MilvusRetriever(
            vectorstore=vectorstore,
            search_type=search_type,
            search_kwargs=search_kwargs,
        )

        return MilvusVectorstoreRetrieverService(retriever=retriever, top_k=top_k)

    def get_relevant_documents(self, query: str):
        return self.retriever.invoke(query)[: self.top_k]
