from typing import List

from langchain_community.document_loaders.unstructured import UnstructuredFileLoader

from rag.parsers.ocr import get_ocr
from utils.log_common import build_logger


logger = build_logger()


class RapidOCRLoader(UnstructuredFileLoader):

    def _get_elements(self) -> List:
        def img2text(filepath):
            resp = ""
            try:
                ocr = get_ocr()
                result, _ = ocr(filepath)
                if result:
                    ocr_result = [line[1] for line in result]
                    resp += "\n".join(ocr_result)
            except Exception as e:
                logger.error(f"Error during OCR for image {filepath}: {e}")
            return resp

        text = img2text(self.file_path)
        from unstructured.partition.text import partition_text

        return partition_text(text=text, strategy="fast", **self.unstructured_kwargs)
