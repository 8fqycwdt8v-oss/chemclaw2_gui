import re

import httpx
import streamlit as st
from rdkit import Chem
from rdkit.Chem import AllChem, Draw
from streamlit_ketcher import st_ketcher

from app.components.api_client import get_wiki_page, list_wiki_pages, upsert_wiki_page
from app.components.wiki_render import (
    MarkdownBlock,
    MoleculeBlock,
    ReactionBlock,
    extract_markdown,
    parse,
)

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _render_blocks(markdown: str, key_prefix: str) -> None:
    for i, block in enumerate(parse(markdown)):
        if isinstance(block, MarkdownBlock):
            st.markdown(block.text)
        elif isinstance(block, MoleculeBlock):
            st_ketcher(block.smiles, height=300, key=f"{key_prefix}_mol_{i}")
        elif isinstance(block, ReactionBlock):
            try:
                rxn = AllChem.ReactionFromSmarts(block.reaction_smiles, useSmiles=True)
                img = Draw.ReactionToImage(rxn)
                st.image(img, caption=block.reaction_smiles)
            except Exception as exc:  # noqa: BLE001 — RDKit raises broad exceptions
                st.warning(f"Invalid reaction SMILES: `{block.reaction_smiles}` ({exc})")


def _list_view() -> None:
    st.subheader("Pages")
    col_search, col_new = st.columns([3, 1])
    with col_search:
        # Search is a nice-to-have on this page; defer wiring to /search page for v1.
        st.caption("Use the Search page for full-text wiki search.")
    with col_new:
        if st.button("New page", type="primary"):
            st.session_state.wiki_mode = "new"
            st.rerun()

    try:
        data = list_wiki_pages()
    except httpx.HTTPError as exc:
        st.error(f"Failed to load wiki pages: {exc}")
        return

    pages = data.get("pages", [])
    if not pages:
        st.info("No wiki pages yet. Click **New page** to create one.")
        return

    for page in pages:
        slug = page["slug"]
        title = page.get("title", slug)
        if st.button(f"📄 {title}", key=f"open_{slug}", use_container_width=True):
            st.session_state.wiki_slug = slug
            st.session_state.wiki_mode = "view"
            st.rerun()


def _view_or_edit(slug: str) -> None:
    try:
        page = get_wiki_page(slug)
    except httpx.HTTPError as exc:
        st.error(f"Failed to load page `{slug}`: {exc}")
        return

    markdown = extract_markdown(page)
    title = page.get("title", slug)

    col_back, col_edit = st.columns([1, 1])
    with col_back:
        if st.button("← Back to list"):
            st.session_state.wiki_mode = "list"
            st.rerun()
    with col_edit:
        if st.session_state.get("wiki_mode") == "view" and st.button("✏️ Edit", type="primary"):
            st.session_state.wiki_mode = "edit"
            st.rerun()

    if st.session_state.get("wiki_mode") == "view":
        st.title(title)
        _render_blocks(markdown, key_prefix=f"view_{slug}")
    else:
        _edit_form(slug, title, markdown)


def _edit_form(slug: str, title: str, markdown: str) -> None:
    st.subheader(f"Editing `{slug}`")
    new_title = st.text_input("Title", value=title)
    source_col, preview_col = st.columns(2)
    with source_col:
        new_markdown = st.text_area(
            "Markdown source",
            value=markdown,
            height=500,
            help="Embed chemistry with `[mol:SMILES]` or `[rxn:RSMILES]` on their own line.",
        )
    with preview_col:
        st.caption("Preview")
        _render_blocks(new_markdown, key_prefix=f"preview_{slug}")

    if st.button("Save", type="primary"):
        try:
            upsert_wiki_page(slug, new_title, new_markdown)
        except httpx.HTTPError as exc:
            st.error(f"Save failed: {exc}")
            return
        st.success("Saved.")
        st.session_state.wiki_mode = "view"
        st.rerun()


def _new_page_form() -> None:
    st.subheader("New page")
    slug = st.text_input(
        "Slug", help="lowercase letters, numbers, hyphens — e.g. aspirin-synthesis"
    )
    title = st.text_input("Title")
    markdown = st.text_area("Markdown source", height=400)
    col_cancel, col_create = st.columns([1, 1])
    with col_cancel:
        if st.button("Cancel"):
            st.session_state.wiki_mode = "list"
            st.rerun()
    with col_create:
        if st.button("Create", type="primary"):
            if not SLUG_RE.match(slug or "") or len(slug) > 200:
                st.error("Slug must match `[a-z0-9-]+` and be ≤ 200 chars.")
                return
            if not title:
                st.error("Title is required.")
                return
            try:
                upsert_wiki_page(slug, title, markdown)
            except httpx.HTTPError as exc:
                st.error(f"Create failed: {exc}")
                return
            st.session_state.wiki_slug = slug
            st.session_state.wiki_mode = "view"
            st.rerun()


# Sanity-import to give a clearer ImportError than the page-load hook:
_ = Chem  # noqa: F841

mode = st.session_state.get("wiki_mode", "list")
if mode == "list":
    _list_view()
elif mode == "new":
    _new_page_form()
else:
    _view_or_edit(st.session_state.get("wiki_slug", ""))
