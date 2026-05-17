"""Chemistry helpers — fingerprint compute that used to live in the BFF.

Both functions are pure: take a SMILES (or reaction SMILES), return a
2048-character `[01]` string suitable for chemclaw2's
POST /api/search {fingerprint_bits | rxn_fingerprint_bits}. Invalid input
raises ValueError — callers (Streamlit pages) translate that into
`st.error(...)` at the call site.

These match the fingerprint methods chemclaw2's MCP servers use
(RDKit Morgan/ECFP4 radius=2 nBits=2048; DRFP folded to 2048), so
bits produced here are comparable to bits stored in chemclaw2's DB.
"""

from drfp import DrfpEncoder
from rdkit import Chem
from rdkit.Chem import AllChem


def morgan_bits(smiles: str) -> str:
    """Morgan/ECFP4 fingerprint as a 2048-char binary string."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"Invalid SMILES: {smiles}")
    fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=2048)
    return fp.ToBitString()


def drfp_bits(rxn_smiles: str) -> str:
    """DRFP reaction fingerprint as a 2048-char binary string."""
    try:
        fps = DrfpEncoder.encode([rxn_smiles], n_folded_length=2048)
    except Exception as exc:  # noqa: BLE001 — DRFP raises generic exceptions
        raise ValueError(f"Invalid reaction SMILES: {exc}") from exc
    if not fps:
        raise ValueError("DRFP returned no fingerprint")
    return "".join("1" if bit else "0" for bit in fps[0])
