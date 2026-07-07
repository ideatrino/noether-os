"""
NOETHER - exhaustive explicit-state model checker.  [Shot 5, runnable substance]

This does what TLC does: from an initial configuration it explores EVERY
reachable state (breadth-first over the finite state space of a small instance)
and checks a safety invariant on each - exhaustive, not sampled. On an unsafe
configuration it reconstructs a counterexample trace, exactly like a model
checker. This is the jump from "we sampled thousands of traces" (property tests)
to "we proved it for this finite instance by exhausting the state space".

The full symbolic version lives in NOETHER.tla (run it with TLC in your own
environment; TLC could not be fetched in this sandbox - the release CDN is
outside the network allowlist).

Run:  python3 noether_modelcheck.py
"""

from __future__ import annotations
from collections import deque
from typing import FrozenSet, Tuple, Dict, Optional, List

# A capability at the authority level: (holder, target, rights)
Cap = Tuple[str, str, FrozenSet[str]]
StateT = FrozenSet[Cap]

SUBJECTS = ["nucleus", "alice", "bob", "attacker"]
OBJECTS = ["secret", "pub"]
RIGHTS = ["read", "write", "grant"]
TARGETS = OBJECTS + SUBJECTS
NONEMPTY_RIGHTSETS = [frozenset(rs) for n in range(1, 4)
                      for rs in __import__("itertools").combinations(RIGHTS, n)]


def successors(state: StateT) -> List[Tuple[str, StateT]]:
    """All states reachable in one Grant step, with a human-readable label."""
    out = []
    for (g, r_edge, redge_rights) in state:
        if r_edge in SUBJECTS and "grant" in redge_rights:      # grant edge g -> r_edge
            for (h2, t, t_rights) in state:
                if h2 == g:                                     # g holds a cap on t
                    for Rd in NONEMPTY_RIGHTSETS:
                        if Rd <= t_rights:                      # no amplification
                            newcap = (r_edge, t, Rd)
                            if newcap not in state:
                                lbl = f"{g} grants {t}:{''.join(sorted(x[0] for x in Rd))} to {r_edge}"
                                out.append((lbl, state | {newcap}))
    return out


def confinement(state: StateT) -> bool:
    """Attacker holds no authority over 'secret'."""
    return not any(h == "attacker" and t == "secret" for (h, t, _) in state)


def model_check(init: StateT, inv, name: str) -> None:
    seen: Dict[StateT, Optional[Tuple[str, StateT]]] = {init: None}
    frontier = deque([init])
    explored = 0
    bad = None
    while frontier:
        s = frontier.popleft(); explored += 1
        if not inv(s):
            bad = s; break
        for lbl, ns in successors(s):
            if ns not in seen:
                seen[ns] = (lbl, s)
                frontier.append(ns)
    print(f"  [{name}]")
    print(f"    reachable states explored : {len(seen)}")
    if bad is None:
        print(f"    invariant (confinement)   : HELD on all {len(seen)} reachable states")
        print(f"    RESULT: VERIFIED (exhaustive for this finite instance)")
    else:
        # reconstruct counterexample trace
        trace = []
        cur = bad
        while seen[cur] is not None:
            lbl, prev = seen[cur]; trace.append(lbl); cur = prev
        print(f"    invariant (confinement)   : VIOLATED")
        print(f"    counterexample ({len(trace)} steps):")
        for i, step in enumerate(reversed(trace), 1):
            print(f"        {i}. {step}")
        print(f"    RESULT: COUNTEREXAMPLE FOUND")


if __name__ == "__main__":
    bar = "=" * 74
    print(bar); print("SHOT 5  -  Exhaustive explicit-state model checking"); print(bar)

    rw = frozenset({"read", "write"})
    grant = frozenset({"grant"})

    # Safe boot (matches NOETHER.tla): no path from attacker to secret.
    safe: StateT = frozenset({
        ("alice", "secret", rw),        # alice holds secret ...
        ("bob", "attacker", grant),     # ... bob can grant to attacker, but holds no secret
    })
    print("\n  Config A - safe boot (alice holds secret; no grant path to attacker):")
    model_check(safe, confinement, "safe")

    # Unsafe boot: alice ALSO has a grant edge to attacker. Now a path exists.
    unsafe: StateT = safe | {("alice", "attacker", grant)}
    print("\n  Config B - unsafe boot (alice additionally has a grant edge to attacker):")
    model_check(unsafe, confinement, "unsafe")

    print("\n" + bar)
    print("Exhaustive over the finite instance: Config A is VERIFIED (every reachable")
    print("state checked); Config B yields a concrete counterexample trace - which is")
    print("exactly the confinement guarantee TLC checks symbolically in NOETHER.tla.")
    print(bar)
