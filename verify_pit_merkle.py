#!/usr/bin/env python3
"""Standalone offline PIT Merkle verifier & Base anchor helper for news402-v25.58.

Pure Python standard library (zero third-party dependencies).
Implements the exact canonical SHA-256 row hash and deterministic sorted-leaf
Merkle tree specification (`sha256-merkle-v1`) executed inside the Cloudflare
Worker (`news402-v25.58.js`), plus Base (`eip155:8453`) calldata verification and
unsigned anchor transaction builder.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

MERKLE_ALGORITHM = "sha256-merkle-v1"
MERKLE_EMPTY_ROOT = hashlib.sha256(b"").hexdigest()
CANONICAL_FIELDS = ("first_seen_at", "link", "published_at", "publisher", "title")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
BASE_CHAIN_ID = 8453
BASE_NETWORK = "eip155:8453"


def sha256_hex(text: str) -> str:
    """Return lowercase 64-char SHA-256 hex digest of UTF-8 encoded text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_row_json(row: dict[str, Any]) -> str:
    """Serialize the 5 canonical PIT row fields deterministically (matching JS JSON.stringify)."""
    payload = {field: row.get(field, None) for field in CANONICAL_FIELDS}
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False, sort_keys=True)


def compute_row_hash(row: dict[str, Any]) -> str:
    """Compute canonical SHA-256 hex digest for one news row."""
    return sha256_hex(canonical_row_json(row))


def build_merkle_tree(hashes: Iterable[str]) -> dict[str, Any]:
    """Build deterministic sorted-leaf Merkle tree (`sha256-merkle-v1`)."""
    leaves = sorted({h.lower() for h in hashes if isinstance(h, str) and HEX64_RE.match(h.lower())})
    if not leaves:
        return {
            "algorithm": MERKLE_ALGORITHM,
            "leaves": [],
            "levels": [],
            "merkle_root": MERKLE_EMPTY_ROOT,
            "leaf_count": 0,
        }
    levels: list[list[str]] = [leaves]
    current = leaves
    while len(current) > 1:
        nxt: list[str] = []
        for i in range(0, len(current), 2):
            left = current[i]
            right = current[i + 1] if i + 1 < len(current) else current[i]
            nxt.append(sha256_hex(f"{left}:{right}"))
        levels.append(nxt)
        current = nxt
    return {
        "algorithm": MERKLE_ALGORITHM,
        "leaves": leaves,
        "levels": levels,
        "merkle_root": current[0],
        "leaf_count": len(leaves),
    }


