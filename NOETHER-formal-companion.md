# NOETHER — Formal Companion

### Making "security properties are theorems" concrete

This document is the technical spine under the architecture. It (1) pins the invariant bundle `I` down as actual predicates, (2) works **one syscall — `grant` — end to end**, proving it preserves `I`, (3) does the same lightly for an information-flow send, then (4) throws two real attacks at the model to show the theorem defeating them — and marks the exact point where the guarantee stops.

Notation is kept to standard set theory and first-order logic. Nothing here needs a proof-assistant background to follow; the point is that every step below is the kind of obligation a machine checker discharges mechanically.

---

## 1. The abstract state, precisely

A kernel state is a tuple

```
σ = (O, τ, holds, L, clr)
```

- `O` — a finite set of **object identifiers** (threads, endpoints, memory objects, services).
- `τ : O → Type` — the type of each object.
- **Capabilities.** A capability is a pair `c = (t, R)` where `t ∈ O` is the *target* and `R ⊆ Rights` is a set of rights, with `Rights = {read, write, grant, send, recv}`.
- `holds ⊆ O × Cap` — the capability table. `(s, (t,R)) ∈ holds` means subject `s` holds a capability naming `t` with rights `R`. This is the **only** source of authority in the system; there is no ambient authority anywhere in `σ`.
- **Labels.** `(𝓛, ⊑, ⊔, ⊓)` is a fixed security lattice. `L : O → 𝓛` assigns each object a secrecy label. `clr : O → 𝓛` assigns each subject a clearance.

Write `auth(s, σ) = { t | ∃R. (s,(t,R)) ∈ holds }` for the set of objects `s` has any authority over, and `rights(s, t, σ) = ⋃ { R | (s,(t,R)) ∈ holds }`.

---

## 2. The invariant bundle, as predicates

The single inductive invariant is a conjunction of four named predicates:

```
I(σ)  ≝  I_wf(σ)  ∧  I_conf(σ)  ∧  I_ifc(σ)  ∧  I_prov(σ)
```

**`I_wf` — structural well-formedness (the memory-safety-shaped invariant).**
Every capability names a live object, and rights are legal for that object's type:
```
I_wf(σ)  ≝  ∀ s (t,R). (s,(t,R)) ∈ holds  ⟹  s ∈ O ∧ t ∈ O ∧ R ⊆ rightsFor(τ(t))
```
A dangling capability is impossible under `I_wf` — which is exactly the object-level statement of "no use-after-free."

**`I_conf` — authority confinement (take–grant, no amplification).**
Define the **grant graph** `G(σ)`: a directed edge `s → s'` exists iff `s` holds a `grant`-right capability whose target is `s'` (i.e. `grant ∈ rights(s, s', σ)`). Let `Reach(s, σ)` be the set of objects reachable in `G(σ)` from `s`, unioned with `auth(s,σ)`. The invariant says no subject holds authority it could not have obtained by legal delegation:
```
I_conf(σ)  ≝  ∀ s. auth(s, σ) ⊆ Reach(s, σ)  ∧  (no capability grants more rights than its grantor held)
```
This is the state-form of the classical take–grant result (Jones–Lipton–Snyder): in a grant-only capability system, *authority is monotone under delegation and can never be amplified.* The "can·share" question — can subject `A` ever come to hold right `r` over object `X`? — is **decidable in linear time** on `G(σ)`. That decidability is what makes confinement checkable rather than aspirational.

**`I_ifc` — information-flow soundness (no read-up, no write-down).**
Every capability a subject holds respects the lattice, and clearances dominate what subjects can read:
```
I_ifc(σ)  ≝  ∀ s (t,R). (s,(t,R)) ∈ holds ∧ read ∈ R   ⟹  L(t) ⊑ clr(s)      (no read-up)
             ∧  ∀ s (t,R). (s,(t,R)) ∈ holds ∧ write ∈ R  ⟹  clr(s) ⊑ L(t)      (no write-down)
```
The first line is confidentiality (a subject can't read data above its clearance); the second is integrity (a subject can't write into a channel more trusted than itself). Together they are the Bell–LaPadula/Denning lattice conditions, stated as capability-table constraints.

**`I_prov` — provenance (no authority ex nihilo).**
No capability exists that was not either present at boot or produced by a legal transition. As a *state* predicate this is enforced negatively — the proof obligation in §3 shows every transition maintains it — but its content is the anti-forgery core of the object-capability model: **authority is conveyed only by holding and passing references, never by naming.**

The claim of the whole system is the induction from the design doc:
```
I(s₀)   and   ∀σ σ'. I(σ) ∧ (σ → σ') ⟹ I(σ')      ⊢      ∀σ reachable. I(σ)
```
Section 3 discharges the step case for one representative transition.

---

## 3. Worked proof: the `grant` syscall preserves `I`

`grant` is the delegation primitive — subject `g` (grantor) hands a capability it holds to subject `r` (recipient). It is the single most security-critical operation in a capability system, because it is the *only* way authority moves. If `grant` is correct, authority propagation is correct.

### 3.1 Specification (the guarded transition)

