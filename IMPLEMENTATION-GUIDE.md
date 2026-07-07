# NOETHER — Step-by-Step Implementation Guide

Building the NOETHER design on the **seL4** verified microkernel with **Microkit**
and Rust userspace. This is the concrete "how to actually build it" companion to
the design docs and the runnable model in this repo.

---

## How to use this guide (read first — it's about honesty)

- **Accurate here:** the build *sequence*, how NOETHER maps onto seL4/Microkit
  primitives, and the reference code for NOETHER's *own* components (translated
  from the tested Python model in this repo).
- **Verify upstream:** exact shell commands, SDK versions, and API signatures
  change between releases. The current Microkit SDK is **2.2.0**. Always
  cross-check the linked seL4/Microkit docs for the precise, current incantations
  before pasting anything.
- **Source of truth:** the *semantics* of NOETHER are defined by the tested
  Python model (`noether_kernel.py` etc.). The Rust below is **reference to
  adapt** — it was not compiled in this repo. Treat it as a faithful sketch, not
  a drop-in crate.

Key upstream anchors:
- Microkit tutorial: https://docs.sel4.systems/projects/microkit/tutorial/
- Microkit manual: https://docs.sel4.systems/projects/microkit/manual/latest/
- Microkit repo + SDK releases: https://github.com/seL4/microkit
- Rust on seL4 tutorial: https://docs.sel4.systems/Tutorials/
- The formal proofs (for the verification track): the seL4 `l4v` repository.

---

## The core insight — build on seL4, don't reprove a kernel

The most expensive part of NOETHER (a verified capability microkernel) already
exists, is production-grade, and is proven. So you *assemble* NOETHER's
distinctive layers on top of seL4 rather than reinventing them. This mapping is
the whole plan:

