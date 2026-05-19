import re
from typing import Any

import httpx
import streamlit as st
from rdkit import Chem
from rdkit.Chem import AllChem, Draw
from streamlit_ketcher import st_ketcher

from app.components.api_client import (
    cached_subscription_slugs,
    get_wiki_page,
    list_projects,
    list_wiki_pages,
    mark_wiki_seen,
    patch_wiki_page,
    subscribe_wiki,
    unsubscribe_wiki,
    upsert_wiki_page,
)
from app.components.text_utils import relative_time
from app.components.wiki_render import (
    MarkdownBlock,
    MoleculeBlock,
    ReactionBlock,
    extract_markdown,
    format_citations,
    parse,
)

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
MATURITY_OPTIONS = ["exploratory", "validated", "production"]


def _render_blocks(markdown: str, key_prefix: str) -> None:
    for i, block in enumerate(parse(markdown)):
        if isinstance(block, MarkdownBlock):
            st.markdown(block.text)
        elif isinstance(block, MoleculeBlock):
            st_ketcher(block.smiles, height=300, key=f"{key_prefix}_mol_{i}")
        elif isinstance(block, ReactionBlock):
            try:
                rxn = AllChem.ReactionFromSmarts(block.reaction_smiles, useSmiles=True)  # type: ignore[attr-defined]
                img = Draw.ReactionToImage(rxn)  # type: ignore[no-untyped-call]
                st.image(img, caption=block.reaction_smiles)
            except Exception as exc:  # noqa: BLE001 — RDKit raises broad exceptions
                st.warning(f"Invalid reaction SMILES: `{block.reaction_smiles}` ({exc})")


def _list_view() -> None:
    st.subheader("Pages")

    with st.sidebar:
        st.caption("Filters")
        try:
            projects = list_projects()
        except httpx.HTTPError:
            projects = []
        project_choices = ["(all projects)", *projects]
        chosen = st.selectbox("Project", project_choices, key="wiki_project_filter")
        project = None if chosen == "(all projects)" else chosen
        include_archived = st.checkbox("Include archived", value=False, key="wiki_include_archived")

    col_search, col_new = st.columns([3, 1])
    with col_search:
        st.caption("Use the Search page for full-text wiki search.")
    with col_new:
        if st.button("New page", type="primary"):
            st.session_state.wiki_mode = "new"
            st.rerun()

    try:
        data = list_wiki_pages(project=project, include_archived=include_archived)
    except httpx.HTTPError as exc:
        st.error(f"Failed to load wiki pages: {exc}")
        return

    pages = data.get("pages", [])
    if not pages:
        st.info("No wiki pages match these filters.")
        return

    for page in pages:
        slug = page["slug"]
        title = page.get("title", slug)
        prefix = "📦 " if page.get("archived") else "📄 "
        review_tag = " · _needs review_" if page.get("needs_review") else ""
        if st.button(f"{prefix}{title}{review_tag}", key=f"open_{slug}", use_container_width=True):
            st.session_state.wiki_slug = slug
            st.session_state.wiki_mode = "view"
            st.rerun()


def _metadata_expander(slug: str, page: dict[str, Any]) -> None:
    """PATCH metadata form (needs_review / archived / maturity / project)."""
    with st.expander("Metadata", expanded=False):
        current_maturity = page.get("maturity") or "exploratory"
        try:
            default_idx = MATURITY_OPTIONS.index(current_maturity)
        except ValueError:
            # Backend allows free-text; surface unknown values + fall back gracefully.
            st.caption(f"Stored value `{current_maturity}` not in standard list.")
            default_idx = 0

        col1, col2 = st.columns(2)
        with col1:
            needs_review = st.checkbox(
                "Needs review", value=bool(page.get("needs_review")), key=f"meta_review_{slug}"
            )
            archived = st.checkbox(
                "Archived", value=bool(page.get("archived")), key=f"meta_archived_{slug}"
            )
        with col2:
            maturity = st.selectbox(
                "Maturity", MATURITY_OPTIONS, index=default_idx, key=f"meta_maturity_{slug}"
            )
            project = st.text_input(
                "Project", value=page.get("project") or "", key=f"meta_project_{slug}"
            )

        if st.button("Save metadata", key=f"meta_save_{slug}"):
            # Only send fields the user actually changed; reduces noise in audit log.
            changes: dict[str, Any] = {}
            if needs_review != bool(page.get("needs_review")):
                changes["needs_review"] = needs_review
            if archived != bool(page.get("archived")):
                changes["archived"] = archived
            if maturity != current_maturity:
                changes["maturity"] = maturity
            if (project or None) != (page.get("project") or None):
                # Backend treats empty string as a value; coerce to None for "unset".
                changes["project"] = project or None

            if not changes:
                st.info("No metadata changes to save.")
                return
            try:
                patch_wiki_page(slug, **changes)
            except httpx.HTTPError as exc:
                st.error(f"Metadata save failed: {exc}")
                return
            st.success("Metadata saved.")
            st.rerun()


