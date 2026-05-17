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
    text = page.get("contentText")
    return text if isinstance(text, str) else ""
