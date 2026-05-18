from app.components.wiki_render import (
    MarkdownBlock,
    MoleculeBlock,
    ReactionBlock,
    extract_markdown,
    format_citations,
    parse,
)


def test_plain_markdown_is_one_block() -> None:
    assert parse("# hi\n\nbody") == [MarkdownBlock("# hi\n\nbody")]


def test_single_mol_directive_isolated() -> None:
    assert parse("[mol:CCO]") == [MoleculeBlock("CCO")]


def test_directive_between_markdown_sections() -> None:
    md = "intro\n\n[mol:CCO]\n\nafter"
    assert parse(md) == [MarkdownBlock("intro"), MoleculeBlock("CCO"), MarkdownBlock("after")]


def test_reaction_directive() -> None:
    md = "first\n[rxn:CC(=O)Cl.OCC>>CC(=O)OCC.Cl]\nsecond"
    blocks = parse(md)
    assert blocks == [
        MarkdownBlock("first"),
        ReactionBlock("CC(=O)Cl.OCC>>CC(=O)OCC.Cl"),
        MarkdownBlock("second"),
    ]


def test_inline_brackets_are_not_directives() -> None:
    # A [mol:...] embedded inside a paragraph is not parsed — only own-line directives.
    md = "the SMILES [mol:CCO] appears inline"
    assert parse(md) == [MarkdownBlock(md)]


def test_multiple_consecutive_directives() -> None:
    md = "[mol:CCO]\n[mol:CCC]\n[rxn:A>>B]"
    assert parse(md) == [MoleculeBlock("CCO"), MoleculeBlock("CCC"), ReactionBlock("A>>B")]


def test_extract_markdown_prefers_md1_content() -> None:
    page = {
        "content": {"version": "md1", "markdown": "# from content"},
        "contentText": "stale plain text",
    }
    assert extract_markdown(page) == "# from content"


def test_extract_markdown_falls_back_to_content_text() -> None:
    # Non-md1 page (e.g. agent-authored): backend returns content_text (snake_case).
    page = {
        "content": {"type": "doc", "content": []},
        "content_text": "legacy text",
    }
    assert extract_markdown(page) == "legacy text"


def test_extract_markdown_empty_when_missing() -> None:
    assert extract_markdown({}) == ""


def test_format_citations_empty_input() -> None:
    assert format_citations([]) == []


def test_format_citations_full_shape() -> None:
    cites = [
        {
            "id": "uuid-1",
            "citation_id": "ref-1",
            "source_type": "paper",
            "source_id": "10.1234/foo",
            "label": "Smith et al. 2024",
            "disputed": False,
        },
        {
            "id": "uuid-2",
            "citation_id": "ref-2",
            "source_type": "internal_eln",
            "source_id": None,
            "label": "EXP-001",
            "disputed": True,
        },
    ]
    lines = format_citations(cites)
    assert len(lines) == 2
    assert lines[0] == "**[1]** Smith et al. 2024 — *paper / 10.1234/foo*"
    assert lines[1] == "**[2]** EXP-001 — *internal_eln* 🚩 disputed"


def test_format_citations_missing_label_falls_back() -> None:
    lines = format_citations([{"source_type": "paper"}])
    assert lines == ["**[1]** (no label) — *paper*"]
