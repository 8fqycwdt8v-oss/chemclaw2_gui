"""Search proxy.

Text search is a plain pass-through. Compound and reaction similarity require
computing a fingerprint client-side first — the chemclaw2 backend's POST /api/search
expects the 2048-bit binary string, not raw SMILES. We use RDKit (Morgan/ECFP4)
and DRFP — the same libraries the chemclaw2 MCP servers use, so the bits match.
"""

from typing import Any

from drfp import DrfpEncoder
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from rdkit import Chem
from rdkit.Chem import AllChem

from bff.auth import require_user
from bff.chemclaw_client import client

router = APIRouter()


class CompoundSearch(BaseModel):
    smiles: str
    limit: int = 20


class ReactionSearch(BaseModel):
    reaction_smiles: str
    limit: int = 20


def _morgan_bits(smiles: str) -> str:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise HTTPException(400, f"Invalid SMILES: {smiles}")
    fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=2048)
    return fp.ToBitString()


def _drfp_bits(rxn_smiles: str) -> str:
    try:
        # DrfpEncoder.encode returns a list of np.uint8 arrays of length 2048.
        fps = DrfpEncoder.encode([rxn_smiles], n_folded_length=2048)
    except Exception as exc:  # noqa: BLE001 — DRFP raises generic exceptions
        raise HTTPException(400, f"Invalid reaction SMILES: {exc}") from exc
    if not fps:
        raise HTTPException(400, "DRFP returned no fingerprint")
    return "".join("1" if bit else "0" for bit in fps[0])


@router.get("/search")
async def search_text(
    q: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(20, ge=1, le=50),
    user: dict[str, str] = Depends(require_user),
) -> dict[str, Any]:
    async with client(user["sub"], user["token"]) as c:
        r = await c.get("/api/search", params={"q": q, "limit": limit})
        r.raise_for_status()
        return r.json()


@router.post("/search/compound")
async def search_compound(
    body: CompoundSearch, user: dict[str, str] = Depends(require_user)
) -> dict[str, Any]:
    bits = _morgan_bits(body.smiles)
    async with client(user["sub"], user["token"]) as c:
        r = await c.post(
            "/api/search",
            json={"fingerprint_bits": bits, "limit": body.limit},
        )
        r.raise_for_status()
        return r.json()


@router.post("/search/reaction")
async def search_reaction(
    body: ReactionSearch, user: dict[str, str] = Depends(require_user)
) -> dict[str, Any]:
    bits = _drfp_bits(body.reaction_smiles)
    async with client(user["sub"], user["token"]) as c:
        r = await c.post(
            "/api/search",
            json={"rxn_fingerprint_bits": bits, "limit": body.limit},
        )
        r.raise_for_status()
        return r.json()
