import json
import os
import time
from typing import Dict, Literal, Tuple, List

import pandas as pd
import streamlit as st

from st_aggrid import AgGrid, JsCode
from st_aggrid.grid_options_builder import GridOptionsBuilder

from config.config import Configs
from rag.kb.base import get_kb_details, get_kb_file_details
from rag.kb.utils.kb_utils import get_file_path, LOADER_DICT
from utils.log_common import build_logger
from web.utils.utils import ApiRequest, check_success_msg, check_error_msg

logger = build_logger()

cell_renderer = JsCode(
    """function(params) {if(params.value==true){return '✓'}else{return '×'}}"""
)


def config_aggrid(
    df: pd.DataFrame,
    columns: Dict[Tuple[str, str], Dict] = {},
    selection_mode: Literal["single", "multiple", "disabled"] = "single",
    use_checkbox: bool = False,
) -> GridOptionsBuilder:
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_column("No", width=40)
    for (col, header), kw in columns.items():
        gb.configure_column(col, header, wrapHeaderText=True, **kw)
    gb.configure_selection(
        selection_mode=selection_mode,
        use_checkbox=use_checkbox,
        pre_selected_rows=st.session_state.get("selected_rows", [0]),
    )
    gb.configure_pagination(
        enabled=True, paginationAutoPageSize=False, paginationPageSize=10
    )
    return gb


def file_exists(kb: str, selected_rows: List) -> Tuple[str, str]:
    """
    check whether a doc file exists in local knowledge base folder.
    return the file's name and path if it exists.
    """
    if selected_rows:
        file_name = selected_rows[0]["file_name"]
        file_path = get_file_path(kb, file_name)
        if os.path.isfile(file_path):
            return file_name, file_path
    return "", ""


