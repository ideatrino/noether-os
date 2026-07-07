"""
NOETHER - scenarios + property-based verification harness.  [Shot 2]

Run:   python3 noether_demos.py

Scenarios:
  1. Confused deputy - defeated by construction (ACL baseline for contrast).
  2. Compromised driver - provably confined; honest boundary named.
  3. Transitive revocation & provenance - shows DIRECT revocation breaking
     I_prov (orphans) and TRANSITIVE revocation preserving it. [NEW this shot]
  4. Property-based verification - I = wf & ifc & prov held across thousands of
     random legal transition sequences; can_share confinement predictions sound.
"""

from __future__ import annotations
import random
from typing import List, Tuple

from noether_kernel import (
    Right, OType, Cap, State, Refused,
    mint, grant, spawn, revoke_direct, revoke_transitive, take, send_cap,
    check_I, check_prov, can_share, subjects, rights_of, cap_id,
    show_state, show_deriv,
)

R, W, G = Right.READ, Right.WRITE, Right.GRANT
BAR = "=" * 74


# ------------------------------- Scenario 1 -------------------------------

def scenario_confused_deputy() -> None:
    print(BAR); print("SCENARIO 1  -  The confused deputy"); print(BAR)
    objects = {"nucleus": OType.NUCLEUS, "attacker": OType.THREAD,
               "compiler": OType.THREAD, "billing": OType.MEMORY, "source": OType.MEMORY}
    label = {"billing": frozenset({"finance"}), "source": frozenset()}
    clr = {"nucleus": frozenset({"finance"}), "compiler": frozenset({"finance"}),
           "attacker": frozenset()}
    s = State(objects, {}, label, clr)
    s = mint(s, "nucleus", "compiler", "billing", frozenset({W}))
    s = mint(s, "nucleus", "attacker", "source", frozenset({R}))
    s = mint(s, "nucleus", "attacker", "compiler", frozenset({G}))
    show_state(s, "boot")

    print("\n  Attacker tries to hand the compiler a write-cap to billing:")
    try:
        grant(s, "attacker", "compiler", "billing", frozenset({W}))
        print("    !! attack succeeded (should NOT happen)")
    except Refused as e:
        print(f"    REFUSED: {e}")
    print(f"  can_share(attacker, billing, write) = {can_share(s, 'attacker', 'billing', W)}")
    print("  ACL baseline (ambient authority): deputy would overwrite billing on request.")


# ------------------------------- Scenario 2 -------------------------------

def scenario_malicious_driver() -> None:
    print("\n" + BAR); print("SCENARIO 2  -  A fully compromised device driver"); print(BAR)
    objects = {"nucleus": OType.NUCLEUS, "init": OType.THREAD, "usb_dev": OType.DEVICE,
               "filesystem": OType.MEMORY, "secrets": OType.MEMORY}
    label = {"usb_dev": frozenset(), "filesystem": frozenset(), "secrets": frozenset({"secret"})}
    clr = {"nucleus": frozenset({"secret"}), "init": frozenset()}
    s = State(objects, {}, label, clr)
    s = mint(s, "nucleus", "init", "usb_dev", frozenset({R, W}))
    s = mint(s, "nucleus", "init", "filesystem", frozenset({R, W}))
    s = spawn(s, "init", "usb_driver", OType.THREAD,
              child_clr=frozenset(), init_caps=[Cap("usb_dev", frozenset({R, W}))])
    show_state(s, "sealed driver")
    print("\n  Assume the driver is fully compromised. Reachability:")
    for tgt, right in [("filesystem", R), ("secrets", R), ("usb_dev", W)]:
        ans = can_share(s, "usb_driver", tgt, right)
        print(f"    can_share(usb_driver, {tgt}, {right.value}) = {str(ans):<5}  "
              f"-> {'reachable' if ans else 'PROVABLY UNREACHABLE'}")
    print("  Boundary (outside the model): DMA under a mis-set IOMMU, timing channels, availability.")


