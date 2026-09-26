"""Bounded, transient document input; never accepts remote URLs or stores files."""

import base64
import binascii
from io import BytesIO
from pathlib import PurePosixPath
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile
from zlib import error as ZlibError

from app.ai_assistant.schemas import AIAttachment
from app.core.errors import ApiError

MAX_BYTES = 2 * 1024 * 1024
MAX_TEXT = 60_000


def attachment_content(file: AIAttachment) -> dict:
    try:
        data = base64.b64decode(file.data, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ApiError(400, "ai_file_invalid", "Faylni qayta tanlang.") from exc
    if not data or len(data) > MAX_BYTES:
        raise ApiError(400, "ai_file_size", "Fayl bo'sh yoki 2 MB dan katta.")
    name = PurePosixPath(file.name.replace("\\", "/")).name
    suffix = PurePosixPath(name).suffix.lower()
    mime = ""
    if suffix == ".pdf" and data.startswith(b"%PDF-"):
        mime = "application/pdf"
    elif suffix == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif suffix in (".jpg", ".jpeg") and data.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif suffix in (".txt", ".docx"):
        try:
            if suffix == ".txt":
                text = data.decode("utf-8-sig")
            else:
                with ZipFile(BytesIO(data)) as archive:
                    info = archive.getinfo("word/document.xml")
                    if info.file_size > MAX_BYTES:
                        raise ValueError("document too large")
                    xml = archive.read(info).decode("utf-8-sig")
                if "<!DOCTYPE" in xml or "<!ENTITY" in xml or "\x00" in xml:
                    raise ValueError("DTD not supported")
                root = ElementTree.fromstring(xml)
                ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
                text = "\n".join(
                    " ".join(node.itertext()) for node in root.iter(ns + "p")
                )
            if not text.strip() or len(text) > MAX_TEXT or "\x00" in text:
                raise ValueError("text empty or too large")
        except (
            ValueError,
            KeyError,
            BadZipFile,
            ElementTree.ParseError,
            RuntimeError,
            NotImplementedError,
            ZlibError,
        ) as exc:
            raise ApiError(
                400,
                "ai_file_text",
                "Matn o'qilmadi yoki juda uzun. Matnli DOCX/TXT (60 000 belgigacha) yoki PDF yuboring.",
            ) from exc
        return {"type": "input_text", "text": f"Hujjat: {name}\n{text}"}
    if not mime:
        raise ApiError(
            400, "ai_file_type", "PDF, DOCX, TXT, JPG yoki PNG fayl tanlang."
        )
    url = f"data:{mime};base64,{file.data}"
    if mime.startswith("image/"):
        return {"type": "input_image", "image_url": url, "detail": "auto"}
    return {"type": "input_file", "filename": name, "file_data": url}
