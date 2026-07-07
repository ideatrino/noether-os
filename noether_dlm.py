"""
NOETHER - decentralized information flow (DLM).  [Shot 4]

The fixed tag-set lattice used in shots 1-3 is a single, central classification.
This module implements the Decentralized Label Model (Myers & Liskov): each
principal owns its OWN read policy, and may DECLASSIFY its own data - no central
authority decides secrecy. It is a drop-in replacement for the kernel's `<=`
(flows_to) and read check (can_read) in check_ifc.

A label is a set of policies, each (owner, readers). A principal p may read data
with label L iff, for EVERY policy, p is the owner or an allowed reader:
    can_read(p, L)  ==  for all (o, R) in L:  p == o  or  p in R
Information may flow from L1 to L2 iff L2 is at least as restrictive - every
principal that can read L2 can already read L1:
    flows_to(L1, L2)  ==  readers(L2) subset-of readers(L1)
Combining data joins labels (union of policies = more restrictive). An owner may
unilaterally relax ONLY its own policy (declassification).

Run:  python3 noether_dlm.py
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import FrozenSet, Set, Tuple
import random

Principal = str


@dataclass(frozen=True)
class Policy:
    owner: Principal
    readers: FrozenSet[Principal]      # the owner is always implicitly a reader


Label = FrozenSet[Policy]              # empty label == public

PUBLIC: Label = frozenset()


def can_read(p: Principal, L: Label) -> bool:
    return all(p == pol.owner or p in pol.readers for pol in L)

def readers(L: Label, universe: FrozenSet[Principal]) -> FrozenSet[Principal]:
    return frozenset(p for p in universe if can_read(p, L))

def flows_to(L1: Label, L2: Label, universe: FrozenSet[Principal]) -> bool:
    """Safe to move L1-data into an L2-container iff L2 does not widen the audience."""
    return readers(L2, universe) <= readers(L1, universe)

def join(L1: Label, L2: Label) -> Label:
    """Label of data derived from both: the union of policies (most restrictive)."""
    return L1 | L2

def declassify(L: Label, actor: Principal, owner: Principal,
               new_readers: FrozenSet[Principal]) -> Label:
    """`actor`, acting for `owner`, relaxes owner's OWN policy. Decentralized:
    an actor can only touch policies it owns; it cannot weaken anyone else's."""
    if actor != owner:
        raise PermissionError(f"{actor} may not declassify {owner}'s policy")
    kept = frozenset(pol for pol in L if pol.owner != owner)
    return kept | {Policy(owner, new_readers)}


# --------------------------------------------------------------------------
# Demo
# --------------------------------------------------------------------------

def demo() -> None:
    bar = "=" * 74
    print(bar); print("SHOT 4  -  Decentralized information flow (DLM) + declassification"); print(bar)
    universe = frozenset({"alice", "bob", "carol", "eve"})

    # 'doc' is co-owned: alice restricts to {alice,bob}; bob allows {alice,bob,carol}.
    doc: Label = frozenset({
        Policy("alice", frozenset({"alice", "bob"})),
        Policy("bob",   frozenset({"alice", "bob", "carol"})),
    })
    print("  doc policies: alice->{alice,bob}, bob->{alice,bob,carol}")
    print(f"  effective readers of doc: {set(readers(doc, universe))}")
    for p in ("alice", "bob", "carol", "eve"):
        print(f"    can_read({p:<5}, doc) = {can_read(p, doc)}")

    print("\n  A read capability on doc is grantable only to an effective reader.")
    print(f"    carol may hold READ on doc? {can_read('carol', doc)}   (blocked by alice's policy)")
    print(f"    flows_to(doc, PUBLIC) = {flows_to(doc, PUBLIC, universe)}   (no silent leak)")

    print("\n  alice DECLASSIFIES her own policy to admit carol (bob's policy untouched):")
    doc2 = declassify(doc, actor="alice", owner="alice",
                      new_readers=frozenset({"alice", "bob", "carol"}))
    print(f"    effective readers now: {set(readers(doc2, universe))}")
    print(f"    can_read(carol, doc2) = {can_read('carol', doc2)}")
    print(f"    can_read(eve,   doc2) = {can_read('eve', doc2)}   (no owner ever admitted eve)")

    print("\n  eve tries to declassify alice's policy:")
    try:
        declassify(doc, actor="eve", owner="alice", new_readers=universe)
    except PermissionError as e:
        print(f"    REFUSED: {e}")


# --------------------------------------------------------------------------
# Property check: flows_to is a sound preorder and join is an upper bound
# --------------------------------------------------------------------------

def rand_label(rng: random.Random, universe) -> Label:
    owners = rng.sample(sorted(universe), rng.randint(0, 3))
    pols = set()
    for o in owners:
        rs = frozenset(p for p in universe if rng.random() < 0.5)
        pols.add(Policy(o, rs))
    return frozenset(pols)


def property_check(trials: int = 4000) -> None:
    print("\n" + "=" * 74)
    print("Property check: flows_to a preorder; join a least upper bound")
    print("=" * 74)
    universe = frozenset({"a", "b", "c", "d"})
    rng = random.Random(7)
    refl = trans = ub = mono = 0
    for _ in range(trials):
        L1, L2, L3 = (rand_label(rng, universe) for _ in range(3))
        refl += flows_to(L1, L1, universe)                                   # reflexive
        if flows_to(L1, L2, universe) and flows_to(L2, L3, universe):        # transitive
            trans += flows_to(L1, L3, universe)
        else:
            trans += 1
        J = join(L1, L2)
        ub += (flows_to(L1, J, universe) and flows_to(L2, J, universe))      # join is upper bound
        if flows_to(L1, L3, universe) and flows_to(L2, L3, universe):        # ... and least
            mono += flows_to(J, L3, universe)
        else:
            mono += 1
    print(f"  reflexivity     : {refl}/{trials}")
    print(f"  transitivity    : {trans}/{trials}")
    print(f"  join upper bound: {ub}/{trials}")
    print(f"  join is least   : {mono}/{trials}")
    ok = refl == trans == ub == mono == trials
    print(f"\n  RESULT: {'PASS - the decentralized labels form a sound information-flow order' if ok else 'FAIL'}")


if __name__ == "__main__":
    demo()
    property_check()
