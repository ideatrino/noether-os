# NOETHER

**A capability-security operating-system design — carried from mathematics to a running, kernel-enforced demo on seL4.**

NOETHER is an educational and research project that explores one question: *what
would an operating system look like if its security properties were theorems
rather than features?* It spans a written design, a machine-checkable model, and
a working prototype on the formally verified [seL4](https://sel4.systems)
microkernel — where the kernel is shown physically faulting a confinement
violation.

---

## What this is

- A **design** for a maximally-secure OS built on object capabilities, least
  authority, information-flow control, and a small trusted base.
- A **runnable model** (dependency-free Python) that implements the capability
  system, its safety invariants, take-grant confinement analysis, decentralized
  information flow, exhaustive model checking, and a content-addressed state store.
- A **formal spec** in TLA+ plus an exhaustive explicit-state checker.
- A **working seL4/Microkit prototype** (`seL4-demo/`) that builds and boots real
  confined components, including a confused-deputy scenario where an isolated
  component's attempt to touch protected memory is **trapped by the kernel**.

## What this is **not**

This is an honest scope statement, and it matters:

- **Not a finished or production operating system.** You cannot install it as your
  computer's OS. The seL4 demo runs in an emulator.
- **Not fully formally verified.** It builds *on* seL4's proofs, but the new
  layers here are modeled and tested, not mechanically proven end-to-end.
- **Not a security product.** It's a learning artifact and a serious demonstration
  of ideas — take it as such.

The value here is the *ideas made concrete and honest*, all the way from a proof
sketch to a kernel-enforced memory fault.

---

## The arc it demonstrates

1. **Design** — a layered architecture that keeps the trusted base tiny and pushes
   functionality outward into confined, mutually-distrusting components.
2. **Proof** — the security properties expressed as an inductive invariant, worked
   through on paper for a representative operation.
3. **Model** — that machine executed: guarded transitions that refuse illegal
   operations, thousands of randomized checks, and exhaustive model checking.
4. **Prototype** — the same principles on real seL4: confined protection domains
   talking only over declared channels, with a protected `billing` region that a
   client reaches *only through* a mediating server — and an attacker that the
   kernel faults the instant it reaches for that memory directly.

---

## Repository contents

- `START-HERE.md` — the friendly, plain-language introduction. **Begin here.**
- `NOETHER-OS-design.md` — the full architecture and rationale.
- `NOETHER-formal-companion.md` — the mathematics and proof sketches.
- `IMPLEMENTATION-GUIDE.md` — how to build the design on seL4/Microkit.
- `WINDOWS-SETUP.md` — step-by-step setup for Windows 11 (Python + WSL2).
- Model (`.py`) — `noether_kernel.py`, `noether_demos.py`, `noether_dlm.py`,
  `noether_store.py`, `noether_modelcheck.py`.
- Formal spec — `NOETHER.tla`, `NOETHER.cfg`.
- `seL4-demo/` — the working confined-deputy prototype for seL4/Microkit
  (derived from the seL4 `passive_server` example; see Credits & license).

## Quick start (no seL4 needed)

The model runs anywhere Python does — no dependencies:

```
python noether_demos.py        # guided tour: confined driver, confused deputy, safety checks
python noether_dlm.py          # decentralized information-flow labels + declassification
python noether_store.py        # content-addressed state: reproducible, tamper-evident, rollback
python noether_modelcheck.py   # exhaustive model checking with a counterexample
```

To build and boot the real seL4 prototype, follow `WINDOWS-SETUP.md` (Path B) and
`IMPLEMENTATION-GUIDE.md`.

---

## Honest limitations

What would take this from prototype to a genuinely production, fully-verified
system is a multi-year, specialist effort: a mechanized refinement proof of the
new layers in a proof assistant, verified compilation to machine code, hardware
memory-capability enforcement (CHERI), and a compatibility layer for existing
software. And even then, one gap never closes: a proof shows code matches its
*specification*, never that the specification is what was intended. These are
stated plainly on purpose — the honesty is part of the point.

## Credits & license

Built on the ideas and tooling of the **seL4** verified microkernel and its
**Microkit** SDK. The `seL4-demo/` prototype is derived from seL4's
`passive_server` example, originally (c) UNSW / Breakaway Consulting under the
**BSD-2-Clause** license; those files retain their original copyright and license.

All original work in this repository is released under the license in `LICENSE`.

*This is an independent educational/research project and is not affiliated with or
endorsed by the seL4 Foundation, or any other organization.*