def build_merkle_from_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Compute canonical hashes for rows and build the Merkle tree."""
    return build_merkle_tree(compute_row_hash(row) for row in rows)


def get_inclusion_proof(tree: dict[str, Any], row_hash: str) -> tuple[int | None, list[dict[str, str]]]:
    """Return (leaf_index, proof) for row_hash in a built Merkle tree, or (None, [])."""
    target = row_hash.lower()
    leaves: list[str] = tree["leaves"]
    try:
        leaf_index = leaves.index(target)
    except ValueError:
        return None, []
    proof: list[dict[str, str]] = []
    idx = leaf_index
    levels: list[list[str]] = tree["levels"]
    for lvl in range(len(levels) - 1):
        nodes = levels[lvl]
        if idx % 2 == 0:
            sibling = nodes[idx + 1] if idx + 1 < len(nodes) else nodes[idx]
            proof.append({"sibling": sibling, "position": "right"})
        else:
            proof.append({"sibling": nodes[idx - 1], "position": "left"})
        idx //= 2
    return leaf_index, proof


def verify_merkle_proof(row_hash: str, proof: list[dict[str, Any]], expected_root: str) -> bool:
    """Mathematically verify a `sha256-merkle-v1` inclusion proof offline."""
    if not isinstance(row_hash, str) or not isinstance(expected_root, str):
        return False
    cur = row_hash.lower()
    root = expected_root.lower()
    if not HEX64_RE.match(cur) or not HEX64_RE.match(root):
        return False
    if not isinstance(proof, list):
        return False
    for step in proof:
        if not isinstance(step, dict):
            return False
        sibling = str(step.get("sibling", "")).lower()
        position = step.get("position")
        if not HEX64_RE.match(sibling):
            return False
        if position == "left":
            cur = sha256_hex(f"{sibling}:{cur}")
        elif position == "right":
            cur = sha256_hex(f"{cur}:{sibling}")
        else:
            return False
    return cur == root


def verify_api_response(
    verify_payload: dict[str, Any],
    row: dict[str, Any] | None = None,
    expected_root: str | None = None,
) -> dict[str, Any]:
    """Verify a JSON payload returned by GET/POST /v1/verify (and optionally a raw row & root)."""
    errors: list[str] = []
    algo = verify_payload.get("algorithm")
    if algo != MERKLE_ALGORITHM:
        errors.append(f"unexpected algorithm: {algo!r}")

    claimed_verified = bool(verify_payload.get("verified"))
    api_hash = str(verify_payload.get("row_hash", "")).lower()
    api_root = str(verify_payload.get("merkle_root", "")).lower()
    proof = verify_payload.get("proof", [])

    recomputed_hash: str | None = None
    if row is not None:
        recomputed_hash = compute_row_hash(row)
        if recomputed_hash != api_hash:
            errors.append(f"row_hash mismatch: local={recomputed_hash} api={api_hash}")

    if expected_root is not None and expected_root.lower() != api_root:
        errors.append(f"merkle_root mismatch: expected={expected_root.lower()} api={api_root}")

    proof_valid = verify_merkle_proof(api_hash, proof, api_root) if claimed_verified else False
    if claimed_verified and not proof_valid:
        errors.append("merkle inclusion proof failed offline verification")

    return {
        "ok": len(errors) == 0 and claimed_verified and proof_valid,
        "claimed_verified": claimed_verified,
        "proof_valid": proof_valid,
        "row_hash": api_hash,
        "recomputed_hash": recomputed_hash,
        "merkle_root": api_root,
        "proof_steps": len(proof) if isinstance(proof, list) else 0,
        "errors": errors,
    }


def build_base_anchor_calldata(date_utc: str, merkle_root: str, leaf_count: int) -> dict[str, Any]:
    """Build deterministic Base (`eip155:8453`) calldata memo & unsigned self-anchor tx template."""
    root = merkle_root.lower()
    if not HEX64_RE.match(root):
        raise ValueError("merkle_root must be a 64-char lowercase hex SHA-256 digest")
    memo = f"NEWS402:PIT:V1:{date_utc}:{root}:{int(leaf_count)}"
    calldata_hex = "0x" + memo.encode("utf-8").hex()
    return {
        "network": BASE_NETWORK,
        "chain_id": BASE_CHAIN_ID,
        "memo": memo,
        "calldata_hex": calldata_hex,
    }


def build_unsigned_base_anchor_tx(
    anchor_address: str, date_utc: str, merkle_root: str, leaf_count: int
) -> dict[str, Any]:
    """Construct an unsigned 0-value Base calldata transaction payload (never broadcasts)."""
    anchor = build_base_anchor_calldata(date_utc, merkle_root, leaf_count)
    return {
        "chainId": BASE_CHAIN_ID,
        "to": anchor_address,
        "value": "0x0",
        "data": anchor["calldata_hex"],
        "memo": anchor["memo"],
        "network": BASE_NETWORK,
    }


def decode_base_anchor_calldata(calldata_hex: str) -> dict[str, Any]:
    """Decode and validate a Base `NEWS402:PIT:V1:...` calldata_hex payload."""
    if not isinstance(calldata_hex, str) or not calldata_hex.startswith("0x"):
        raise ValueError("calldata_hex must start with 0x")
    raw = bytes.fromhex(calldata_hex[2:])
    memo = raw.decode("utf-8")
    parts = memo.split(":")
    if len(parts) != 6 or parts[:3] != ["NEWS402", "PIT", "V1"]:
        raise ValueError(f"unexpected anchor memo format: {memo!r}")
    date_utc, merkle_root, leaf_count_str = parts[3], parts[4], parts[5]
    if not HEX64_RE.match(merkle_root):
        raise ValueError(f"invalid merkle_root in calldata: {merkle_root!r}")
    return {
        "memo": memo,
        "date_utc": date_utc,
        "merkle_root": merkle_root,
        "leaf_count": int(leaf_count_str),
    }


def _cmd_hash_row(args: argparse.Namespace) -> int:
    row = json.loads(Path(args.row_json).read_text(encoding="utf-8"))
    print(json.dumps({"canonical_json": canonical_row_json(row), "row_hash": compute_row_hash(row)}, indent=2))
    return 0


def _cmd_build_tree(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.rows_json).read_text(encoding="utf-8"))
    rows = data["items"] if isinstance(data, dict) and "items" in data else data
    tree = build_merkle_from_rows(rows)
    out = {
        "algorithm": tree["algorithm"],
        "leaf_count": tree["leaf_count"],
        "merkle_root": tree["merkle_root"],
    }
    if args.date:
        out["chain_anchor"] = build_base_anchor_calldata(args.date, tree["merkle_root"], tree["leaf_count"])
    print(json.dumps(out, indent=2))
    return 0


def _cmd_verify_proof(args: argparse.Namespace) -> int:
    verify_payload = json.loads(Path(args.verify_json).read_text(encoding="utf-8"))
    row = json.loads(Path(args.row_json).read_text(encoding="utf-8")) if args.row_json else None
    result = verify_api_response(verify_payload, row=row, expected_root=args.root)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


def _cmd_anchor_tx(args: argparse.Namespace) -> int:
    merkle_payload = json.loads(Path(args.merkle_json).read_text(encoding="utf-8"))
    addr = args.to or merkle_payload.get("chain_anchor", {}).get("pay_to") or "0x97EA9650acB8eC97672CB14b7CE0a71092981022"
    tx = build_unsigned_base_anchor_tx(
        anchor_address=addr,
        date_utc=merkle_payload["date_utc"],
        merkle_root=merkle_payload["merkle_root"],
        leaf_count=merkle_payload["leaf_count"],
    )
    api_calldata = merkle_payload.get("chain_anchor", {}).get("calldata_hex")
    tx["matches_api_calldata"] = api_calldata == tx["data"] if api_calldata else None
    print(json.dumps(tx, indent=2))
    return 0 if tx["matches_api_calldata"] is not False else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline SHA-256 PIT Merkle verifier & Base anchor helper.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_hash = sub.add_parser("hash-row", help="Compute canonical SHA-256 row_hash for a JSON row file.")
    p_hash.add_argument("row_json")
    p_hash.set_defaults(func=_cmd_hash_row)

    p_tree = sub.add_parser("build-tree", help="Compute sha256-merkle-v1 root from a JSON array of rows.")
    p_tree.add_argument("rows_json")
    p_tree.add_argument("--date", help="Optional UTC YYYY-MM-DD date to include Base anchor calldata.")
    p_tree.set_defaults(func=_cmd_build_tree)

    p_ver = sub.add_parser("verify-proof", help="Verify a /v1/verify JSON proof offline.")
    p_ver.add_argument("verify_json")
    p_ver.add_argument("--row-json", help="Optional raw row JSON file to also recompute row_hash.")
    p_ver.add_argument("--root", help="Optional expected merkle_root hex to pin against.")
    p_ver.set_defaults(func=_cmd_verify_proof)

    p_anc = sub.add_parser("anchor-tx", help="Build unsigned Base anchor transaction from /v1/merkle JSON.")
    p_anc.add_argument("merkle_json")
    p_anc.add_argument("--to", help="Target Base anchor address (defaults to chain_anchor.pay_to).")
    p_anc.set_defaults(func=_cmd_anchor_tx)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
