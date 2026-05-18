"""Parse markdown with inline `[mol:SMILES]` / `[rxn:RSMILES]` directives.

Renderable as alternating markdown sections and chemistry component blocks.
Pure function; no Streamlit dependency so tests can run without a server.
"""

import re
from dataclasses import dataclass

_DIRECTIVE_RE = re.compile(
    r"^\s*\[(?P<kind>mol|rxn):(?P<payload>[^\]]+)\]\s*$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class MarkdownBlock:
    text: str


@dataclass(frozen=True)
class MoleculeBlock:
    smiles: str


@dataclass(frozen=True)
class ReactionBlock:
    reaction_smiles: str


Block = MarkdownBlock | MoleculeBlock | ReactionBlock


def parse(markdown: str) -> list[Block]:
    """Split markdown into a sequence of renderable blocks."""
    blocks: list[Block] = []
    cursor = 0
    for match in _DIRECTIVE_RE.finditer(markdown):
        if match.start() > cursor:
            chunk = markdown[cursor : match.start()].strip("\n")
            if chunk:
                blocks.append(MarkdownBlock(chunk))
        payload = match["payload"].strip()
        blocks.append(
            MoleculeBlock(payload) if match["kind"] == "mol" else ReactionBlock(payload)
        )
        cursor = match.end()
    if cursor < len(markdown):
        tail = markdown[cursor:].strip("\n")
        if tail:
            blocks.append(MarkdownBlock(tail))
    return blocks


def format_citations(citations: list[dict[str, object]]) -> list[str]:
    """Render each citation as a numbered markdown bullet for the References footer.

    Pure function — tests can verify shape without booting Streamlit.

    Citation fields per chemclaw2 contract:
      label (str), source_type (str), source_id (str | None), disputed (bool).
    """
    lines: list[str] = []
    for i, c in enumerate(citations, start=1):
        label = str(c.get("label") or "(no label)")
        source_type = str(c.get("source_type") or "")
        source_id = c.get("source_id")
        source = source_type
        if source_id:
            source = f"{source_type} / {source_id}"
        disputed = " 🚩 disputed" if c.get("disputed") else ""
        suffix = f" — *{source}*" if source else ""
        lines.append(f"**[{i}]** {label}{suffix}{disputed}")
    return lines


def extract_markdown(page: dict[str, object]) -> str:
    """Pull the markdown source from a wiki page payload.

    Prefers `content.markdown` when the page was saved by this GUI
    (`content.version == "md1"`); falls back to `contentText` for
    legacy Tiptap-authored pages.
    """
    content = page.get("content")
    if isinstance(content, dict) and content.get("version") == "md1":
        md = content.get("markdown")
        if isinstance(md, str):
            return md
    text = page.get("content_text")
    return text if isinstance(text, str) else ""