def _citations_footer(page: dict[str, Any]) -> None:
    """Render the page's citations as a numbered ## References footer."""
    lines = format_citations(page.get("citations") or [])
    if not lines:
        return
    st.markdown("---")
    st.markdown("## References")
    for line in lines:
        st.markdown(line)


def _view_or_edit(slug: str) -> None:
    try:
        page = get_wiki_page(slug)
    except httpx.HTTPError as exc:
        st.error(f"Failed to load page `{slug}`: {exc}")
        return

    markdown = extract_markdown(page)
    title = page.get("title", slug)
    mode = st.session_state.get("wiki_mode", "view")
    dirty_key = f"wiki_dirty_{slug}"

    col_back, col_edit, col_sub = st.columns([2, 1, 1])
    with col_back:
        if mode == "edit" and st.session_state.get(dirty_key):
            # Guarded back: require explicit Discard click while dirty.
            st.warning("Unsaved changes")
            if st.button("Discard and go back", key=f"discard_{slug}"):
                st.session_state[dirty_key] = False
                st.session_state.wiki_mode = "list"
                st.rerun()
        else:
            if st.button("← Back to list"):
                st.session_state.wiki_mode = "list"
                st.rerun()
    with col_edit:
        if mode == "view" and st.button("✏️ Edit", type="primary"):
            st.session_state.wiki_mode = "edit"
            st.rerun()
    with col_sub:
        if mode == "view":
            _subscribe_button(slug)

    if mode == "view":
        st.title(title)
        _freshness_header(page)
        _metadata_expander(slug, page)
        _render_blocks(markdown, key_prefix=f"view_{slug}")
        _citations_footer(page)
        _auto_mark_seen(slug, page)
    else:
        _edit_form(slug, title, markdown)


def _subscribe_button(slug: str) -> None:
    """Toggle subscription for the current page."""
    subscribed = slug in cached_subscription_slugs()
    if subscribed:
        if st.button("🔕 Unsubscribe", key=f"unsub_{slug}"):
            try:
                unsubscribe_wiki(slug)
            except httpx.HTTPError as exc:
                st.error(f"Unsubscribe failed: {exc}")
                return
            st.rerun()
    else:
        if st.button("🔔 Subscribe", key=f"sub_{slug}"):
            try:
                subscribe_wiki(slug)
            except httpx.HTTPError as exc:
                st.error(f"Subscribe failed: {exc}")
                return
            st.rerun()


def _auto_mark_seen(slug: str, page: dict[str, Any]) -> None:
    """Mark the current page version as seen when the user opens it.

    Only fires once per (slug, version) per Streamlit session to avoid spamming
    the backend on every rerun, and only for pages the user is subscribed to —
    no-op for the unsubscribed case.
    """
    if slug not in cached_subscription_slugs():
        return
    version = page.get("version")
    if not isinstance(version, int):
        return
    key = f"wiki_seen_{slug}_{version}"
    if st.session_state.get(key):
        return
    try:
        mark_wiki_seen(slug, version)
    except httpx.HTTPError:
        return  # silent — best-effort
    st.session_state[key] = True


def _freshness_header(page: dict[str, Any]) -> None:
    """One-line caption: updated time, by whom, version, maturity badge."""
    updated = relative_time(page.get("updated_at"))
    updated_by = page.get("updated_by") or "system"
    version = page.get("version") or 1
    maturity = page.get("maturity") or "exploratory"
    badges = []
    if page.get("archived"):
        badges.append("📦 archived")
    if page.get("needs_review"):
        badges.append("⚠️ needs review")
    badge_str = " · ".join(badges)
    parts = [f"Updated **{updated}** by `{updated_by}`", f"v{version}", f"maturity: **{maturity}**"]
    if badge_str:
        parts.append(badge_str)
    st.caption(" · ".join(parts))


def _edit_form(slug: str, title: str, markdown: str) -> None:
    dirty_key = f"wiki_dirty_{slug}"
    dirty = st.session_state.get(dirty_key, False)
    marker = "● " if dirty else ""
    st.subheader(f"{marker}Editing `{slug}`")

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

    # Re-evaluate dirty state every rerun so the marker is always accurate.
    st.session_state[dirty_key] = new_markdown != markdown or new_title != title

    if st.button("Save", type="primary"):
        try:
            upsert_wiki_page(slug, new_title, new_markdown)
        except httpx.HTTPError as exc:
            st.error(f"Save failed: {exc}")
            return
        st.session_state[dirty_key] = False
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