def knowledge_base_page(api: ApiRequest):
    try:
        kb_list = {x["kb_name"]: x for x in get_kb_details()}
    except Exception as e:
        logger.error(e)
        st.error(
            "Failed to get knowledge base information, please check if the database connection is correct."
        )
        st.stop()
    kb_names = list(kb_list.keys())

    if (
        "selected_kb_name" in st.session_state
        and st.session_state["selected_kb_name"] in kb_names
    ):
        selected_kb_index = kb_names.index(st.session_state["selected_kb_name"])
    else:
        selected_kb_index = 0

    if "selected_kb_info" not in st.session_state:
        st.session_state["selected_kb_info"] = ""

    def format_selected_kb(kb_name: str) -> str:
        if kb := kb_list.get(kb_name):
            return f"{kb_name} ({kb['vs_type']} @ {kb['embed_model']})"
        else:
            return kb_name

    selected_kb = st.selectbox(
        "Select or create knowledge base:",
        kb_names + ["New knowledge base"],
        format_func=format_selected_kb,
        index=selected_kb_index,
    )

    if selected_kb == "New knowledge base":
        with st.form("New knowledge base"):
            kb_name = st.text_input(
                "New knowledge base name",
                placeholder="New knowledge base name, do not support Chinese naming",
                key="kb_name",
            )
            kb_info = st.text_input(
                "Knowledge base description",
                placeholder="Knowledge base description,to make it easier for the Agent to retrieve",
                key="kb_info",
            )

            col0, _ = st.columns([3, 1])

            vs_types = list([Configs.kb_config.default_vs_type])
            vs_type = col0.selectbox(
                "Vector store type",
                vs_types,
                index=vs_types.index(Configs.kb_config.default_vs_type),
                key="vs_type",
            )

            col1, _ = st.columns([3, 1])
            with col1:
                embed_models = list([Configs.llm_config.embedding_models])
                index = 0
                embed_model = st.selectbox("Embeddings model", embed_models, index)

            submit_create_kb = st.form_submit_button(
                "New",
                # disabled=not bool(kb_name),
                use_container_width=True,
            )

        if submit_create_kb:
            if not kb_name or not kb_name.strip():
                st.error(f"Knowledge base name cannot be empty!")
            elif kb_name in kb_list:
                st.error(f"Knowledge base named {kb_name} already exists!")
            elif embed_model is None:
                st.error(f"Please select an Embedding model!")
            else:
                ret = api.create_knowledge_base(
                    knowledge_base_name=kb_name,
                    vector_store_type=vs_type,
                    embed_model=embed_model,
                )
                st.toast(ret.get("msg", " "))
                st.session_state["selected_kb_name"] = kb_name
                st.session_state["selected_kb_info"] = kb_info
                st.rerun()

    elif selected_kb:
        kb = selected_kb
        st.session_state["selected_kb_info"] = kb_list[kb]["kb_info"]
        # Upload files
        files = st.file_uploader(
            "Upload Knowledge File:",
            [i for ls in LOADER_DICT.values() for i in ls],
            accept_multiple_files=True,
        )
        kb_info = st.text_area(
            "Please enter the knowledge base description:",
            value=st.session_state["selected_kb_info"],
            max_chars=None,
            key=None,
            help=None,
            on_change=None,
            args=None,
            kwargs=None,
        )

        if kb_info != st.session_state["selected_kb_info"]:
            st.session_state["selected_kb_info"] = kb_info
            api.update_kb_info(kb, kb_info)

        # with st.sidebar:
        with st.expander(
            "File processing configuration",
            expanded=True,
        ):
            cols = st.columns(3)
            chunk_size = cols[0].number_input("Single text maximum length", 1, 1000, Configs.kb_config.chunk_size)
            chunk_overlap = cols[1].number_input(
                "Adjacent text overlap length", 0, chunk_size, Configs.kb_config.overlap_size
            )


        if st.button(
            "Add files to knowledge base",
            # use_container_width=True,
            disabled=len(files) == 0,
        ):
            ret = api.upload_kb_docs(
                files,
                knowledge_base_name=kb,
                override=True,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            if msg := check_success_msg(ret):
                st.toast(msg, icon="✔")
            elif msg := check_error_msg(ret):
                st.toast(msg, icon="✖")

        st.divider()

        # Knowledge base details
        # st.info("请选择文件，点击按钮进行操作。")
        doc_details = pd.DataFrame(get_kb_file_details(kb))
        selected_rows = []
        if not len(doc_details):
            st.info(f"Knowledge base `{kb}` has no files")
        else:
            st.write(f"Knowledge base `{kb}` has files:")
            st.info("Knowledge base contains source files and vector store, please select files from the table below to perform operations")
            doc_details.drop(columns=["kb_name"], inplace=True)
            doc_details = doc_details[
                [
                    "No",
                    "file_name",
                    "document_loader",
                    "text_splitter",
                    "docs_count",
                    "in_folder",
                    "in_db",
                ]
            ]
            doc_details["in_folder"] = (
                doc_details["in_folder"].replace(True, "✓").replace(False, "×")
            )
            doc_details["in_db"] = (
                doc_details["in_db"].replace(True, "✓").replace(False, "×")
            )
            gb = config_aggrid(
                doc_details,
                {
                    ("No", "Number"): {},
                    ("file_name", "Document name"): {},
                    # ("file_ext", "Document type"): {},
                    # ("file_version", "Document version"): {},
                    ("document_loader", "Document loader"): {},
                    ("docs_count", "Document count"): {},
                    ("text_splitter", "Text splitter"): {},
                    # ("create_time", "Create time"): {},
                    ("in_folder", "Source file"): {},
                    ("in_db", "Vector store"): {},
                },
                "multiple",
            )

            doc_grid = AgGrid(
                doc_details,
                gb.build(),
                columns_auto_size_mode="FIT_CONTENTS",
                theme="alpine",
                custom_css={
                    "#gridToolBar": {"display": "none"},
                },
                allow_unsafe_jscode=True,
                enable_enterprise_modules=False,
            )

            selected_rows = doc_grid.get("selected_rows")
            if selected_rows is None:
                selected_rows = []
            else:
                selected_rows = selected_rows.to_dict("records")
            cols = st.columns(4)
            file_name, file_path = file_exists(kb, selected_rows)
            if file_path:
                with open(file_path, "rb") as fp:
                    cols[0].download_button(
                        "Download selected document",
                        fp,
                        file_name=file_name,
                        use_container_width=True,
                    )
            else:
                cols[0].download_button(
                    "Download selected document",
                    "",
                    disabled=True,
                    use_container_width=True,
                )

            st.write()
            # 将文件分词并加载到向量库中
            if cols[1].button(
                "Re-add to vector store"
                if selected_rows and (pd.DataFrame(selected_rows)["in_db"]).any()
                else "Add to vector store",
                disabled=not file_exists(kb, selected_rows)[0],
                use_container_width=True,
            ):
                file_names = [row["file_name"] for row in selected_rows]
                api.update_kb_docs(
                    kb,
                    file_names=file_names,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
                st.rerun()

            # 将文件从向量库中删除，但不删除文件本身。
            if cols[2].button(
                "Delete from vector store",
                disabled=not (selected_rows and selected_rows[0]["in_db"]),
                use_container_width=True,
            ):
                file_names = [row["file_name"] for row in selected_rows]
                api.delete_kb_docs(kb, file_names=file_names)
                st.rerun()

            if cols[3].button(
                "Delete from knowledge base",
                type="primary",
                use_container_width=True,
            ):
                file_names = [row["file_name"] for row in selected_rows]
                api.delete_kb_docs(kb, file_names=file_names, delete_content=True)
                st.rerun()

        st.divider()

        cols = st.columns(3)

        if cols[1].button(
            "Delete knowledge base",
            use_container_width=True,
        ):
            ret = api.delete_knowledge_base(kb)
            st.toast(ret.get("msg", " "))
            time.sleep(1)
            st.rerun()


        st.write("File document list. Double-click to modify, fill in Y in the delete column to delete the corresponding row.")
        docs = []
        df = pd.DataFrame([], columns=["seq", "id", "content", "source"])
        if selected_rows:
            file_name = selected_rows[0]["file_name"]
            docs = api.search_kb_docs(
                knowledge_base_name=selected_kb, file_name=file_name
            )

            data = [
                {
                    "seq": i + 1,
                    "id": x["id"],
                    "page_content": x["page_content"],
                    "source": x["metadata"].get("source"),
                    "type": x["type"],
                    "metadata": json.dumps(x["metadata"], ensure_ascii=False),
                    "to_del": "",
                }
                for i, x in enumerate(docs)
            ]
            df = pd.DataFrame(data)

            gb = GridOptionsBuilder.from_dataframe(df)
            gb.configure_columns(["id", "source", "type", "metadata"], hide=True)
            gb.configure_column("seq", "No.", width=50)
            gb.configure_column(
                "page_content",
                "Content",
                editable=True,
                autoHeight=True,
                wrapText=True,
                flex=1,
                cellEditor="agLargeTextCellEditor",
                cellEditorPopup=True,
            )
            gb.configure_column(
                "to_del",
                "Delete",
                editable=True,
                width=50,
                wrapHeaderText=True,
                cellEditor="agCheckboxCellEditor",
                cellRender="agCheckboxCellRenderer",
            )
            # 启用分页
            gb.configure_pagination(
                enabled=True, paginationAutoPageSize=False, paginationPageSize=10
            )
            gb.configure_selection()
            edit_docs = AgGrid(df, gb.build(), fit_columns_on_grid_load=True)

            if st.button("Save changes"):
                origin_docs = {
                    x["id"]: {
                        "page_content": x["page_content"],
                        "type": x["type"],
                        "metadata": x["metadata"],
                    }
                    for x in docs
                }
                changed_docs = []
                for index, row in edit_docs.data.iterrows():
                    origin_doc = origin_docs[row["id"]]
                    if row["page_content"] != origin_doc["page_content"]:
                        if row["to_del"] not in ["Y", "y", 1]:
                            changed_docs.append(
                                {
                                    "page_content": row["page_content"],
                                    "type": row["type"],
                                    "metadata": json.loads(row["metadata"]),
                                }
                            )

                if changed_docs:
                    if api.update_kb_docs(
                        knowledge_base_name=selected_kb,
                        file_names=[file_name],
                        docs={file_name: changed_docs},
                    ):
                        st.toast("Update document successfully")
                    else:
                        st.toast("Update document failed")