# ------------------------------- Scenario 3 (NEW) -------------------------

def scenario_revocation() -> None:
    print("\n" + BAR); print("SCENARIO 3  -  Transitive revocation & provenance"); print(BAR)
    objects = {"nucleus": OType.NUCLEUS, "A": OType.THREAD, "B": OType.THREAD,
               "C": OType.THREAD, "m": OType.MEMORY}
    clr = {x: frozenset() for x in ("nucleus", "A", "B", "C")}
    s = State(objects, {}, {"m": frozenset()}, clr)
    # A holds m (root), and grant edges A->B, B->C exist
    s = mint(s, "nucleus", "A", "m", frozenset({R, W}))
    s = mint(s, "nucleus", "A", "B", frozenset({G}))
    s = mint(s, "nucleus", "B", "C", frozenset({G}))
    # delegation chain: A grants m to B, B grants (read-only) m to C
    s = grant(s, "A", "B", "m", frozenset({R, W}))
    s = grant(s, "B", "C", "m", frozenset({R}))
    print("  Derivation chain (who holds what, derived from which cap):")
    show_deriv(s)
    print(f"\n  I_prov holds initially: {check_prov(s) == []}")

    b_m = cap_id(s, "B", "m")   # the capability B holds on m

    print("\n  (a) DIRECT revoke of B's cap on m (removes B's cap only):")
    s_direct = revoke_direct(s, "A", "B", "m")
    viol = check_prov(s_direct)
    print(f"      C still holds a cap on m? {cap_id(s_direct, 'C', 'm') is not None}")
    print(f"      I_prov now: {'HOLDS' if not viol else 'VIOLATED -> ' + viol[0]}")

    print("\n  (b) TRANSITIVE revoke of the same cap (removes B's cap AND C's derived cap):")
    s_trans = revoke_transitive(s, "A", b_m)
    print(f"      B holds m? {cap_id(s_trans, 'B', 'm') is not None}   "
          f"C holds m? {cap_id(s_trans, 'C', 'm') is not None}")
    print(f"      I_prov now: {'HOLDS' if check_prov(s_trans) == [] else 'VIOLATED'}")
    print("\n  => Direct revocation is unsound (orphans descendants); transitive")
    print("     revocation is what keeps authority provenance consistent.")


# --------------------------- Scenario 3.5 (Shot 3) -----------------------

def scenario_take_and_ipc() -> None:
    print("\n" + BAR); print("SCENARIO 3.5  -  Take edges & IPC capability transfer  [Shot 3]"); print(BAR)
    objects = {"nucleus": OType.NUCLEUS, "producer": OType.THREAD, "consumer": OType.THREAD,
               "boss": OType.THREAD, "worker": OType.THREAD,
               "widget": OType.MEMORY, "report": OType.MEMORY, "chan": OType.ENDPOINT}
    clr = {x: frozenset() for x in ("nucleus", "producer", "consumer", "boss", "worker")}
    label = {o: frozenset() for o in ("widget", "report", "chan")}
    s = State(objects, {}, label, clr)
    s = mint(s, "nucleus", "producer", "widget", frozenset({R, W}))
    s = mint(s, "nucleus", "producer", "chan", frozenset({Right.SEND}))
    s = mint(s, "nucleus", "consumer", "chan", frozenset({Right.RECV}))
    s = mint(s, "nucleus", "worker", "report", frozenset({R, W}))
    s = mint(s, "nucleus", "boss", "worker", frozenset({Right.TAKE}))  # boss has a take edge to worker

    print("  IPC: producer holds SEND, consumer holds RECV on 'chan'.")
    print(f"    can_share(consumer, widget, read) BEFORE transfer = "
          f"{can_share(s, 'consumer', 'widget', R)}  (endpoint is an authority channel)")
    s = send_cap(s, "producer", "chan", "consumer", "widget", frozenset({R}))
    print(f"    after send_cap: consumer holds a cap on widget? {cap_id(s, 'consumer', 'widget') is not None}")

    print("\n  TAKE: boss holds a take edge to worker, who holds 'report'.")
    print(f"    can_share(boss, report, write) = {can_share(s, 'boss', 'report', W)}")
    s = take(s, "boss", "worker", "report", frozenset({R, W}))
    print(f"    after take: boss holds a cap on report? {cap_id(s, 'boss', 'report') is not None}")
    print(f"\n  I still holds across both transfers: {check_I(s) == []}")


