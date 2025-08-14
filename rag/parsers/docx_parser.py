from typing import List

import tqdm
from langchain_community.document_loaders.unstructured import UnstructuredFileLoader
from utils.log_common import build_logger


logger = build_logger()


class RapidOCRDocLoader(UnstructuredFileLoader):

    def _get_elements(self) -> List:
        def doc2text(filepath):
            from io import BytesIO

            import numpy as np
            from docx import Document as DocxDocument  # Renamed to avoid conflict
            from docx.image.part import ImagePart
            from docx.oxml.table import CT_Tbl
            from docx.oxml.text.paragraph import CT_P
            from docx.table import Table, _Cell
            from docx.text.paragraph import Paragraph
            from PIL import Image
            from rag.parsers.ocr import get_ocr

            try:
                ocr = get_ocr()
            except Exception as e:
                logger.error(
                    f"Failed to initialize OCR engine: {e}. OCR will be disabled."
                )
                ocr = None

            doc = DocxDocument(filepath)
            resp = ""

            def iter_block_items(parent):
                from docx.document import Document

                if isinstance(parent, Document):
                    parent_elm = parent.element.body
                elif isinstance(parent, _Cell):
                    parent_elm = parent._tc
                else:
                    raise ValueError("RapidOCRDocLoader parse fail")

                for child in parent_elm.iterchildren():
                    if isinstance(child, CT_P):
                        yield Paragraph(child, parent)
                    elif isinstance(child, CT_Tbl):
                        yield Table(child, parent)

            b_unit = tqdm.tqdm(
                total=len(list(iter_block_items(doc))),
                desc="RapidOCRDocLoader block index: 0",
            )
            for i, block in enumerate(iter_block_items(doc)):
                b_unit.set_description("RapidOCRDocLoader  block index: {}".format(i))
                b_unit.refresh()
                if isinstance(block, Paragraph):
                    resp += block.text.strip() + "\n"
                    if ocr:
                        try:
                            images = block._element.xpath(".//pic:pic")
                            for image in images:
                                for img_id in image.xpath(".//a:blip/@r:embed"):
                                    part = doc.part.related_parts[img_id]
                                    if isinstance(part, ImagePart):
                                        image_bytes = BytesIO(part.blob)
                                        pil_image = Image.open(image_bytes)
                                        result, _ = ocr(np.array(pil_image))
                                        if result:
                                            ocr_result = [line[1] for line in result]
                                            resp += "\n" + "\n".join(ocr_result)
                        except Exception as e:
                            logger.error(
                                f"Error during OCR on docx image in {filepath}: {e}"
                            )
                elif isinstance(block, Table):
                    for row in block.rows:
                        for cell in row.cells:
                            for paragraph in cell.paragraphs:
                                resp += paragraph.text.strip() + "\n"
                b_unit.update(1)
            return resp

        text = doc2text(self.file_path)
        from unstructured.partition.text import partition_text

        return partition_text(text=text, strategy="fast", **self.unstructured_kwargs)
