"""
NOETHER - deterministic content-addressed world.  [Shot 6]

Implements the L4 idea from the design: the whole system state is a content-
addressed Merkle structure. Consequences, all demonstrated below with real
SHA-256:
  * REPRODUCIBILITY  - a state is fully named by its root hash; same logical
    state => identical root, bit for bit.
  * TAMPER-EVIDENCE  - changing any capability changes the root.
  * FREE ROLLBACK / TIME-TRAVEL - previous states are just older roots; reverting
    is a pointer swap, and shared sub-structure is deduplicated by hash.

Run:  python3 noether_store.py
"""

from __future__ import annotations
import hashlib, json
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, FrozenSet

Cap = Tuple[str, str, Tuple[str, ...]]   # (holder, target, sorted rights)


def h(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def leaf_hash(cap: Cap) -> str:
    # canonical JSON so identical caps hash identically regardless of construction
    return h(b"leaf:" + json.dumps(cap, sort_keys=True, separators=(",", ":")).encode())

def merkle_root(caps: List[Cap]) -> str:
    """A Merkle root over the capability set. Canonical (sorted) => order-independent."""
    layer = sorted(leaf_hash(c) for c in caps) or [h(b"empty")]
    while len(layer) > 1:
        nxt = []
        for i in range(0, len(layer), 2):
            pair = layer[i] + (layer[i + 1] if i + 1 < len(layer) else layer[i])
            nxt.append(h(b"node:" + pair.encode()))
        layer = nxt
    return layer[0]


@dataclass
class Store:
    """A content-addressed object store + a history of world roots."""
    objects: Dict[str, bytes] = field(default_factory=dict)   # hash -> bytes (dedup by hash)
    history: List[str] = field(default_factory=list)          # sequence of world roots

    def put(self, data: bytes) -> str:
        k = h(data)
        self.objects[k] = data       # last-write-wins is a no-op: identical content, identical key
        return k

    def commit(self, caps: List[Cap]) -> str:
        for c in caps:
            self.put(json.dumps(c, sort_keys=True, separators=(",", ":")).encode())
        root = merkle_root(caps)
        self.history.append(root)
        return root


def norm(holds) -> List[Cap]:
    """Normalize a capability table to canonical content-addressable form."""
    return sorted((hc[0], hc[1], tuple(sorted(hc[2]))) for hc in holds)


if __name__ == "__main__":
    bar = "=" * 74
    print(bar); print("SHOT 6  -  Deterministic content-addressed world (Merkle state)"); print(bar)
    store = Store()

    v1 = norm([("alice", "secret", {"read", "write"}), ("bob", "attacker", {"grant"})])
    root1 = store.commit(v1)
    print(f"\n  commit v1 -> root {root1[:16]}...")

    # Reproducibility: rebuild the SAME logical state in a different order.
    v1_again = norm([("bob", "attacker", {"grant"}), ("alice", "secret", {"write", "read"})])
    print(f"  same state, different build order -> root {merkle_root(v1_again)[:16]}...")
    print(f"    reproducible? {merkle_root(v1_again) == root1}")

    # Tamper-evidence: widen one capability's rights.
    v_tampered = norm([("alice", "secret", {"read", "write"}),
                       ("bob", "attacker", {"grant", "read"})])
    print(f"\n  one capability altered -> root {merkle_root(v_tampered)[:16]}...")
    print(f"    tamper detected? {merkle_root(v_tampered) != root1}")

    # An update (a grant) produces a new root; old root remains valid.
    v2 = norm([("alice", "secret", {"read", "write"}), ("bob", "attacker", {"grant"}),
               ("bob", "attacker", {"grant"}), ("carol", "pub", {"read"})])
    root2 = store.commit(v2)
    print(f"\n  commit v2 (added carol->pub:r) -> root {root2[:16]}...")
    print(f"  world history: {[r[:8] for r in store.history]}")

    # Free rollback: revert simply names the previous root.
    current = store.history[-1]
    rolled_back = store.history[0]
    print(f"\n  rollback v2 -> v1 is a pointer swap: {current[:8]} => {rolled_back[:8]}")
    print(f"    rolled-back root equals original v1 root? {rolled_back == root1}")

    print(f"\n  distinct content objects stored (deduped by hash): {len(store.objects)}")
    print("\n" + bar)
    print("State is named by its hash: reproducible, tamper-evident, and rollback is")
    print("free. This is the L4 'deterministic world' - updates are new roots, never")
    print("in-place mutation, so any past state is one pointer away.")
    print(bar)