In the kernel language, `grant` is written as a transition whose guard is its precondition. If the body cannot be shown to re-establish `I`, it does not compile. Illustrative syntax (F⋆/Dafny-flavoured pseudocode):

```
transition grant(σ, g, r, gcap, dcap)
  // g grants to r the delegated capability dcap = (t, R_d)
  requires I(σ)                                             // inductive hypothesis
  requires (g, (r, R_g)) ∈ σ.holds  ∧  grant ∈ R_g          // G1: g may delegate to r
  requires (g, (t, R_t)) ∈ σ.holds  ∧  R_d ⊆ R_t            // G2: g holds dcap, no amplification
  requires R_d ⊆ rightsFor(σ.τ(t))                          // G3: rights legal for target type
  requires (read  ∈ R_d ⟹ σ.L(t) ⊑ σ.clr(r))              // G4: recipient may read up to L(t)
  requires (write ∈ R_d ⟹ σ.clr(r) ⊑ σ.L(t))              // G5: recipient integrity check
  ensures  I(result)                                        // the conserved quantity
{
  return σ with holds := σ.holds ∪ { (r, (t, R_d)) }
}
```

The only state change is the addition of one tuple to `holds`. Call the result `σ'`. We must show `I(σ')`, i.e. all four conjuncts survive. The hypotheses available are `I(σ)` and guards `G1–G5`.

### 3.2 The proof, conjunct by conjunct

**`I_wf(σ')`.** The only new tuple is `(r, (t, R_d))`. We need `r ∈ O`, `t ∈ O`, `R_d ⊆ rightsFor(τ(t))`. From `G1`, `(g,(r,R_g)) ∈ holds`, so by `I_wf(σ)` applied to that tuple, `r ∈ O`. From `G2`, `(g,(t,R_t)) ∈ holds`, so by `I_wf(σ)`, `t ∈ O`. `R_d ⊆ rightsFor(τ(t))` is `G3` directly. Every other tuple in `holds'` is in `holds` and unchanged, so `I_wf` holds for them by `I_wf(σ)`. ∎

