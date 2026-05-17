import httpx
import streamlit as st

from app.components.api_client import search_compound, search_reaction, search_text

st.title("Search")

text_tab, compound_tab, reaction_tab = st.tabs(
    ["Text (wiki FTS)", "Compound (Morgan)", "Reaction (DRFP)"]
)

with text_tab:
    q = st.text_input("Query", key="text_q")
    limit = st.slider("Limit", 5, 50, 20, key="text_limit")
    if st.button("Search", key="text_btn"):
        try:
            data = search_text(q, limit=limit)
        except httpx.HTTPError as exc:
            st.error(f"Search failed: {exc}")
        else:
            hits = data.get("wiki", [])
            if not hits:
                st.info("No matches.")
            for hit in hits:
                st.markdown(f"**{hit.get('title')}** — `{hit.get('slug')}`")
                if excerpt := hit.get("excerpt"):
                    st.caption(excerpt)

with compound_tab:
    smiles = st.text_input("Compound SMILES", placeholder="e.g. CC(=O)Oc1ccccc1C(=O)O", key="cmp_q")
    limit = st.slider("Limit", 5, 50, 20, key="cmp_limit")
    if st.button("Search", key="cmp_btn"):
        try:
            data = search_compound(smiles, limit=limit)
        except httpx.HTTPError as exc:
            st.error(f"Search failed: {exc}")
        else:
            results = data.get("results", [])
            if not results:
                st.info("No similar compounds found.")
            st.dataframe(results, use_container_width=True)

with reaction_tab:
    rxn_smiles = st.text_input(
        "Reaction SMILES (`reactants>>products`)",
        placeholder="e.g. CC(=O)Cl.OCC>>CC(=O)OCC.Cl",
        key="rxn_q",
    )
    limit = st.slider("Limit", 5, 50, 20, key="rxn_limit")
    if st.button("Search", key="rxn_btn"):
        try:
            data = search_reaction(rxn_smiles, limit=limit)
        except httpx.HTTPError as exc:
            st.error(f"Search failed: {exc}")
        else:
            results = data.get("results", [])
            if not results:
                st.info("No similar reactions found.")
            st.dataframe(results, use_container_width=True)
