# NOETHER

### An operating system whose security properties are *theorems, not features*

> **Codename:** NOETHER — after Emmy Noether, whose theorem ties symmetries to *conserved quantities*. The organizing idea of this OS is that its security properties are **invariants conserved across every state transition**. Rename it to anything you like; the architecture is yours.

---

## 0. The honest framing (read this first)

"Solve for the most secure *and* most functional OS" is not a closed-form equation with a unique answer. It is a **multi-objective optimization** over at least three competing axes:

1. **Security** — how little authority any component holds, and how much an attacker gains by compromising one.
2. **Functionality** — richness of features, hardware support, performance, and the ability to run the software people actually want.
3. **Assurance** — how strongly the security claims are *proven* rather than hoped.

These trade against each other. Run all device drivers in the kernel and you gain functionality and speed but destroy assurance (any driver bug is a total compromise). Shrink the trusted base to something tiny and provable (the route the verified microkernel `seL4` took) and you gain assurance but historically pay in ecosystem and convenience.

Because there is no total order over these axes, "the most secure and most functional" is **not a single point**. NOETHER's thesis is one specific, principled move on the frontier:

> **Push functionality *out* of the trusted base. Grow what the system can *do* without growing what must be *trusted*.**

Everything below is downstream of that one sentence.

---

## 1. The central theorem (the mathematics under everything)

Model the whole OS as a **state-transition system**:

```
M = (S, s₀, →)
```

- `S` — the set of all possible system states (memory, capability tables, thread states, labels, …).
- `s₀` — the initial state at boot.
- `→ ⊆ S × S` — the transition relation. *Every* observable event — a syscall, an interrupt, an IPC send, a context switch — is a transition.

Now define a single predicate `I : S → Bool`, the **invariant bundle**, that encodes *all* the safety and security properties at once: memory safety, capability confinement, information-flow correctness, scheduler integrity.

The entire security argument is then **one induction**:

```
(base)      I(s₀)
(step)      ∀ s s'.  I(s) ∧ (s → s')  ⟹  I(s')
─────────────────────────────────────────────
(theorem)   ∀ s reachable from s₀.  I(s)
```

This is the conserved-quantity idea: `I` is conserved under `→` exactly the way momentum is conserved under a symmetry. Most operating systems treat memory safety, access control, and information flow as *three separate bolted-on subsystems*. NOETHER treats them as **components of a single inductive invariant**, which is what makes a machine-checked proof tractable and what stops the classic failure mode where two individually-correct subsystems interact to produce a hole.

The job of the kernel language and toolchain (§5) is mechanical: **a transition that cannot be shown to preserve `I` does not compile.** Security is therefore a *type-checking and proof-discharge* problem at build time, not a runtime monitor bolted on afterward.

---

## 2. Mathematical foundations, layer by layer

Each layer of the system rests on a specific, real body of theory. Nothing here is invented out of nothing — the *originality is in the synthesis*, the way these are wired into a single invariant.

