"""
NOETHER - executable reference model of the verified nucleus.  [Shot 2]

Adds over Shot 1:
  * Capability INSTANCES with identity (cid) and a DERIVATION GRAPH (parent link).
  * TRANSITIVE revocation: revoking a capability kills everything derived from it.
  * I_prov promoted from "true by construction" to a REAL, CHECKED invariant:
    every non-root capability descends from an existing capability with a
    superset of its rights over the same target; roots are nucleus-minted or boot.

The machine is  sigma = (O, tau, holds, L, clr)  with the transition relation
( -> ). Each syscall is a guarded transition; guard failure raises Refused;
every successful transition re-establishes I = I_wf & I_ifc & I_prov.

This is the abstract machine the proof reasons about, made runnable - NOT the
machine-checked proof nor compiled kernel code (see README.md).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet, Set, List, Iterable, Optional


# --------------------------------------------------------------------------
# 1. Rights, object types, legal-rights map
# --------------------------------------------------------------------------

class Right(Enum):
    READ = "read"; WRITE = "write"; GRANT = "grant"; TAKE = "take"; SEND = "send"; RECV = "recv"


class OType(Enum):
    THREAD = "thread"; NUCLEUS = "nucleus"; ENDPOINT = "endpoint"
    MEMORY = "memory"; DEVICE = "device"


SUBJECT_TYPES = frozenset({OType.THREAD, OType.NUCLEUS})

RIGHTS_FOR: Dict[OType, FrozenSet[Right]] = {
    OType.THREAD:   frozenset({Right.GRANT, Right.TAKE}),  # grant/take edges subject->subject
    OType.NUCLEUS:  frozenset(),
    OType.ENDPOINT: frozenset({Right.SEND, Right.RECV}),
    OType.MEMORY:   frozenset({Right.READ, Right.WRITE}),
    OType.DEVICE:   frozenset({Right.READ, Right.WRITE}),
}

Label = FrozenSet[str]   # secrecy label; lattice ( P(tags), subset ); flow a->b iff L(a)<=L(b)


# --------------------------------------------------------------------------
# 2. Capability spec (input) and held capability instance (in state)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Cap:
    """A capability SPEC: what to grant. Used as input to mint/grant/spawn."""
    target: str
    rights: FrozenSet[Right]
    def __repr__(self) -> str:
        return f"cap({self.target}:{''.join(sorted(r.value[0] for r in self.rights))})"


@dataclass(frozen=True)
class HeldCap:
    """A capability INSTANCE actually held in the state, with provenance."""
    cid: str
    holder: str
    target: str
    rights: FrozenSet[Right]
    parent: Optional[str]     # cid it was derived from; None = root
    origin: str               # "mint" | "grant" | "spawn" | "boot"
    def spec(self) -> Cap:
        return Cap(self.target, self.rights)
    def __repr__(self) -> str:
        rs = ''.join(sorted(r.value[0] for r in self.rights))
        return f"{self.cid}[{self.target}:{rs}]"


@dataclass
class State:
    objects: Dict[str, OType]
    holds: Dict[str, HeldCap] = field(default_factory=dict)
    label: Dict[str, Label] = field(default_factory=dict)
    clr: Dict[str, Label] = field(default_factory=dict)
    next_cid: int = 0
    def copy(self) -> "State":
        return State(dict(self.objects), dict(self.holds), dict(self.label),
                     dict(self.clr), self.next_cid)


class Refused(Exception):
    pass


# --------------------------------------------------------------------------
# 3. Accessors
# --------------------------------------------------------------------------

def subjects(s: State) -> Set[str]:
    return {o for o, t in s.objects.items() if t in SUBJECT_TYPES}

def lbl(s: State, o: str) -> Label: return s.label.get(o, frozenset())
def clr(s: State, o: str) -> Label: return s.clr.get(o, frozenset())

def held_by(s: State, holder: str) -> List[HeldCap]:
    return [hc for hc in s.holds.values() if hc.holder == holder]

def caps_of(s: State, holder: str) -> Set[Cap]:
    return {hc.spec() for hc in s.holds.values() if hc.holder == holder}

def rights_of(s: State, holder: str, target: str) -> FrozenSet[Right]:
    r: Set[Right] = set()
    for hc in s.holds.values():
        if hc.holder == holder and hc.target == target:
            r |= hc.rights
    return frozenset(r)

def holds_right(s: State, holder: str, target: str, right: Right) -> bool:
    return right in rights_of(s, holder, target)

def cap_id(s: State, holder: str, target: str) -> Optional[str]:
    for hc in s.holds.values():
        if hc.holder == holder and hc.target == target:
            return hc.cid
    return None

def _find_parent(s: State, g: str, target: str, rights_needed: FrozenSet[Right]) -> Optional[str]:
    """A capability instance held by g over target whose rights cover rights_needed."""
    for hc in s.holds.values():
        if hc.holder == g and hc.target == target and rights_needed <= hc.rights:
            return hc.cid
    return None

def _add_cap(ns: State, holder: str, target: str, rights: FrozenSet[Right],
             parent: Optional[str], origin: str) -> str:
    cid = f"c{ns.next_cid}"; ns.next_cid += 1
    ns.holds = {**ns.holds, cid: HeldCap(cid, holder, target, frozenset(rights), parent, origin)}
    return cid

def descendants(s: State, cid: str) -> Set[str]:
    """cid and everything transitively derived from it (the revocation subtree)."""
    out = {cid}; frontier = [cid]
    while frontier:
        x = frontier.pop()
        for hc in s.holds.values():
            if hc.parent == x and hc.cid not in out:
                out.add(hc.cid); frontier.append(hc.cid)
    return out


# --------------------------------------------------------------------------
# 4. The invariant bundle I  (wf & ifc & prov)
# --------------------------------------------------------------------------

def check_wf(s: State) -> List[str]:
    v: List[str] = []
    for hc in s.holds.values():
        if hc.holder not in s.objects or s.objects.get(hc.holder) not in SUBJECT_TYPES:
            v.append(f"{hc.holder!r} is not a live subject but holds {hc}")
        if hc.target not in s.objects:
            v.append(f"{hc} is dangling (target missing)")
        elif not hc.rights <= RIGHTS_FOR[s.objects[hc.target]]:
            v.append(f"{hc} has illegal rights for {s.objects[hc.target].value}")
    return v

def check_ifc(s: State) -> List[str]:
    v: List[str] = []
    for hc in s.holds.values():
        tt = s.objects.get(hc.target)
        if tt in (OType.MEMORY, OType.DEVICE):
            if Right.READ in hc.rights and not (lbl(s, hc.target) <= clr(s, hc.holder)):
                v.append(f"read-up: {hc.holder} reads {hc.target}")
            if Right.WRITE in hc.rights and not (clr(s, hc.holder) <= lbl(s, hc.target)):
                v.append(f"write-down: {hc.holder} writes {hc.target}")
        elif tt == OType.ENDPOINT:
            if Right.RECV in hc.rights and not (lbl(s, hc.target) <= clr(s, hc.holder)):
                v.append(f"read-up (recv): {hc.holder} on {hc.target}")
            if Right.SEND in hc.rights and not (clr(s, hc.holder) <= lbl(s, hc.target)):
                v.append(f"write-down (send): {hc.holder} on {hc.target}")
    return v

def check_prov(s: State) -> List[str]:
    """I_prov: derivation-chain soundness. Every capability either is a legitimate
    root (nucleus-minted or boot) or descends from an EXISTING capability with a
    superset of its rights over the same target. This is exactly what DIRECT
    revocation breaks (it orphans descendants) and TRANSITIVE revocation preserves."""
    v: List[str] = []
    for hc in s.holds.values():
        if hc.parent is None:
            if hc.origin not in ("mint", "boot"):
                v.append(f"{hc} is a root with illegitimate origin {hc.origin!r}")
        else:
            p = s.holds.get(hc.parent)
            if p is None:
                v.append(f"{hc} is ORPHANED (parent {hc.parent} was revoked non-transitively)")
            elif p.target != hc.target or not hc.rights <= p.rights:
                v.append(f"{hc} amplifies or diverges from its parent {p}")
    return v

def check_I(s: State) -> List[str]:
    return check_wf(s) + check_ifc(s) + check_prov(s)

def assert_I(s: State, where: str) -> State:
    v = check_I(s)
    if v:
        raise AssertionError(f"INVARIANT VIOLATED after {where}: {v}")
    return s


# --------------------------------------------------------------------------
# 5. Take-grant confinement (decidable can-share)
# --------------------------------------------------------------------------

def tg_closure(s: State) -> Dict[str, Set[Cap]]:
    """Sound over-approximation of the authority each subject could EVER hold,
    via grant edges, take edges, AND endpoint-mediated capability transfer.
    (Endpoints are authority channels in an ocap system, so confinement analysis
    must model them or it would be unsound against send_cap.)"""
    potential: Dict[str, Set[Cap]] = {a: caps_of(s, a) for a in subjects(s)}
    endpoints = [o for o, t in s.objects.items() if t == OType.ENDPOINT]

    def merge(dst: str, src: str) -> bool:
        before = len(potential.setdefault(dst, set()))
        potential[dst] |= potential.get(src, set())
        return len(potential[dst]) != before

    changed = True
    while changed:
        changed = False
        for x in list(potential.keys()):
            for c in list(potential[x]):
                if s.objects.get(c.target) in SUBJECT_TYPES:
                    if Right.GRANT in c.rights and merge(c.target, x):  # x pushes to c.target
                        changed = True
                    if Right.TAKE in c.rights and merge(x, c.target):   # x pulls from c.target
                        changed = True
        for e in endpoints:  # any SEND holder may pass caps to any RECV holder on e
            senders = [a for a in potential if any(c.target == e and Right.SEND in c.rights for c in potential[a])]
            receivers = [a for a in potential if any(c.target == e and Right.RECV in c.rights for c in potential[a])]
            for snd in senders:
                for rcv in receivers:
                    if merge(rcv, snd):
                        changed = True
    return potential

def can_share(s: State, a: str, x: str, right: Right) -> bool:
    return any(c.target == x and right in c.rights for c in tg_closure(s).get(a, set()))


# --------------------------------------------------------------------------
# 6. Guarded transitions
# --------------------------------------------------------------------------

def mint(s: State, by: str, holder: str, target: str, rights: FrozenSet[Right]) -> State:
    if s.objects.get(by) != OType.NUCLEUS:
        raise Refused(f"mint: {by} is not the nucleus")
    if holder not in subjects(s):
        raise Refused(f"mint: {holder} is not a subject")
    if target not in s.objects:
        raise Refused(f"mint: target {target} missing")
    if not rights <= RIGHTS_FOR[s.objects[target]]:
        raise Refused(f"mint: rights illegal for {s.objects[target].value}")
    if Right.READ in rights and not (lbl(s, target) <= clr(s, holder)):
        raise Refused("mint: read-up")
    if Right.WRITE in rights and not (clr(s, holder) <= lbl(s, target)):
        raise Refused("mint: write-down")
    ns = s.copy(); _add_cap(ns, holder, target, frozenset(rights), None, "mint")
    return assert_I(ns, f"mint({holder}<-{target})")


def grant(s: State, g: str, r: str, target: str, rights_d: FrozenSet[Right]) -> State:
    if not (r in subjects(s) and holds_right(s, g, r, Right.GRANT)):
        raise Refused(f"grant: {g} has no grant edge to {r}")
    parent = _find_parent(s, g, target, frozenset(rights_d))
    if parent is None:
        raise Refused(f"grant: {g} cannot grant {set(rights_d)} over {target} it does not hold (no amplification)")
    if not rights_d <= RIGHTS_FOR[s.objects[target]]:
        raise Refused(f"grant: rights illegal for {s.objects[target].value}")
    if Right.READ in rights_d and not (lbl(s, target) <= clr(s, r)):
        raise Refused(f"grant: {r} read-up on {target}")
    if Right.WRITE in rights_d and not (clr(s, r) <= lbl(s, target)):
        raise Refused(f"grant: {r} write-down on {target}")
    ns = s.copy(); _add_cap(ns, r, target, frozenset(rights_d), parent, "grant")
    return assert_I(ns, f"grant({g}->{r}:{target})")


def take(s: State, r: str, g: str, target: str, rights_t: FrozenSet[Right]) -> State:
    """r pulls a capability over `target` from g, via a take edge r -> g."""
    if not (g in subjects(s) and holds_right(s, r, g, Right.TAKE)):
        raise Refused(f"take: {r} has no take edge to {g}")
    parent = _find_parent(s, g, target, frozenset(rights_t))
    if parent is None:
        raise Refused(f"take: {g} does not hold {set(rights_t)} over {target}")
    if not rights_t <= RIGHTS_FOR[s.objects[target]]:
        raise Refused("take: illegal rights")
    if Right.READ in rights_t and not (lbl(s, target) <= clr(s, r)):
        raise Refused(f"take: {r} read-up on {target}")
    if Right.WRITE in rights_t and not (clr(s, r) <= lbl(s, target)):
        raise Refused(f"take: {r} write-down on {target}")
    ns = s.copy(); _add_cap(ns, r, target, frozenset(rights_t), parent, "take")
    return assert_I(ns, f"take({r}<-{g}:{target})")


def send_cap(s: State, sender: str, e: str, receiver: str,
             target: str, rights_c: FrozenSet[Right]) -> State:
    """Capability-passing over IPC: sender transfers a cap it holds over `target`
    through endpoint e to a receiver holding RECV on e. This is how authority
    moves between mutually-distrusting services."""
    if not holds_right(s, sender, e, Right.SEND):
        raise Refused(f"send: {sender} lacks SEND on {e}")
    if not holds_right(s, receiver, e, Right.RECV):
        raise Refused(f"send: {receiver} lacks RECV on {e}")
    parent = _find_parent(s, sender, target, frozenset(rights_c))
    if parent is None:
        raise Refused(f"send: {sender} does not hold {set(rights_c)} over {target}")
    if not rights_c <= RIGHTS_FOR[s.objects[target]]:
        raise Refused("send: illegal rights")
    if Right.READ in rights_c and not (lbl(s, target) <= clr(s, receiver)):
        raise Refused(f"send: {receiver} read-up on {target}")
    if Right.WRITE in rights_c and not (clr(s, receiver) <= lbl(s, target)):
        raise Refused(f"send: {receiver} write-down on {target}")
    ns = s.copy(); _add_cap(ns, receiver, target, frozenset(rights_c), parent, "send")
    return assert_I(ns, f"send_cap({sender}->{receiver}:{target})")


def spawn(s: State, parent: str, child: str, ctype: OType,
          child_clr: Label, init_caps: Iterable[Cap], manageable: bool = False) -> State:
    """Least authority by construction; SEALED by default (no parent grant edge)."""
    if parent not in subjects(s):
        raise Refused("spawn: parent is not a subject")
    if child in s.objects:
        raise Refused(f"spawn: {child} exists")
    links = []
    for c in init_caps:
        pcid = _find_parent(s, parent, c.target, c.rights)
        if pcid is None:
            raise Refused(f"spawn: parent cannot pass {c} it does not hold")
        if Right.READ in c.rights and not (lbl(s, c.target) <= child_clr):
            raise Refused("spawn: child read-up")
        if Right.WRITE in c.rights and not (child_clr <= lbl(s, c.target)):
            raise Refused("spawn: child write-down")
        links.append((c, pcid))
    ns = s.copy(); ns.objects[child] = ctype; ns.clr[child] = child_clr
    for c, pcid in links:
        _add_cap(ns, child, c.target, c.rights, pcid, "spawn")
    if manageable:
        _add_cap(ns, parent, child, frozenset({Right.GRANT}), None, "mint")
    return assert_I(ns, f"spawn({child})")


def revoke_direct(s: State, g: str, r: str, target: str) -> State:
    """UNSOUND on purpose (for contrast): removes r's caps to target WITHOUT
    removing descendants, orphaning them and breaking I_prov. Do not assert I."""
    if not (r in subjects(s) and holds_right(s, g, r, Right.GRANT)):
        raise Refused(f"revoke_direct: {g} does not manage {r}")
    ns = s.copy()
    ns.holds = {k: v for k, v in s.holds.items() if not (v.holder == r and v.target == target)}
    return ns  # deliberately not assert_I'd


def revoke_transitive(s: State, g: str, cid: str) -> State:
    """Revoke a capability AND its whole derivation subtree. Preserves I_prov."""
    if cid not in s.holds:
        raise Refused("revoke: no such capability")
    hc = s.holds[cid]
    authorized = (s.objects.get(g) == OType.NUCLEUS) or \
                 (hc.parent is not None and s.holds.get(hc.parent) and s.holds[hc.parent].holder == g)
    if not authorized:
        raise Refused(f"revoke: {g} did not grant {cid}, cannot revoke it")
    dead = descendants(s, cid)
    ns = s.copy()
    ns.holds = {k: v for k, v in s.holds.items() if k not in dead}
    return assert_I(ns, f"revoke_transitive({cid})")


# --------------------------------------------------------------------------
# 7. Pretty printing
# --------------------------------------------------------------------------

def show_state(s: State, title: str = "state") -> None:
    print(f"  [{title}] " + ", ".join(f"{o}:{t.value}" for o, t in s.objects.items()))
    for h in sorted(subjects(s)):
        cs = sorted(held_by(s, h), key=lambda c: c.target)
        if cs:
            print(f"    {h:<11} " + "  ".join(map(repr, cs)))

def show_deriv(s: State) -> None:
    for hc in sorted(s.holds.values(), key=lambda c: c.cid):
        arrow = f" <- {hc.parent}" if hc.parent else f" (root/{hc.origin})"
        print(f"    {hc.holder:<11} {hc}{arrow}")
