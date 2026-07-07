# Running NOETHER on a Windows 11 Laptop

**Read this first.** NOETHER is not a finished operating system, so you are *not*
replacing Windows and you should *not* wipe your drive or change your boot setup.
Everything here runs safely **alongside** Windows 11, like any other program.
There are two paths:

- **Path A — Run the reference model.** ~10 minutes, easy, needs only Python.
  Start here.
- **Path B — Build the real prototype.** Advanced. Uses WSL2 (a Linux environment
  built into Windows) to run the seL4 tutorial system inside an emulator.

Your laptop brand (HP) makes no difference; these steps are the same on any
Windows 11 machine.

---

## Path A — Run the reference model (start here)

This runs the tested Python model — the confined-driver demo, the confused-deputy
demo, the safety checks, all of it. **No coding required**, and it installs
nothing beyond Python (the code uses only Python's standard library).

### Step 1 — Install Python

1. Go to https://www.python.org/downloads/ and click the yellow "Download Python"
   button (any recent 3.x version is fine).
2. Run the installer. **Important:** on the first screen, tick the box
   **"Add python.exe to PATH"** before clicking Install. (This one checkbox saves
   a lot of trouble.)
3. Let it finish, then close the installer.

*(Alternative: open the Microsoft Store, search "Python", and install it there —
that adds it to PATH automatically.)*

### Step 2 — Check it worked

1. Press the **Windows key**, type `Terminal`, and open **Windows Terminal** (or
   "PowerShell" — either is fine).
2. Type this and press Enter:
   ```
   python --version
   ```
   You should see something like `Python 3.13.1`. If instead you get an error,
   try `py --version`. If that works, use `py` in place of `python` everywhere
   below. If neither works, reinstall Python and make sure the PATH box is ticked.

### Step 3 — Get the project files onto your laptop

1. Download the files I shared in our conversation. At minimum you need these two
   together in one folder (the demo imports the kernel):
   - `noether_kernel.py`
   - `noether_demos.py`
   You can also grab `noether_dlm.py`, `noether_store.py`, `noether_modelcheck.py`,
   and the `.md` guides.
2. Put them in a new folder, for example: `Documents\noether`. The two `.py` files
   above **must be in the same folder**.

### Step 4 — Run it

1. In your Terminal, move into that folder. Type `cd ` (with a space), then drag
   the folder from File Explorer onto the Terminal window (it pastes the path),
   then press Enter. For example:
   ```
   cd C:\Users\YourName\Documents\noether
   ```
2. Run the main tour:
   ```
   python noether_demos.py
   ```
   (Use `py noether_demos.py` if `python` didn't work in Step 2.)

You'll see it walk through the scenarios and finish with a batch of safety checks
that all pass.

### Step 5 — Run the other pieces (optional)

Each of these runs on its own:
```
python noether_dlm.py          # decentralized secrecy labels + declassification
python noether_store.py        # save points: reproducible, tamper-evident, rollback
python noether_modelcheck.py   # exhaustive safety checking with a counterexample
```

### If something goes wrong

- **`python` is not recognized** → Python isn't on your PATH. Reinstall and tick
  "Add python.exe to PATH", or try `py` instead.
- **`can't open file ... noether_demos.py`** → you're not in the right folder.
  Redo Step 4's `cd`, and confirm the file is really there with `dir`.
- **`ModuleNotFoundError: noether_kernel`** → `noether_kernel.py` isn't in the
  same folder as `noether_demos.py`. Put them together.

That's it — you're running NOETHER's core on your laptop.

---

## Path B — Build the real prototype (advanced)

This sets up a Linux environment *inside* Windows (WSL2) so you can follow the
seL4 Microkit tutorial and, from there, `IMPLEMENTATION-GUIDE.md`. The result runs
in an **emulator (QEMU)** — a tiny seL4 system in a window, not a replacement for
Windows. Expect this to take a couple of hours and some patience; it assumes basic
comfort with a Linux command line.

> Reality check: even completed, this is a research/prototype toolchain for
> building and experimenting — not a daily-driver OS. Path A is where the learning
> value is; do Path B only if you specifically want to build on seL4.

### Step 1 — Install WSL2 (Linux on Windows)

1. Press **Windows key**, type `PowerShell`, right-click it, choose
   **Run as administrator**.
2. Run:
   ```
   wsl --install
   ```
   This installs WSL2 and Ubuntu by default. Reboot when it asks.
3. After reboot, an Ubuntu window opens and asks you to create a username and
   password (this is separate from your Windows login — remember it).

### Step 2 — Update Ubuntu

In the Ubuntu terminal:
```
sudo apt update && sudo apt upgrade -y
```
(Enter the password you just made when prompted.)

### Step 3 — Install the build tools

The seL4 Microkit tutorial's **Part 0** lists the exact, current packages —
follow it rather than a frozen list here, because the names change between
versions. It's at:
https://docs.sel4.systems/projects/microkit/tutorial/

In broad strokes you'll install: a build toolchain (`build-essential`, `make`),
**QEMU** for ARM emulation, and an **AArch64 cross-compiler**. The tutorial gives
the precise `apt install` line for Linux — WSL2 *is* Linux, so use those Linux
instructions.

### Step 4 — Get the Microkit SDK

Inside Ubuntu, following the tutorial (the version updates over time; the current
one is 2.2.0):
```
mkdir microkit_tutorial && cd microkit_tutorial
curl -L https://github.com/seL4/microkit/releases/download/2.2.0/microkit-sdk-2.2.0-linux-x86-64.tar.gz -o sdk.tar.gz
tar xf sdk.tar.gz
```
Then download the tutorial code as shown on the tutorial page.

### Step 5 — Build and run the tutorial in QEMU

Follow the tutorial steps to build the system image and launch it in QEMU. When
you see the tutorial's system boot and print output, **your seL4 toolchain
works** — this is Milestone 0 from `IMPLEMENTATION-GUIDE.md`.

### Step 6 — Edit comfortably (recommended)

Install **VS Code** on Windows (https://code.visualstudio.com/) and its **WSL**
extension. Then, from your Ubuntu terminal, type `code .` in a project folder — it
opens that Linux folder in VS Code on Windows, so you get a nice editor while the
files and build stay in Linux. From here, work through the phases in
`IMPLEMENTATION-GUIDE.md`.

---

## Honest expectations

- **Path A** is real and complete: you're running NOETHER's actual security core
  today, on your laptop, safely alongside Windows.
- **Path B** gets you a working seL4 build environment and the tutorial system in
  an emulator — the genuine starting point for building the prototype, but a long
  road, and still not a daily operating system.
- **Neither path touches your Windows install, your files, or your boot setup.**
  Don't attempt to install any of this as your computer's main OS — that's not
  what it is, and there's no safe or finished way to do that.

Start with Path A. Have fun breaking the demos on purpose — it's the best way to
learn how the safety actually works.