| NOETHER concept (our model) | seL4 / Microkit mechanism |
|---|---|
| subject | protection domain (PD) — its own TCB, VSpace, CSpace |
| `holds` (capability table) | the PD's **CSpace** (real, kernel-enforced caps) |
| derivation graph (`parent`) | seL4's **Capability Derivation Tree (CDT)** |
| `grant` (delegate) | `seL4_CNode_Copy` / `seL4_CNode_Mint` |
| `revoke_transitive` | `seL4_CNode_Revoke` — kernel revokes all derived caps, already proven |
| sealed POLA `spawn` | a static Microkit PD given only the caps you declare |
| objects / memory | Microkit **memory regions** (mapped into a PD's VSpace) |
| IPC endpoints / `send_cap` | Microkit **channels** (protected procedure calls + notifications) |
| `I_ifc` (information flow) | userspace policy layer (+ seL4's kernel info-flow proof for static configs) |
| deterministic world (L4) | userspace content-addressed store |

Read that table twice. `revoke_transitive` — the hard thing we built in Shot 2 —
is `seL4_CNode_Revoke`, and it is *already machine-checked* in seL4. You inherit it.

---

## Phase 0 — Environment and first boot

**Goal:** a working Microkit toolchain that boots a real seL4 system in QEMU.

1. Install host dependencies (a C cross-toolchain for AArch64, `qemu`, `make`,
   and either Nix or Docker). The tutorial's part 0 lists the exact packages per
   OS — follow it, don't guess.
2. Download the Microkit SDK (currently 2.2.0) from the `seL4/microkit` releases
   and extract it. Grab the tutorial code (the "Wordle" system) from the tutorial
   page.
3. Build and run the tutorial system in QEMU.

**Milestone 0:** the tutorial system boots under QEMU and you see its output.
You now have the full seL4 + Microkit loop working. *Do not proceed until this
boots* — everything else builds on it.

> Why Microkit (not CAmkES): CAmkES is being superseded; the seL4 docs recommend
> Microkit for new projects. Microkit targets **static** architectures (resources
> assigned at init), which is a perfect fit for NOETHER's confined-by-
> construction components. Dynamic delegation (our `grant`/`revoke`) uses the raw
> seL4 CNode API from within a PD — covered in Phase 2.

---

## Phase 1 — Model your system as protection domains

**Goal:** express a NOETHER configuration as a Microkit system description.

A Microkit system is declared in an XML "system description" file: you list each
PD, the memory regions, the channels between PDs, and the IRQs. This *is* your
initial state `s₀` and it is where confinement-by-construction lives.

1. For each **subject** in your model, declare a `protection_domain`. By default
   a PD's VSpace contains only its own code — it can touch nothing else. That
   default-deny is POLA for free.
2. For each **object** (a device, a shared buffer, a file backing store), declare
   a `memory_region` and map it *only* into the PDs that should reach it.
3. For each **IPC endpoint**, declare a `channel` between exactly the two PDs
   that share it.
4. For device drivers, attach the device's MMIO region and its `irq` to that one
   driver PD and nowhere else.

**Milestone 1:** your PDs boot, isolated; a PD that tries to touch memory it was
not granted takes a VM fault delivered to the monitor (you'll see the fault
printed). That fault *is* the confinement theorem enforced by hardware+kernel.

Map to our model: this XML is `mint`/`spawn` at boot. The malicious-driver
scenario (Scenario 2) becomes a fact about the XML: the driver PD simply has no
region or channel reaching the filesystem, so it *cannot* — checked by the kernel.

---

## Phase 2 — The capability & provenance runtime (Rust)

**Goal:** the policy layer that adds NOETHER's provenance + dynamic delegation on
top of seL4's caps.

Two layers cooperate:
- **Enforcement (kernel):** seL4's CSpace/CDT already enforce that caps are
  unforgeable, that delegation copies real authority, and that `CNode_Revoke`
  transitively kills derived caps. In production you back `grant` with
  `seL4_CNode_Copy`/`Mint` and `revoke_transitive` with `seL4_CNode_Revoke`.
- **Policy/metadata (your Rust):** seL4 doesn't track *why* a cap exists or its
  information-flow label. This Rust layer mirrors our model to record provenance
  and drive the IFC checks *before* asking the kernel to perform the operation.

Reference (adapt; not compiled here) — the policy cap-table, faithful to
`noether_kernel.py`:

```rust
use std::collections::{BTreeMap, BTreeSet};

pub type Cid = u64;
pub type Id  = String; // a PD name or object name

#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Right { Read, Write, Grant, Take, Send, Recv }

#[derive(Clone, Copy)]
pub enum Origin { Boot, Mint, Grant, Take, Send, Spawn }

#[derive(Clone)]
pub struct HeldCap {
    pub holder: Id,
    pub target: Id,
    pub rights: BTreeSet<Right>,
    pub parent: Option<Cid>,   // derivation edge == seL4's CDT parent
    pub origin: Origin,
}

pub struct Refused(pub &'static str);

#[derive(Default)]
pub struct CapState { pub caps: BTreeMap<Cid, HeldCap>, next: Cid }

impl CapState {
    fn add(&mut self, hc: HeldCap) -> Cid { let c = self.next; self.next += 1; self.caps.insert(c, hc); c }

    fn rights_of(&self, holder: &str, target: &str) -> BTreeSet<Right> {
        self.caps.values()
            .filter(|hc| hc.holder == holder && hc.target == target)
            .flat_map(|hc| hc.rights.iter().copied()).collect()
    }
    fn holds_right(&self, h: &str, t: &str, r: Right) -> bool { self.rights_of(h, t).contains(&r) }

    fn find_parent(&self, g: &str, target: &str, needed: &BTreeSet<Right>) -> Option<Cid> {
        self.caps.iter()
            .find(|(_, hc)| hc.holder == g && hc.target == target && needed.is_subset(&hc.rights))
            .map(|(c, _)| *c)
    }

    /// Delegate (guards G1, G2 from the formal companion). IFC guards (G4/G5)
    /// are applied by the DLM layer (Phase 4) before calling this.
    pub fn grant(&mut self, g: &str, r: &str, target: &str, rights_d: BTreeSet<Right>)
        -> Result<Cid, Refused>
    {
        if !self.holds_right(g, r, Right::Grant) { return Err(Refused("no grant edge g->r")); }
        let parent = self.find_parent(g, target, &rights_d)
            .ok_or(Refused("no amplification: grantor lacks the cap"))?;
        // Production: also perform seL4_CNode_Copy/Mint here so the KERNEL enforces it.
        Ok(self.add(HeldCap { holder: r.into(), target: target.into(),
                              rights: rights_d, parent: Some(parent), origin: Origin::Grant }))
    }

    fn descendants(&self, cid: Cid) -> BTreeSet<Cid> {
        let mut out = BTreeSet::from([cid]);
        let mut frontier = vec![cid];
        while let Some(x) = frontier.pop() {
            for (c, hc) in &self.caps {
                if hc.parent == Some(x) && out.insert(*c) { frontier.push(*c); }
            }
        }
        out
    }

    /// Transitive revocation == seL4_CNode_Revoke. Removes the cap and every
    /// capability derived from it, preserving I_prov.
    pub fn revoke_transitive(&mut self, cid: Cid) {
        let dead = self.descendants(cid);
        self.caps.retain(|c, _| !dead.contains(c));
        // Production: seL4_CNode_Revoke on the corresponding kernel cap.
    }
}
```

1. Port this policy layer, wiring `grant`/`revoke_transitive` to the seL4 CNode
   syscalls so the kernel is the enforcer and your Rust holds the metadata.
2. **Port the property tests** from `noether_demos.py` (Scenario 4) as Rust unit
   tests: thousands of random legal ops, assert the invariants hold every step.

**Milestone 2:** a capability-manager PD that performs delegation/revocation via
seL4, refuses amplification, and tracks provenance — with the Rust property tests
green.

---

## Phase 3 — Confined services and drivers (sDDF)

**Goal:** real drivers and services as mutually-distrusting confined PDs.

1. Start from the tutorial's **serial-server** pattern: a driver PD that gets the
   UART's MMIO region and its IRQ channel — and nothing else.
2. For production drivers, build on **sDDF** (the seL4 Device Driver Framework):
   network, block, serial classes with a confined structure.
3. Encode NOETHER's guarantees as system-description facts:
   - *Confused deputy (Scenario 1):* the "billing" region is simply not mapped
     into, and no channel reaches, the attacker PD. Inexpressible, per Phase 1.
   - *Driver confinement (Scenario 2):* the driver PD has the device region only.

**Milestone 3:** a driver that provably cannot touch the filesystem, because no
region or channel in the system description connects it there — verifiable by
reading the XML and confirmed by the kernel at runtime.

---

## Phase 4 — Information flow (the DLM crate)

**Goal:** decentralized labels enforced as a userspace policy over the caps.

For a static system, enforce labels at *design time* (a checker over the system
description). For dynamic delegation, a small **reference-monitor PD** applies the
DLM checks before any `grant`/`send_cap`. Reference (adapt; from `noether_dlm.py`):

```rust
use std::collections::BTreeSet;
pub type Principal = String;

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct Policy { pub owner: Principal, pub readers: BTreeSet<Principal> }
pub type Label = BTreeSet<Policy>;

pub fn can_read(p: &str, l: &Label) -> bool {
    l.iter().all(|pol| pol.owner == p || pol.readers.contains(p))
}
pub fn flows_to(a: &Label, b: &Label, universe: &BTreeSet<Principal>) -> bool {
    universe.iter().all(|p| !can_read(p, b) || can_read(p, a))   // readers(b) ⊆ readers(a)
}
pub fn declassify(l: &Label, actor: &str, owner: &str, new_readers: BTreeSet<Principal>)
    -> Result<Label, &'static str>
{
    if actor != owner { return Err("may not declassify another owner's policy"); }
    let mut kept: Label = l.iter().filter(|p| p.owner != owner).cloned().collect();
    kept.insert(Policy { owner: owner.into(), readers: new_readers });
    Ok(kept)
}
```

Wire `flows_to`/`can_read` into `grant`'s IFC guards (G4/G5). Port the DLM
property check (preorder + join laws) as Rust tests.

**Milestone 4:** a read cap is grantable only to an effective reader; owner-only
declassification works; the algebra tests pass.

---

## Phase 5 — Deterministic content-addressed state (Rust)

**Goal:** the L4 "deterministic world" — reproducible, tamper-evident, rollback.

Reference (adapt; from `noether_store.py`, using the `sha2` crate):

```rust
use sha2::{Sha256, Digest};
use std::collections::BTreeSet;

fn h(tag: &str, data: &[u8]) -> [u8; 32] {
    let mut d = Sha256::new(); d.update(tag.as_bytes()); d.update(data); d.finalize().into()
}
/// Merkle root over a canonical (sorted) set of serialized capabilities.
pub fn merkle_root(mut leaves: Vec<[u8; 32]>) -> [u8; 32] {
    leaves.sort();
    if leaves.is_empty() { return h("empty", b""); }
    while leaves.len() > 1 {
        leaves = leaves.chunks(2)
            .map(|c| { let r = if c.len() == 2 { c[1] } else { c[0] };
                       let mut buf = c[0].to_vec(); buf.extend_from_slice(&r); h("node", &buf) })
            .collect();
    }
    leaves[0]
}
```

Serialize each cap canonically (sorted fields), hash to a leaf, take the root.
Same state ⇒ same root (reproducible); any change ⇒ new root (tamper-evident);
keep roots in a history vector ⇒ rollback is a pointer swap.

**Milestone 5:** commit a state, rebuild it in a different order to the identical
root, alter one cap to get a different root, and roll back to a prior root.

---

## Phase 6 — Compatibility and CHERI

**Goal:** run legacy software confined, and (optionally) get hardware capabilities.

1. **Linux personality.** Microkit can manage a virtual machine per PD (it
   enforces one VM per managing PD). Run a Linux guest as a confined VM — it holds
   only the caps/regions you grant, so it's untrusted-by-construction. This gives
   you the ecosystem without expanding the TCB.
2. **CHERI (optional hardware upgrade).** Options, in rough order of effort:
   run on a Morello board with the CheriBSD stack (mature: memory-safe kernel +
   userspace, 10k+ packages) for evaluation; target CHERI-RISC-V on FPGA/QEMU;
   or license Codasip's CHERI RISC-V IP. Morello remains an experimental
   prototype — treat CHERI as a later hardening port, not a day-one requirement.

**Milestone 6:** a legacy Linux app runs inside a confined VM that cannot reach
anything you didn't grant it.

---

## Phase 7 — The verification track (run in parallel from day one)

Don't leave verification to the end; keep the spec living alongside the code.

1. **Design-time model checking.** Keep `NOETHER.tla` current; run it in TLC (or
   Apalache for symbolic checking) whenever you change the transition rules.
2. **Implementation checking.** Put the userspace components (cap runtime, DLM,
   store) under Rust verifiers — **Kani** (bounded model checking), **Verus**, or
   **Creusot** (deductive) — turning the Python property tests into machine
   checks on the actual Rust.
3. **Deep escalation (optional, expensive).** For the highest assurance, express
   the invariant in Isabelle/HOL and connect to seL4's `l4v` proofs. This is the
   seL4-scale, person-years effort; it is the ceiling, not the starting point.

**Milestone 7:** the invariant is model-checked on every design change and the
core Rust components pass a verifier in CI.

---

## The milestone ladder (checklist)

- [ ] 0. Microkit tutorial boots in QEMU
- [ ] 1. Your PDs boot isolated; unauthorized access faults
- [ ] 2. Capability-manager PD: delegation/revocation via seL4, provenance tracked, tests green
- [ ] 3. A confined driver that provably can't reach the filesystem
- [ ] 4. DLM enforcement + owner-only declassification
- [ ] 5. Content-addressed state: reproducible, tamper-evident, rollback
- [ ] 6. A legacy app running in a confined VM
- [ ] 7. Invariant model-checked + core components verified in CI

Reaching milestone 6 gives you a **real, bootable, capability-secure OS** at high
assurance (Rust safety + seL4's proven core + confined-by-construction
components). Milestone 7's deep proof of your *new* layers is the optional
escalation toward full formal assurance.

---

## Honest scope reminder

You inherit seL4's proof for the nucleus. What is still large is the mechanized
proof of NOETHER's *new* layers (cap-manager policy, IFC monitor, state store).
And the permanent gap remains: a proof shows the code meets its **specification**,
never that the specification is what you meant. Keep the spec small and reviewed.
```