# ------------------------------- Scenario 4 ------------------------------

def rich_state(seed: int):
    rng = random.Random(seed)
    subs = ["a", "b", "c", "d"]; objs = ["m1", "m2", "m3"]
    objects = {"nucleus": OType.NUCLEUS}
    for x in subs: objects[x] = OType.THREAD
    for m in objs: objects[m] = OType.MEMORY
    s = State(objects, {}, {m: frozenset() for m in objs}, {x: frozenset() for x in subs + ["nucleus"]})
    for _ in range(10):
        g = rng.choice(subs); r = rng.choice([x for x in subs if x != g])
        s = mint(s, "nucleus", g, r, frozenset({G}))
    for _ in range(8):
        s = mint(s, "nucleus", rng.choice(subs), rng.choice(objs),
                 frozenset(rng.choice([[R], [W], [R, W]])))
    return s, subs, objs

def random_transition(s: State, subs, objs, rng) -> State:
    kind = rng.choice(["grant", "grant", "revoke"])
    if kind == "grant":
        g, r, t = rng.choice(subs), rng.choice(subs), rng.choice(objs)
        return grant(s, g, r, t, frozenset(rng.choice([[R], [W], [R, W]])))
    if s.holds:
        cid = rng.choice(list(s.holds.keys()))
        hc = s.holds[cid]
        g = s.holds[hc.parent].holder if (hc.parent and hc.parent in s.holds) else "nucleus"
        return revoke_transitive(s, g, cid)
    return s

def property_tests(runs: int = 400, steps: int = 40) -> None:
    print("\n" + BAR); print("SCENARIO 4  -  Property-based verification"); print(BAR)
    total = refused = violations = 0
    conf_trials = conf_ok = 0
    for run in range(runs):
        rng = random.Random(2000 + run)
        s0, subs, objs = rich_state(run); s = s0
        claim = None
        for a in subs:
            for x in objs:
                for right in (R, W):
                    if not can_share(s0, a, x, right):
                        claim = (a, x, right); break
                if claim: break
            if claim: break
        for _ in range(steps):
            try:
                s = random_transition(s, subs, objs, rng); total += 1
                if check_I(s): violations += 1
            except Refused:
                refused += 1
            except AssertionError:
                violations += 1
            if claim:
                a, x, right = claim; conf_trials += 1
                if right not in rights_of(s, a, x): conf_ok += 1
    print(f"  legal transitions applied             : {total}")
    print(f"  illegal operations correctly refused  : {refused}")
    print(f"  states where I (wf & ifc & prov) held : {total - violations}/{total}")
    print(f"  invariant violations                  : {violations}")
    print(f"  can_share confinement predictions held: {conf_ok}/{conf_trials}")
    ok = violations == 0 and conf_ok == conf_trials and total > 0
    print(f"\n  RESULT: {'PASS - I (now including provenance) conserved at every sampled state' if ok else 'FAIL'}")


if __name__ == "__main__":
    scenario_confused_deputy()
    scenario_malicious_driver()
    scenario_revocation()
    scenario_take_and_ipc()
    property_tests()
    print("\n" + BAR)
    print("Shot 2 complete. Next reachable shots: full take-grant + endpoint")
    print("cap-passing (3), decentralized IFC (4), a TLC-checkable TLA+ spec (5).")
    print(BAR)
