from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_CONVERSION_EXTENSIONS = {".pdf", ".docx", ".pptx", ".epub"}


@dataclass
class ConversionResult:
    success: bool
    markdown_text: str | None
    source_format: str
    error_message: str | None = None


@dataclass
class ConversionQuality:
    char_count: int
    paragraph_count: int
    is_low_quality: bool
    warning: str | None = None


def convert_to_markdown(source_path: Path) -> ConversionResult:
    """Convert a PDF/DOCX/PPTX file to Markdown using markitdown."""
    suffix = source_path.suffix.lower()
    source_format = suffix.lstrip(".")

    if suffix not in SUPPORTED_CONVERSION_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_CONVERSION_EXTENSIONS))
        return ConversionResult(
            success=False,
            markdown_text=None,
            source_format=source_format,
            error_message=f"不支持的文件格式：{suffix}。支持的格式：{supported}",
        )

    try:
        from markitdown import MarkItDown

        converter = MarkItDown()
        result = converter.convert(str(source_path))
        text = result.text_content or ""
    except Exception as exc:
        return ConversionResult(
            success=False,
            markdown_text=None,
            source_format=source_format,
            error_message=f"转换失败：{exc}",
        )

    return ConversionResult(
        success=True,
        markdown_text=text.strip(),
        source_format=source_format,
    )


def assess_conversion_quality(text: str) -> ConversionQuality:
    """Assess the quality of converted Markdown text."""
    if not text or not text.strip():
        return ConversionQuality(
            char_count=0,
            paragraph_count=0,
            is_low_quality=True,
            warning="转换内容为空，可能是扫描件 PDF 或损坏的文件",
        )

    char_count = len(text)
    paragraphs = [paragraph for paragraph in text.split("\n\n") if paragraph.strip()]
    paragraph_count = len(paragraphs)

    garbled_pattern = re.compile(r"[\ufffd\x00-\x08\x0b\x0c\x0e-\x1f]")
    garbled_count = len(garbled_pattern.findall(text))
    garbled_ratio = garbled_count / max(char_count, 1)

    if garbled_ratio > 0.15:
        return ConversionQuality(
            char_count=char_count,
            paragraph_count=paragraph_count,
            is_low_quality=True,
            warning=f"转换质量较低（乱码比例 {garbled_ratio:.0%}），建议下载后在外部编辑器检查",
        )

    if char_count < 50:
        return ConversionQuality(
            char_count=char_count,
            paragraph_count=paragraph_count,
            is_low_quality=True,
            warning="转换内容极少（不足 50 字），可能丢失了大量内容",
        )

    return ConversionQuality(
        char_count=char_count,
        paragraph_count=paragraph_count,
        is_low_quality=False,
    )
