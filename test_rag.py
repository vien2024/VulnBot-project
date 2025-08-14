import asyncio
from rich.console import Console
from rich.panel import Panel
from rich.pretty import pprint
from starlette.concurrency import run_in_threadpool

from config.config import Configs
from rag.kb.api.kb_doc_api import search_docs
from rag.reranker.reranker import LangchainReranker
from server.chat.chat import _chat, OpenAIChat, OllamaChat, GeminiChat
from server.utils.utils import replace_ip_with_targetip, LLMType

# Khởi tạo console để in ra đẹp hơn
console = Console()

# ==============================================================================
# === CẤU HÌNH TEST: THAY ĐỔI CÁC GIÁ TRỊ NÀY ĐỂ TEST ===
# ==============================================================================
KB_NAME_TO_TEST = "a"  # <--- THAY ĐỔI: Tên Knowledge Base bạn muốn test
QUERY_TO_TEST = "what is this document about?"  # <--- THAY ĐỔI: Câu hỏi bạn muốn test
TEST_MODE = "detailed-steps"  # Chọn 1 trong 3: 'simple-chat', 'detailed-steps', 'retrieval-only'
# ==============================================================================


def handle_chat_response(response):
    """
    Xử lý response từ hàm _chat một cách an toàn.
    Hàm _chat có thể trả về 1 string (lỗi) hoặc 1 tuple (thành công).
    """
    if isinstance(response, tuple) and len(response) == 2:
        return response[0]  # Chỉ lấy phần text trả lời
    elif isinstance(response, str):
        return response  # Trả về chuỗi lỗi
    return "Unknown response format from _chat function."


async def main():
    """
    Hàm test chính, sử dụng async/await để tương thích với các hàm khác.
    """
    kb_name = KB_NAME_TO_TEST
    query = QUERY_TO_TEST
    mode = TEST_MODE

    console.rule(f"[bold green]Starting RAG Test[/bold green]")
    console.print(f"Knowledge Base: [cyan]{kb_name}[/cyan]")
    console.print(f"Query: [cyan]{query}[/cyan]")
    console.print(f"Mode: [cyan]{mode}[/cyan]")
    console.line()

    # Kích hoạt RAG để _chat sử dụng nó
    Configs.basic_config.enable_rag = True

    if mode == "simple-chat":
        console.print("[yellow]Running in 'simple-chat' mode...[/yellow]")
        with console.status("[bold blue]Generating final answer..."):
            response = await run_in_threadpool(
                _chat, query=query, kb_name=kb_name, kb_query=query, summary=False
            )
        final_answer = handle_chat_response(response)
        console.print(
            Panel(
                final_answer,
                title="[bold green]Final LLM Answer[/bold green]",
                expand=False,
            )
        )

    elif mode in ["detailed-steps", "retrieval-only"]:
        console.print(
            "[yellow]Running in 'detailed-steps' or 'retrieval-only' mode...[/yellow]"
        )

        # --- BƯỚC 1: RETRIEVAL ---
        console.rule(
            "[bold blue]Step 1: Initial Retrieval from Vector Store[/bold blue]"
        )
        with console.status("[blue]Searching for relevant documents..."):
            initial_docs = await run_in_threadpool(
                search_docs,
                query=query,
                knowledge_base_name=kb_name,
                top_k=Configs.kb_config.top_k + 5,
                score_threshold=Configs.kb_config.score_threshold,
            )

        if not initial_docs:
            console.print("[bold red]No documents found from vector store.[/bold red]")
            return

        console.print(f"Found {len(initial_docs)} documents from Milvus.")
        pprint(initial_docs, expand_all=True)

        if mode == "retrieval-only":
            console.rule("[bold green]Test Finished (Retrieval-Only Mode)[/bold green]")
            return

        # --- BƯỚC 2: RERANKING ---
        console.rule("[bold magenta]Step 2: Reranking[/bold magenta]")
        with console.status("[magenta]Reranking documents..."):
            reranker_model = LangchainReranker(
                top_n=Configs.kb_config.top_n,
                name_or_path=Configs.llm_config.rerank_model,
            )
            reranked_docs = reranker_model.compress_documents(
                documents=initial_docs, query=query
            )

        console.print(f"Reranked to top {len(reranked_docs)} documents.")
        pprint(reranked_docs, expand_all=True)

        # --- BƯỚC 3: CONTEXT BUILDING ---
        console.rule("[bold yellow]Step 3: Building Final Context[/bold yellow]")
        if not reranked_docs:
            context = ""
            console.print(
                "[bold red]No documents left after reranking. Context is empty.[/bold red]"
            )
        else:
            context = "\n".join([doc["page_content"] for doc in reranked_docs])
            context = replace_ip_with_targetip(context)

        console.print(
            Panel(context, title="Final Context for LLM", border_style="yellow")
        )

        # --- BƯỚC 4: LLM GENERATION ---
        console.rule("[bold green]Step 4: Final LLM Generation[/bold green]")
        final_query = f"{query}\n\n\n Ensure that the **Overall Target** IP or the IP from the **Initial Description** is prioritized. You will respond to questions and generate tasks based on the provided penetration test case materials: {context}. \n"

        with console.status("[bold green]Generating final answer with context..."):
            # Lựa chọn client LLM dựa trên config
            if Configs.llm_config.llm_model == LLMType.OPENAI:
                client = OpenAIChat(config=Configs.llm_config)
            elif Configs.llm_config.llm_model == LLMType.OLLAMA:
                client = OllamaChat(config=Configs.llm_config)
            elif Configs.llm_config.llm_model == LLMType.GEMINI:
                client = GeminiChat(config=Configs.llm_config)
            else:
                response_text = "Unsupported model type in config."

            if "client" in locals():
                history = [{"role": "user", "content": final_query}]
                response_text = await run_in_threadpool(client.chat, history=history)

        console.print(
            Panel(
                response_text,
                title="[bold green]Final LLM Answer[/bold green]",
                expand=False,
            )
        )

    console.rule("[bold green]Test Finished[/bold green]")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        console.print_exception()