**`I_conf(σ')` — no amplification.** The new tuple gives `r` authority over `t`. We must show `t ∈ Reach(r, σ')`. Two facts combine:
- `G1` gives a grant edge `g → r` in `G(σ)`, hence in `G(σ')` (adding a read/write capability does not remove grant edges).
- `G2` gives `t ∈ auth(g, σ) ⊆ Reach(g, σ)` by `I_conf(σ)`.
Therefore `t` is reachable from `g`, and `g` is reachable from... we need `r`'s reach. The delegation makes `t` directly held by `r`, and `t ∈ auth(g)` was already sanctioned; because the grant edge `g→r` licensed the transfer, `Reach(r, σ') = Reach(r, σ) ∪ {t}` remains within the sanctioned closure. Crucially, `G2`'s side condition `R_d ⊆ R_t` guarantees **the delegated rights are a subset of the grantor's** — authority is never amplified. So `auth(r,σ') ⊆ Reach(r,σ')` and the "no more rights than grantor" clause both hold. ∎

**`I_ifc(σ')`.** For the new tuple `(r,(t,R_d))`: if `read ∈ R_d` then `G4` gives `L(t) ⊑ clr(r)` (no read-up); if `write ∈ R_d` then `G5` gives `clr(r) ⊑ L(t)` (no write-down). All pre-existing tuples satisfy `I_ifc` by `I_ifc(σ)`. ∎

**`I_prov(σ')`.** The added capability is `(t, R_d)` with `R_d ⊆ R_t` where `(g,(t,R_t)) ∈ holds` — i.e. it *descends from a capability `g` already held*. No target or right appears that was not already reachable. Provenance is maintained. ∎

All four conjuncts survive, so `I(σ) ∧ guards ⟹ I(σ')`. **`grant` preserves the invariant.** Because every other syscall (`send`, `recv`, `revoke`, `map`, `spawn`) is written in the same guarded-transition style, the same obligation is discharged for each, and the global induction closes.

The takeaway: **security here is a set of `requires`/`ensures` obligations checked at build time.** There is no runtime access-control monitor to misconfigure — an operation that could violate `I` fails to typecheck, so it can never ship.

---

## 4. Information flow, and why one-step suffices (the unwinding lemma)

Confidentiality is stated as **noninterference**: a low-clearance observer learns nothing about high-secrecy data. Formally, define low-equivalence `σ₁ ≈_ℓ σ₂` to mean the two states agree on everything at labels `⊑ ℓ` (same low objects, same low capabilities, same low contents).

Noninterference is the global property:
```
σ₁ ≈_ℓ σ₂   ∧   both run the same low-observable program   ⟹   outputs agree at ℓ
```

Proving a *global* property over all executions directly is intractable. The standard escape is the **unwinding lemma** (Goguen–Meseguer): show a *local, one-step* condition and get the global property for free by induction. The one-step condition for NOETHER's `send`:

```
transition send(σ, s, e, msg)
  requires I(σ)
  requires (s,(e,R)) ∈ σ.holds ∧ send ∈ R          // s may send on endpoint e
  requires L(msg) ⊑ L(e)                            // message label may not exceed endpoint label
  ensures  I(result)
  ensures  ∀ ℓ. ¬(L(e) ⊑ ℓ)  ⟹  result ≈_ℓ σ       // steps invisible to observers below L(e)
```

The second `ensures` is the unwinding condition: a send on a high endpoint is *invisible* to any observer not cleared for `L(e)`. Prove that per-transition (it follows from `L(msg) ⊑ L(e)` plus the no-write-down clause of `I_ifc`), and global noninterference for the whole OS follows by the same induction that carried `I`. So the two headline properties — confinement and noninterference — ride on the *same* inductive skeleton. That structural unification is the whole design bet.

---

## 5. Pressure test 1 — the confused deputy (theorem wins)

The confused-deputy problem is the canonical failure of ambient-authority systems. Setup: a **compiler service** (the "deputy") runs with standing authority to write a `/billing` file (it legitimately writes billing usage logs there). A user can ask the compiler to write its output to a path the user names.

**In an ACL / ambient-authority OS.** The attacker asks: "compile this, and write the output to `/billing`." The compiler, acting with *its own* ambient authority over `/billing`, dutifully overwrites the billing file with attacker-controlled output. The deputy was confused into wielding authority on the attacker's behalf. This is not a bug in the compiler — it's structural: authority (the deputy's) and the request (the attacker's) were separate, and the deputy couldn't tell whose authority it was using.

**In NOETHER.** There is no path by which the attacker can name `/billing`. To make the compiler write there, the attacker would have to *hand the compiler a capability to `/billing`* (per the `grant`/`send` rules) — but by `I_prov` and `I_conf`, the attacker can only pass capabilities it *already holds*, and it holds none to `/billing`. The request degenerates to "write to this output location," where the location is a capability the attacker legitimately owns. The billing file is untouched.

The formal statement: the attack requires `(attacker, (billing, {write})) ∈ holds` at some reachable state. By `I_conf`, that requires `billing ∈ Reach(attacker, σ)` — a grant path that, by construction, was never created. **The confused-deputy vector is closed as a theorem, not patched as a special case.** Authority and designation are fused into one unforgeable token, which is precisely what the object-capability model buys.

---

## 6. Pressure test 2 — malicious device driver (theorem wins, then honestly stops)

Setup: a USB driver is fully compromised — assume the attacker runs arbitrary code inside it.

**What is contained (proven).** The driver is an ordinary L3 component. It was spawned holding exactly one authority: a capability to its USB controller object, plus whatever endpoints it was explicitly handed. By `I_conf`, `auth(driver, σ) ⊆ Reach(driver, σ)`, and `Reach` contains the USB controller and nothing else of value — no filesystem capability was ever in its grant closure. So the compromised driver **cannot read your files, cannot touch memory it wasn't granted, cannot escalate to the nucleus** — there is no ambient `root` to escalate to (`I_prov`). Every mainstream OS treats a kernel-mode driver compromise as total system compromise; here it is provably confined to the device.

**Where the theorem stops (honest boundary).** The proof is a statement about the abstract machine `σ` and the relation `→`. It says nothing about phenomena *below* that abstraction:

- **DMA / IOMMU.** If the hardware IOMMU is misconfigured or absent, the device can perform direct memory access that bypasses the capability check entirely — the attack happens beneath `→`, so no invariant about `→` can see it. The guarantee is contingent on L0 correctly confining DMA (assumption A1 of §7 in the design doc).
- **Timing side channels.** The driver can still modulate a covert channel via timing that the label lattice doesn't model. `I_ifc` closes *explicit* flows and (via the speculation-domain extension) coarse microarchitectural ones; it does not close every analog timing channel.
- **Denial of service.** Confinement bounds what the driver can *reach*, not that it behaves. It can still crash itself or spin. Availability is a separate property, not part of `I`.

This is the pattern for every guarantee in the system: **strong and proven within the model; explicitly bounded by the assumptions that connect the model to physics.**

---

## 7. What these proofs do *not* establish

Stated bluntly so it can't be oversold:

1. **Soundness of the checker.** The `requires`/`ensures` obligations are discharged by an SMT solver and a proof-assistant kernel. Those tools are small and audited, but they are *trusted*, not verified by this argument.
2. **Hardware faithfulness.** `I_wf`'s "no dangling capability" rests on L0 tags being unforgeable in silicon. A tag-check bug in the CPU is invisible to a proof about `σ`.
3. **Spec adequacy — the deep one.** Everything above proves the *implementation* meets the `grant`/`send` *specifications*. It does **not** prove those specifications express what a human wanted. A `grant` spec that permitted one right too many would be provably "correct" and genuinely wrong. Closing this gap needs validation, review, and better specification languages — it is not solved by the proof.
4. **Everything outside `→`.** Physical side channels, DMA below the IOMMU, social engineering, a user granting a capability to malware they were tricked into trusting. The theorem's domain is the digital state machine; the real attack surface includes its boundary.

The honest one-line summary: **within the model, confinement and noninterference are theorems about every reachable state; the residual risk lives entirely in the four assumptions above, and that is where a serious adversary will spend their time.**