| Property to guarantee | Mathematical tool | What it buys |
|---|---|---|
| Memory safety (spatial + temporal) | **Affine/linear type systems** + **separation logic** (Reynolds, O'Hearn; concurrent separation logic) | No use-after-free, no buffer overrun, no double-free — proven, not patched |
| No data races / deadlocks | **Affine ownership** + **session types** + **CSP / π-calculus** framing | Race freedom by construction; well-typed protocols don't deadlock |
| Authority confinement | **Object-capability calculus**; **take–grant** decidability results | Authority travels *only* by reference passing; reachability of authority is analyzable |
| Information flow / secrecy | **Lattice model of secure information flow** (Denning); **noninterference** (Goguen–Meseguer); **decentralized IFC** (Myers–Liskov) | "High-secrecy inputs cannot affect low-secrecy outputs" stated as a theorem |
| Functional correctness of the kernel | **Refinement** (refinement calculus, B-method, TLA⁺) | The implementation provably *refines* an abstract spec |
| State / supply-chain integrity | **Merkle DAGs / content addressing**; cryptographic hashing | Any system state is reproducible and tamper-evident |
| Cheap runtime memory safety | **Hardware capabilities** (a CHERI-style capability machine) | Spatial/temporal safety enforced in silicon, shrinking the proof burden |

The key structural fact: **information flow forms a lattice** `(L, ⊑, ⊔, ⊓)`. A label `ℓ` rides on every piece of data. The rule "information may flow from `a` to `b` only if `label(a) ⊑ label(b)`" is the entire secrecy story, and the compiler discharges most of these obligations statically (so the common case costs ~nothing at runtime). NOETHER uses a **decentralized** lattice — every principal owns its own label components — so it's usable by ordinary apps, not a rigid military classification scheme that nobody can actually program against.

---

## 3. Architecture: six layers, one tiny trusted core

```
┌──────────────────────────────────────────────────────────────┐
│  L5  Applications + Compatibility                              │
│      • native ocap apps   • POSIX/Linux "personality" guest    │  ← untrusted by construction
├──────────────────────────────────────────────────────────────┤
│  L4  Deterministic World  (content-addressed Merkle-DAG state) │
│      packages · configs · service topology · time-travel       │
├──────────────────────────────────────────────────────────────┤
│  L3  System Services  (mutually-distrusting, each confined)    │
│      drivers · filesystem · network stack · display            │
├──────────────────────────────────────────────────────────────┤
│  L2  Object-Capability Runtime  (POLA by default)              │
│      no ambient authority · authority = unforgeable reference   │
├──────────────────────────────────────────────────────────────┤
│  L1  The Verified Nucleus  (the entire TCB — kept tiny)        │  ◄── proven to refine spec
│      capabilities · address spaces · threads · IPC · IFC monitor│
├──────────────────────────────────────────────────────────────┤
│  L0  Hardware Capability Substrate  (CHERI-style + spec. domains)│  ◄── trust anchor
└──────────────────────────────────────────────────────────────┘
```

Everything **above L1 is outside the trusted computing base**. A compromise in a driver, the filesystem, the network stack, or any application is — by the central theorem — *confined*: it can only exercise the authority it was explicitly handed, and it cannot break the invariant `I` that the nucleus maintains. That confinement is the whole point of pushing functionality outward.

### L0 — Hardware capability substrate

Memory pointers are replaced by **hardware capabilities**: unforgeable, bounds-tagged references (this is the CHERI model, real silicon exists — Arm's Morello). The hardware enforces that you cannot fabricate a pointer, run off the end of a buffer, or reuse freed memory. This does two things: it gives spatial/temporal memory safety *at hardware speed*, and it **shrinks the software proof** — the nucleus can assume memory safety as a hardware axiom rather than re-proving it for every line.

To address **speculative side channels** (Spectre/Meltdown-class), L0 adds *speculation domains*: the IFC lattice (§2) is extended, as a coarse but **sound over-approximation**, to the microarchitectural channel. Code at different labels is never co-resident in the same speculation context. This costs performance, so it is opt-out for workloads that hold no secrets. (Honest scope note: this closes *microarchitectural* channels, not the *analog* ones — power and EM emanations remain out of scope; see §7.)

### L1 — The Verified Nucleus (the only thing you must trust)

A microkernel in the spirit of `seL4`, deliberately tiny, providing exactly five primitives and nothing else:

1. **Capabilities** — minting, delegation, revocation. The nucleus is the *only* entity that can mint a capability.
2. **Address spaces** — backed by L0 hardware capabilities.
3. **Threads & scheduling** — including the deterministic scheduler option (§6).
4. **IPC** — session-typed message passing (§6).
5. **The IFC monitor** — the small verified runtime piece that handles *dynamic* labels the compiler couldn't resolve statically.

The nucleus is written in the kernel language (§5) and **proven to refine its abstract specification** — the implementation does nothing the spec doesn't permit. The refinement chain runs *hardware caps → nucleus capabilities → the abstract object-capability calculus*, so authority reasoning is sound end-to-end.

### L2 — Object-capability runtime

There is **no ambient authority**. A process does not "have permissions" by virtue of who ran it (the Unix `root` model is abolished). It can only do what the specific capabilities it holds let it do — the **Principle of Least Authority (POLA)** is the default, not a hardening step. This structurally kills two classic bug classes: privilege escalation (there is no ambient privilege to escalate to) and the *confused-deputy* problem (authority and the request to use it travel together as one reference).

### L3 — System services as mutually-distrusting components

Drivers, the filesystem, the network stack, the display server — each is an ordinary confined component holding only the capabilities it needs. A malicious or buggy USB driver gets the USB controller capability and nothing else. It cannot read your filesystem, because it was never handed a capability to it. This is where the bulk of real-world functionality lives, *outside* the trusted base.

### L4 — The Deterministic World

The **entire system state** — installed packages, configuration, even the running service topology — is a **content-addressed Merkle DAG** (the lineage here is Nix/Guix, generalized to the whole machine). Consequences:

- **Reproducibility:** a state is fully described by its root hash; the same root rebuilds bit-for-bit.
- **Updates are typed transactions:** an update must be shown to *preserve the global invariant* `I` before it is admitted — "patch correctness" becomes a refinement check rather than crossed fingers.
- **Rollback is free:** previous states are just older DAG roots; reverting is a pointer swap. *Time-travel* is a built-in property of the data model, not a backup feature.
- **Supply-chain integrity:** every artifact is content-addressed and hash-pinned, so tampering is cryptographically detectable.

### L5 — Applications and compatibility (functionality without trust)

This is how you get the ecosystem without paying for it in assurance. A **POSIX/Linux personality** runs as an *unprivileged, capability-confined guest*. Legacy software runs unmodified — but it is **untrusted by construction**: it only ever holds capabilities you explicitly grant, so a compromised legacy app cannot violate the nucleus invariants. You get Linux's software catalogue *and* NOETHER's confinement at the same time. That is the resolution of the security/functionality tension: functionality lives where a breach is contained.

---

## 4. How NOETHER answers the known failures of existing systems

| Shortcoming of mainstream OSes | NOETHER's mechanism | Eliminated or mitigated? |
|---|---|---|
| Huge monolithic kernel TCB (millions of LOC; any bug ⇒ total compromise) | Tiny verified nucleus; everything else confined above L1 | **Eliminated** as a class (breaches are confined) |
| Memory-safety bugs (~70% of CVEs historically) | Hardware capabilities (L0) + affine types + separation logic (L5 lang) | **Eliminated** for native code; **confined** for legacy guests |
| Ambient authority → privilege escalation, confused deputy | Object-capability model, POLA by default, no `root` | **Eliminated** as a class |
| Coarse ACLs leak data across boundaries | Lattice IFC + noninterference, statically discharged | **Eliminated** for native code (subject to §7 assumptions) |
| Concurrency bugs (races, deadlocks) | Affine ownership + session types + structured concurrency | **Eliminated** for well-typed code |
| Risky updates / un-rollbackable patches | Merkle-DAG world; updates are invariant-preserving transactions; free rollback | **Eliminated** |
| Supply-chain tampering | Content addressing + hash pinning | **Mitigated** strongly (tamper-evident) |
| Speculative side channels (Spectre/Meltdown) | Speculation domains over the IFC lattice | **Mitigated** (microarch channels; not analog) |
| Physical side channels (power, EM, acoustic) | — | **Out of scope** (see §7) |

---

## 5. The systems language

A dedicated language is what makes the central theorem mechanical. Think of it as a Rust-descendant with proof obligations built in:

- **Affine ownership & lifetimes** — no aliasing of mutable state ⇒ no data races; no use-after-free.
- **Refinement types** — types refined by predicates (the lineage is Liquid Haskell / F⋆ / Dafny), so you can *state* functional properties in the type and have an SMT solver discharge them.
- **Embedded separation logic** — for the heap-manipulating, concurrent parts of the nucleus.
- **Information-flow labels in the type** — secrecy is part of the type signature; most noninterference obligations are discharged at compile time (≈ zero runtime cost in the common case).
- **Verified extraction** — the nucleus compiles through a verified pipeline to machine code (the lineage is CompCert / Project Everest's `F⋆ → Low⋆ → C`), so the proof covers the code that actually runs, not an idealization of it.

Two short, illustrative sketches (pseudocode):

```rust
// A guarded transition. If the body cannot be shown to preserve `I`,
// this does not compile.
transition send_message(s: State, c: Cap<Channel>, m: Msg)
    requires I(s) ∧ holds(current_thread, c)        // precondition
    ensures  I(result)                              // the invariant is conserved
{
    // ... the implementation; proof obligations auto-discharged ...
}
```

```rust
// A capability-confined service with an information-flow label.
// `Secret ⊑ Secret` but NOT `Secret ⊑ Public`, so a leak won't typecheck.
service KeyStore {
    fn sign(@self, key: Cap<PrivKey @Secret>, doc: Bytes @Public)
        -> Signature @Public;        // output is Public — must not depend on key bits beyond the signature
}
```

---

## 6. Concurrency and determinism

- **Structured concurrency** — task lifetimes nest; no orphaned threads, no leaked work.
- **Session-typed IPC** — every channel carries a *session type* describing the legal protocol; the type checker guarantees both parties follow it and that well-typed sessions are deadlock-free (the theory is from session types and the π-calculus).
- **Deterministic-by-default scheduler (optional mode)** — for testing, debugging, and reproducible builds, the scheduler can run fully deterministically, so a bug reproduces exactly. Combined with the L4 content-addressed world, an entire run is reproducible from a root hash + an input log.

---

## 7. Threat model — what is *proven* vs *assumed*

This section is the difference between an honest design and a fantasy. "Verified" never means "perfectly secure." It means: *the implementation refines the specification, given a stated set of assumptions.* The residual attack surface is exactly the gap in those assumptions. Stated plainly, NOETHER's guarantees hold **only if**:

1. **The hardware is correct** — the L0 capability machine actually enforces what its model says. A silicon bug is below the proof.
2. **The proof assistant / SMT solver is sound** — the checking kernel is small and audited, but it is trusted.
3. **The specification captures intent** — the deepest limit. Code can be *provably correct against the wrong spec.* A complete proof against an incomplete spec is a real, residual risk, not a solved problem.
4. **The physical layer is out of scope** — power analysis, EM emanation, acoustic, thermal, and fault-injection attacks operate below the digital abstraction the proof lives in.
5. **Humans** — social engineering, a user granting a capability to malware they were tricked into trusting, a malicious insider with legitimate authority. No formal method touches this.

What you *do* get, contingent on (1)–(2): memory safety, capability confinement, and information-flow noninterference are **theorems about every reachable state**, and any breach above L1 is **confined to the authority that component was granted**. That is a dramatically stronger position than any mainstream OS — but it is a *bounded* claim, and the boundaries above are where a serious adversary will spend their effort.

---

## 8. Tradeoffs and open problems (no free lunch)

- **Verification cost.** `seL4`'s proof took person-*years* for ~10k LOC. NOETHER's nucleus-language approach is designed to amortize this (proofs ride along with code), but the upfront engineering is enormous. This is the real price of assurance.
- **Performance.** Capability checks, IPC across confined services, and speculation-domain isolation all cost cycles. The design trades some raw speed for containment; the deterministic scheduler trades more.
- **Ecosystem bootstrapping.** Native ocap software has to be written or ported; the Linux personality (L5) is the bridge, but it runs legacy code at lower assurance.
- **The spec-adequacy problem (the hard one).** As in §7.3 — proving the system meets its spec does not prove the spec is *what you actually wanted*. Closing this needs better specification languages and validation, and it is genuinely unsolved.
- **POLA usability.** Least-authority systems can be annoying: software constantly needs capabilities granted. Good defaults and a clean "powerbox"-style granting UI are the difference between secure-and-usable and secure-and-abandoned.

---

## 9. A buildable roadmap

1. **Pin the spec.** Write the abstract state machine `M` and the invariant `I` in a proof assistant *first*.
2. **Target a CHERI machine** (Morello hardware or a CHERI-RISC-V emulator) for L0.
3. **Build the kernel language** (or adopt and extend F⋆/Low⋆) so transitions discharge `I`.
4. **Implement and verify the nucleus** (L1) against the spec; verified extraction to machine code.
5. **Grow services outward** (L3) one confined component at a time — start with a filesystem and a network stack.
6. **Lay the deterministic world** (L4) as a content-addressed store with transactional, invariant-checked updates.
7. **Ship the Linux personality** (L5) so real software runs from day one.
8. **Build the powerbox** so granting authority is humane.

---

### One-line summary

> **NOETHER moves functionality out of the trusted base so the system can do more without trusting more — and it states memory safety, authority confinement, and information-flow secrecy as a single inductive invariant conserved across every transition, so they are theorems rather than features.** What it cannot promise is captured honestly in §7: the proof is only as good as the hardware, the checker, and — above all — the specification.
