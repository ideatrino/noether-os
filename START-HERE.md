# NOETHER — Start Here (a friendly on-ramp)

Welcome! The other documents in this project are written for experienced systems
programmers. **This page is the friendly version.** You don't need any special
background to understand *why* NOETHER is interesting — and you can run part of it
on your own computer today.

Take your time. Nothing here is a test.

---

## The one big idea, in plain English

Think about how permissions usually work on a computer. It's like a **guest list
at a club**: for every room, a bouncer checks whether your name is on the list.

NOETHER works differently. Permissions are like **physical keys**. You can only
open a door if you're actually holding its key. The only way to give someone
access is to hand them a copy of the key. You *cannot* open a door just by knowing
its name.

That small change is the heart of the whole project. Because you can only act with
keys you're holding, a program can never be tricked into misusing power it was
never given. A surprising number of real security disasters come from the
"guest list" style, and the "keys" style just... doesn't have them.

---

## A few more ideas, gently

**No all-powerful admin.** On most systems there's a super-user ("root") who can
do anything — and if an attacker becomes root, they own everything. NOETHER has no
god-mode. Every program only holds the specific keys it was given, so breaking one
program doesn't hand over the whole house.

**Everyone starts with an empty keyring.** A new program gets *only* the keys it
needs to do its job, and nothing more. So a hacked printer driver holds the
printer key and that's it — it can't read your files, because it was never given a
key to them.

**"Proven safe" means a rule that's always true.** We write down a few safety
rules and then have the computer check that, no matter what the system does, those
rules never break — a bit like proving a board game can never reach an illegal
position. That's what "the security is a theorem" means.

**Secrets carry a label.** Sensitive data is tagged with who's allowed to see it,
and the system refuses to let it leak to anyone who isn't — and the *owner* of the
secret is the one who controls that, not some central authority.

**Save points you can always return to.** The whole system's state gets a
fingerprint (a hash). You can always roll back to an earlier save, and if anything
is tampered with, the fingerprint changes, so it gets caught.

That's the entire project, in five ideas. Everything else is detail.

---

## Try it today (the friendliest step)

You only need **Python** installed. Then, in this folder:

```
python3 noether_demos.py
```

You'll see it walk through real scenarios: an attacker *failing* to trick a
program into overwriting a billing file, a hacked driver that *cannot* reach your
files, and thousands of automatic safety checks all passing. It prints what's
happening in plain-ish English as it goes.

**A fun first experiment:** open `noether_kernel.py`, read the comments (they
explain each piece), then open `noether_demos.py` and change one of the scenario
setups — for example, give the attacker a key it shouldn't have — and re-run it.
Watch the safety checks react. Breaking it *on purpose* is one of the best ways to
understand it.

---

## An honest map of the journey

The *ideas* above are reachable right now. Building the full, real operating
system is a long climb — and that's completely normal; people spend careers here.
Here's a realistic ladder, easiest first:

1. **Run and read the Python model.** (You can start today.) This teaches the
   actual concepts — capabilities, confinement, information flow — with code
   simple enough to follow.
2. **Get comfortable with the concepts** by tweaking the model and watching what
   happens. *(A few weeks of tinkering.)*
3. **Learn operating-system basics** — what a process is, what memory is, what a
   kernel does. A good intro OS course or book. *(A few months.)*
4. **Learn Rust** — the free official "Rust Book" is excellent. *(A few months.)*
5. **Do the seL4 Microkit tutorial** (it builds a tiny system step by step). After
   that, `IMPLEMENTATION-GUIDE.md` will actually read as friendly.

You do **not** need to finish this ladder to get a lot out of NOETHER. Steps 1–2
alone will teach you real ideas that working security engineers use.

---

## Which file is which (friendliest → most advanced)

- **START-HERE.md** — you're reading it.
- **noether_demos.py** — run this; it's the guided tour.
- **noether_kernel.py** — the model itself, with explanatory comments.
- **noether_dlm.py / noether_store.py / noether_modelcheck.py** — self-contained
  pieces you can run one at a time (labels, save points, safety checking).
- **NOETHER-OS-design.md** — the big-picture design, in prose.
- **NOETHER-formal-companion.md** — the mathematical proofs (this one is deep).
- **IMPLEMENTATION-GUIDE.md** — how to build the real thing on seL4 (advanced).

---

## One last thing

If any of this feels over your head, that's not a sign you don't belong here — it's
just a sign you've found the edge of what you know yet, which is exactly where
learning happens. Start with the Python. Poke at it. Break it. The rest can wait.
