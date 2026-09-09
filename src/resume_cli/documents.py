"""Page-aware text and offsets calculated locally, never supplied by a model."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class TextPage:
    number: int | None
    text: str
    method: Literal["text", "pdf_text", "pdf_layout", "ocr"] = "text"


@dataclass(frozen=True)
class ParsedDocument:
    pages: tuple[TextPage, ...]

    @property
    def text(self) -> str:
        return "\n\n".join(page.text for page in self.pages)

    @classmethod
    def from_text(cls, text: str) -> "ParsedDocument":
        # A plain string has no verified PDF page number.
        return cls((TextPage(None, text),))


def locate_quote(text: str, quote: str) -> dict[str, int] | None:
    """First whitespace-insensitive occurrence, with offsets into the original text."""
    offsets = [index for index, character in enumerate(text) if not character.isspace()]
    compact = "".join(text[index] for index in offsets)
    needle = "".join(quote.split())
    if not needle:
        return None
    position = compact.find(needle)
    if position < 0:
        return None
    start = offsets[position]
    end = offsets[position + len(needle) - 1] + 1
    return {
        "start_char": start,
        "end_char": end,
        "line_start": text.count("\n", 0, start) + 1,
        "line_end": text.count("\n", 0, end - 1) + 1,
    }
