import contextlib
import json
import os
from io import BytesIO
from pathlib import Path
from typing import *
import httpx
import loguru

from config.config import Configs
from server.utils.utils import get_httpx_client, api_address
from utils.log_common import build_logger

logger = build_logger()

class ApiRequest:
    """
    A synchronous wrapper for making calls to api.py, simplifying the API invocation process.
    """

    def __init__(
        self,
        base_url: str = api_address(),
        timeout: float = Configs.basic_config.http_default_timeout,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self._use_async = False
        self._client = None

    @property
    def client(self):
        if self._client is None or self._client.is_closed:
            self._client = get_httpx_client(
                base_url=self.base_url, use_async=self._use_async, timeout=self.timeout
            )
        return self._client

    def get(
        self,
        url: str,
        params: Union[Dict, List[Tuple], bytes] = None,
        retry: int = 3,
        stream: bool = False,
        **kwargs: Any,
    ) -> Union[httpx.Response, Iterator[httpx.Response], None]:
        while retry > 0:
            try:
                if stream:
                    return self.client.stream("GET", url, params=params, **kwargs)
                else:
                    return self.client.get(url, params=params, **kwargs)
            except Exception as e:
                msg = f"Error during GET request to {url}: {e}"
                logger.error(f"{e.__class__.__name__}: {msg}")
                retry -= 1

    def post(
        self,
        url: str,
        data: Dict = None,
        json_data: Dict = None, # Renamed from `json` to avoid shadowing the built-in
        retry: int = 3,
        stream: bool = False,
        **kwargs: Any,
    ) -> Union[httpx.Response, Iterator[httpx.Response], None]:
        while retry > 0:
            try:
                if stream:
                    return self.client.stream(
                        "POST", url, data=data, json=json_data, **kwargs
                    )
                else:
                    return self.client.post(url, data=data, json=json_data, **kwargs)
            except Exception as e:
                msg = f"Error during POST request to {url}: {e}"
                logger.error(f"{e.__class__.__name__}: {msg}")
                retry -= 1

    def delete(
        self,
        url: str,
        data: Dict = None,
        json_data: Dict = None, # Renamed from `json` to avoid shadowing the built-in
        retry: int = 3,
        stream: bool = False,
        **kwargs: Any,
    ) -> Union[httpx.Response, Iterator[httpx.Response], None]:
        while retry > 0:
            try:
                if stream:
                    return self.client.stream(
                        "DELETE", url, data=data, json=json_data, **kwargs
                    )
                else:
                    return self.client.delete(url, data=data, json=json_data, **kwargs)
            except Exception as e:
                msg = f"Error during DELETE request to {url}: {e}"
                logger.error(f"{e.__class__.__name__}: {msg}")
                retry -= 1

    def _httpx_stream2generator(
        self,
        response: contextlib._GeneratorContextManager,
        as_json: bool = False,
    ):
        """
        Converts the GeneratorContextManager returned by httpx.stream into a standard generator.
        """

        async def ret_async(response, as_json):
            try:
                async with response as r:
                    chunk_cache = ""
                    async for chunk in r.aiter_text(None):
                        if not chunk:  # fastchat api yields empty bytes on start and end
                            continue
                        if as_json:
                            try:
                                if chunk.startswith("data: "):
                                    data = json.loads(chunk_cache + chunk[6:-2])
                                elif chunk.startswith(":"):  # skip sse comment line
                                    continue
                                else:
                                    data = json.loads(chunk_cache + chunk)

                                chunk_cache = ""
                                yield data
                            except Exception as e:
                                msg = f"API returned a JSON error for chunk: '{chunk}'. Error: {e}."
                                logger.error(f"{e.__class__.__name__}: {msg}")

                                if chunk.startswith("data: "):
                                    chunk_cache += chunk[6:-2]
                                elif chunk.startswith(":"):  # skip sse comment line
                                    continue
                                else:
                                    chunk_cache += chunk
                                continue
                        else:
                            yield chunk
            except httpx.ConnectError as e:
                msg = f"Could not connect to the API server. Please ensure 'api.py' is running correctly. ({e})"
                logger.error(msg)
                yield {"code": 500, "msg": msg}
            except httpx.ReadTimeout as e:
                msg = f"API communication timed out. Please ensure FastChat and the API service are running. ({e})"
                logger.error(msg)
                yield {"code": 500, "msg": msg}
            except Exception as e:
                msg = f"An error occurred during API communication: {e}"
                logger.error(f"{e.__class__.__name__}: {msg}")
                yield {"code": 500, "msg": msg}

        def ret_sync(response, as_json):
            try:
                with response as r:
                    chunk_cache = ""
                    for chunk in r.iter_text(None):
                        if not chunk:  # fastchat api yields empty bytes on start and end
                            continue
                        if as_json:
                            try:
                                if chunk.startswith("data: "):
                                    data = json.loads(chunk_cache + chunk[6:-2])
                                elif chunk.startswith(":"):  # skip sse comment line
                                    continue
                                else:
                                    data = json.loads(chunk_cache + chunk)
                                
                                chunk_cache = ""
                                yield data
                            except Exception as e:
                                msg = f"API returned a JSON error for chunk: '{chunk}'. Error: {e}."
                                logger.error(f"{e.__class__.__name__}: {msg}")
                                
                                if chunk.startswith("data: "):
                                    chunk_cache += chunk[6:-2]
                                elif chunk.startswith(":"):  # skip sse comment line
                                    continue
                                else:
                                    chunk_cache += chunk
                                continue
                        else:
                            yield chunk
            except httpx.ConnectError as e:
                msg = f"Could not connect to the API server. Please ensure 'api.py' is running correctly. ({e})"
                logger.error(msg)
                yield {"code": 500, "msg": msg}
            except httpx.ReadTimeout as e:
                msg = f"API communication timed out. Please ensure FastChat and the API service are running. ({e})"
                logger.error(msg)
                yield {"code": 500, "msg": msg}
            except Exception as e:
                msg = f"An error occurred during API communication: {e}"
                logger.error(f"{e.__class__.__name__}: {msg}")
                yield {"code": 500, "msg": msg}

        if self._use_async:
            return ret_async(response, as_json)
        else:
            return ret_sync(response, as_json)

    def _get_response_value(
        self,
        response: httpx.Response,
        as_json: bool = False,
        value_func: Callable = None,
    ):
        """
        Processes the response from a synchronous or asynchronous request.
        `as_json`: If True, returns the response body as JSON.
        `value_func`: A user-defined function to process the response or JSON object.
        """

        def to_json(r):
            try:
                return r.json()
            except Exception as e:
                msg = f"The API did not return valid JSON. {e}"
                logger.error(f"{e.__class__.__name__}: {msg}")
                return {"code": 500, "msg": msg, "data": None}

        if value_func is None:
            value_func = lambda r: r

        async def ret_async(response):
            if as_json:
                return value_func(to_json(await response))
            else:
                return value_func(await response)

        if self._use_async:
            return ret_async(response)
        else:
            if as_json:
                return value_func(to_json(response))
            else:
                return value_func(response)


    # Knowledge Base Operations

    def list_knowledge_bases(self):
        """
        Corresponds to the /knowledge_base/list_knowledge_bases endpoint.
        """
        response = self.get("/knowledge_base/list_knowledge_bases")
        return self._get_response_value(
            response, as_json=True, value_func=lambda r: r.get("data", [])
        )

    def create_knowledge_base(
        self,
        knowledge_base_name: str,
        vector_store_type: str = Configs.kb_config.default_vs_type,
        embed_model: str = Configs.llm_config.embedding_models,
    ):
        """
        Corresponds to the /knowledge_base/create_knowledge_base endpoint.
        """
        data = {
            "knowledge_base_name": knowledge_base_name,
            "vector_store_type": vector_store_type,
            "embed_model": embed_model,
        }

        response = self.post(
            "/knowledge_base/create_knowledge_base",
            json_data=data,
        )
        return self._get_response_value(response, as_json=True)

    def delete_knowledge_base(
        self,
        knowledge_base_name: str,
    ):
        """
        Corresponds to the /knowledge_base/delete_knowledge_base endpoint.
        """
        response = self.post(
            "/knowledge_base/delete_knowledge_base",
            json_data={"knowledge_base_name": knowledge_base_name},
        )
        return self._get_response_value(response, as_json=True)

    def list_kb_docs(
        self,
        knowledge_base_name: str,
    ):
        """
        Corresponds to the /knowledge_base/list_files endpoint.
        """
        response = self.get(
            "/knowledge_base/list_files",
            params={"knowledge_base_name": knowledge_base_name},
        )
        return self._get_response_value(
            response, as_json=True, value_func=lambda r: r.get("data", [])
        )

    def search_kb_docs(
        self,
        knowledge_base_name: str,
        query: str = "",
        top_k: int = Configs.kb_config.top_k,
        score_threshold: int = Configs.kb_config.score_threshold,
        file_name: str = "",
        metadata: dict = {},
    ) -> List:
        """
        Corresponds to the /knowledge_base/search_docs endpoint.
        """
        data = {
            "query": query,
            "knowledge_base_name": knowledge_base_name,
            "top_k": top_k,
            "score_threshold": score_threshold,
            "file_name": file_name,
            "metadata": metadata,
        }

        response = self.post(
            "/knowledge_base/search_docs",
            json_data=data,
        )
        return self._get_response_value(response, as_json=True)

    def upload_kb_docs(
        self,
        files: List[Union[str, Path, bytes]],
        knowledge_base_name: str,
        override: bool = False,
        to_vector_store: bool = True,
        chunk_size=Configs.kb_config.chunk_size,
        chunk_overlap=Configs.kb_config.overlap_size,
        docs: Dict = {},
        not_refresh_vs_cache: bool = False,
    ):
        """
        Corresponds to the /knowledge_base/upload_docs endpoint.
        """

        def convert_file(file, filename=None):
            if isinstance(file, bytes):  # raw bytes
                file = BytesIO(file)
            elif hasattr(file, "read"):  # a file-like object
                filename = filename or file.name
            else:  # a local path
                file = Path(file).absolute().open("rb")
                filename = filename or os.path.split(file.name)[-1]
            return filename, file

        files_to_upload = [convert_file(file) for file in files]
        data = {
            "knowledge_base_name": knowledge_base_name,
            "override": override,
            "to_vector_store": to_vector_store,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "docs": docs,
            "not_refresh_vs_cache": not_refresh_vs_cache,
        }

        if isinstance(data["docs"], dict):
            data["docs"] = json.dumps(data["docs"], ensure_ascii=False)
        
        response = self.post(
            "/knowledge_base/upload_docs",
            data=data,
            files=[("files", (filename, file)) for filename, file in files_to_upload],
        )
        return self._get_response_value(response, as_json=True)

    def delete_kb_docs(
        self,
        knowledge_base_name: str,
        file_names: List[str],
        delete_content: bool = False,
        not_refresh_vs_cache: bool = False,
    ):
        """
        Corresponds to the /knowledge_base/delete_docs endpoint.
        """
        data = {
            "knowledge_base_name": knowledge_base_name,
            "file_names": file_names,
            "delete_content": delete_content,
            "not_refresh_vs_cache": not_refresh_vs_cache,
        }

        response = self.post(
            "/knowledge_base/delete_docs",
            json_data=data,
        )
        return self._get_response_value(response, as_json=True)

    def update_kb_info(self, knowledge_base_name, kb_info):
        """
        Corresponds to the /knowledge_base/update_info endpoint.
        """
        data = {
            "knowledge_base_name": knowledge_base_name,
            "kb_info": kb_info,
        }

        response = self.post(
            "/knowledge_base/update_info",
            json_data=data,
        )
        return self._get_response_value(response, as_json=True)

    def update_kb_docs(
        self,
        knowledge_base_name: str,
        file_names: List[str],
        override_custom_docs: bool = False,
        chunk_size=Configs.kb_config.chunk_size,
        chunk_overlap=Configs.kb_config.overlap_size,
        docs: Dict = {},
        not_refresh_vs_cache: bool = False,
    ):
        """
        Corresponds to the /knowledge_base/update_docs endpoint.
        """
        data = {
            "knowledge_base_name": knowledge_base_name,
            "file_names": file_names,
            "override_custom_docs": override_custom_docs,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "docs": docs,
            "not_refresh_vs_cache": not_refresh_vs_cache,
        }

        if isinstance(data["docs"], dict):
            data["docs"] = json.dumps(data["docs"], ensure_ascii=False)

        response = self.post(
            "/knowledge_base/update_docs",
            json_data=data,
        )
        return self._get_response_value(response, as_json=True)


class AsyncApiRequest(ApiRequest):
    def __init__(
        self, base_url: str = api_address(), timeout: float = Configs.basic_config.http_default_timeout
    ):
        super().__init__(base_url, timeout)
        self._use_async = True


def check_error_msg(data: Union[str, dict, list], key: str = "errorMsg") -> str:
    """
    Return an error message if an error occurred when requesting the API.
    """
    if isinstance(data, dict):
        if key in data:
            return data[key]
        if "code" in data and data["code"] != 200:
            return data.get("msg", "")
    return ""


def check_success_msg(data: Union[str, dict, list], key: str = "msg") -> str:
    """
    Return a success message if the API request was successful.
    """
    if (
        isinstance(data, dict)
        and key in data
        and "code" in data
        and data["code"] == 200
    ):
        return data[key]
    return ""


def webui_address() -> str:
    host = Configs.basic_config.webui_server["host"]
    port = Configs.basic_config.webui_server["port"]
    return f"http://{host}:{port}"