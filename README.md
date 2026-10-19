<p align="center">
  <img src="GenCHERI_logo.jpg" alt="GenCHERI logo" width="220">
</p>

<h1 align="center">GenCHERI</h1>

<p align="center">
  <b>Generate CHERI capability headers for the RISC-V VP, then port and build them with one click.</b>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/python-3.8%2B-blue">
  <img alt="GUI" src="https://img.shields.io/badge/GUI-tkinter-informational">
  <img alt="Target" src="https://img.shields.io/badge/target-CHERI%20RISC--V%20VP-success">
</p>

---

## What it does

GenCHERI takes a few design choices for a CHERI capability format and writes the two C++ headers the CHERI RISC-V Virtual Prototype (VP) needs:

| File | Content |
|------|---------|
| `general.h` | `CAP_*_TOP/BOT` bit-position macros, permission / otype / flag enums, `PERM`/`OTYPE`/`FLAG`/`CHERI` typedefs, `CAP_LEN`, `BYTES_PER_TAG`, `MIN_INSTR_BYTES` |
| `cheri_utils.h` | Template-specific macros (`CAP_IE`, `CAP_TE_*`, `CAP_T_*`, `CAP_BE_*`, `CAP_B_*`, `CAP_L7`), `NULL_CAP`, `INF_CAP` and the `cheri32` namespace declarations |

It then copies them into the right folders of your riscv-vp checkout (replacing the old ones) and runs `cmake` and `make` for the **TestRig** or **QEMU** VP.

## Features

- **Three capability templates**
  - **Template 1 (Spandan) / Template 2 (Sail)**: fixed 32-bit metadata. The limits of the permission, otype and flag widths depend on each other; the remaining bits become the bound.
  - **Template 3 (General)**: variable layout (`struct CHERI`). Perm up to 32 bits, otype up to 32 bits, flag up to 32 bits, bound up to 64 bits (rounded up to 8/16/32/64). Every field sits in a slot as wide as its storage type.
- **User-defined permissions, otypes and flags**
  - Permissions are appended after the **11 hardware permissions** (upper-cased).
  - Otypes: `Unsealed`, `Sealed` and `Reserved` come first; at least four otype values are reserved, so up to `2^o − 4` user otypes fit (user otypes start at `Unsealed − 4`).
  - Flags are appended after `CAP_MODE = 0` (up to `f − 1`, upper-cased).
- **Name checks**: names must be valid C identifiers, differ from each other **across all three groups** (case-insensitive) and must not reuse a built-in name (hardware permissions, `Unsealed`, `Sealed`, `Reserved`, `CAP_MODE`). The GUI refuses a bad name at the moment you finish typing it, so a later build cannot fail on a redefinition.
- **Any field order**: drag the Perm / Otype / Flag / Bound chips into any of the 24 orders (MSB → LSB).
- **Bound tooltip**: hover the Bound chip to see how it is divided (`BE`, `B`, `TE`, `T`, `L7`, `IE`, wasted) and which absolute bits each part uses.
- **Smallest storage type** (`uint8_t` … `uint64_t`) chosen automatically for every field.
- **Compressed-instruction switch** (`MIN_INSTR_BYTES` 2 or 4).
- **Tkinter GUI** with live limits, collapsible steps, a logo-themed look, **TestRig / QEMU build buttons** and a streamed build log.
- **Command-line mode** with the same rules (shared in `gen_config.py`).
- **Safe porting**: everything is checked before the first copy, and replaced files are kept as `.bak`.

## How it works

Everything is driven by one validated configuration dictionary (`build_cfg()` in `gen_config.py`); the terminal tool and the GUI call the same functions, so their limits can never differ.

1. **Limits.** For Templates 1/2 the metadata is fixed to 32 bits. With `p`, `o`, `f` perm/otype/flag bits the bound gets `b = 32 − (p+o+f)` bits, and each field's maximum depends on what the previous ones took (see the cheat-sheet). Template 3 fields are independent.
2. **Storage types.** Each field is stored in the smallest of `uint8_t/16/32/64`. For Template 3, `meta_w` is the sum of the four slot sizes and `CAP_LEN = 32 + meta_w`.
3. **Compressed bound (Templates 1/2).** With `spare = b − reserved`, `T` may be `1 … 1 + ⌊spare/2⌋`, `B = T + 2`, and leftover bits are wasted.
4. **Layout.** The field order (MSB → LSB) is walked from the LSB side. `layout()` packs fields tightly (T1/T2); `layout_gen()` advances by the *storage* size of each field (T3), so the macros match `struct CHERI`.
5. **Names.** All user names are checked case-insensitively across perms, otypes and flags, and against built-in names, before anything is written.
6. **Generation, then port and build.** `generate_headers()` writes the two files. `port_to()` first validates every source and target, then copies (saving `.bak`). `run_build()` runs `cmake <options> ..` and `make <target> -jN` and streams the output.

### Worked example (Template 1, perm 12, otype 4, flag 1, order `PFOB`)

Bound = 32 − 17 = 15 bits, reserved 10, spare 5, so `T ∈ [1, 3]`. With `T = 2`: `B = 4`, 3 bits wasted.

| Field | Bits |
|-------|------|
| Bound | `[14:0]` (`BE[1:0]`, `B[5:2]`, `TE[7:6]`, `T[9:8]`, `L7[10]`, `IE[11]`, unused `[14:12]`) |
| Otype | `[18:15]` |
| Flag | `[19]` |
| Perm | `[31:20]` |

## Requirements

- Python 3.8+
- `tkinter` for the GUI (`sudo apt install python3-tk` on Debian/Ubuntu)
- `pillow` for the logo and theme (`pip install pillow`; the GUI also runs without it)
- `cmake`, `make` and a C++ toolchain, to build the VP

## Quick start (GUI)

```bash
git clone https://github.com/Thread-t/GenCHERI_Lib.git
cd GenCHERI_Lib
python3 GenCHeri_gui.py
```

1. **Generate headers**
   Choose the template, the bit widths (the allowed maximums update as you change them), the compressed-instruction option, optional user-defined perms / otypes / flags, and the field order. Pick a staging folder and press **Generate headers**.
2. **Port into riscv-vp and build**
   Select your riscv-vp checkout (default `~/Documents/riscv-vp`), choose a build mode and press **Port & Build** (or **Port only** to just copy).

### Where to keep this tool

Any location works; the GUI only needs the path of your riscv-vp checkout. A convenient place is inside the VP tree itself:

```
riscv-vp/vp/tools/GenCHERI_Lib/      <- this repository
```

and then, from there, `python3 GenCHeri_gui.py` with *riscv-vp folder* set to the checkout root (the folder that contains `vp/`).

### Build modes

| Button | CMake options | `make` target |
|--------|---------------|---------------|
| **TESTRIG** | `-DUSE_TESTRIG=ON -DUSE_RISCV_VP=ON -DTEMPLATE=<N>` | `riscv-vp` |
| **QEMU** | `-DUSE_TESTRIG=ON -DUSE_QEMU=ON -DTEMPLATE=<N>` | `qemu32-vp` |

`<N>` is the template of the last generation. Tick **Show all cmake arguments** to also pass the other mode explicitly as `OFF` (`-DUSE_QEMU=OFF` for TestRig, `-DUSE_RISCV_VP=OFF` for QEMU), which keeps stale values in `CMakeCache.txt` from leaking into a build. The exact command is shown before you run it.

### Where the files go

| File | Destination |
|------|-------------|
| `general.h` | `<vp>/vp/src/core/GenCHERI/` |
| `cheri_utils.h` | `<vp>/vp/src/core/GenCHERI/Template<N>/` |
| build | `<vp>/vp/build`: `cmake <options> ..` then `make <target> -jN` |

Last used folders, build mode and `-j` value are remembered in `~/.cheri_gui.json`.

## Command line

Run from the repository root:

```bash
# interactive prompts, headers written to ./out
python3 -m Backend.GenCHeri -d out

# choose the file names too
python3 -m Backend.GenCHeri -d out -o general.h -u cheri_utils.h

# port (and optionally build) without the GUI
python3 -m Backend.port_build out/general.h --dst ~/Documents/riscv-vp/vp/src/core/GenCHERI
python3 -m Backend.port_build out/cheri_utils.h --dst ~/Documents/riscv-vp/vp/src/core/GenCHERI/Template2 \
        --build-dir ~/Documents/riscv-vp/vp/build --cmake-arg=-DUSE_QEMU=ON -j8
```

## Project layout

```
GenCHERI_Lib/
├── GenCHeri_gui.py        # tkinter front end
├── gen_config.py          # limits, derived values, name checks, build_cfg() (shared by CLI and GUI)
├── Backend/
│   ├── GenCHeri.py        # command-line front end + generate_headers()
│   ├── gen_general.py     # general.h generation
│   ├── gen_utils.py       # cheri_utils.h generation (templates 1, 2, 3)
│   ├── helper.py          # terminal prompts, layout() / layout_gen()
│   └── port_build.py      # stage 2: copy headers into the VP tree, run cmake + make
├── generated/             # sample output
├── GenCHERI_logo.jpg      # logo used by the GUI and this README
├── LICENSE
└── README.md
```

Generation (stage 1) and porting/building (stage 2) are deliberately independent: `Backend/port_build.py` only needs file paths and uses the standard library only.

## Template cheat-sheet

| | Template 1 | Template 2 | Template 3 |
|---|---|---|---|
| Metadata width | 32 bits | 32 bits | sum of field storage sizes |
| `CAP_LEN` | 64 | 64 | 32 + metadata |
| Reserved bits in the bound | 10 (`BE2, TE2, L7, IE` + minimum `B`, `T`) | 11 (`BE3, TE3, IE` + minimum `B`, `T`) | none |
| Spare bits for perm/otype/flag | 8 | 7 | n/a |
| Perm range | 11 … 19 | 11 … 18 | 11 … 32 |
| Otype range | 2 … 10 − (p−11) | 2 … 9 − (p−11) | 2 … 32 |
| Flag range | 1 … 9 − (p−11) − (o−2) | 1 … 8 − (p−11) − (o−2) | 1 … 32 |
| Bound | `32 − (p+o+f)` bits | `32 − (p+o+f)` bits | 1–64 bits, rounded to 8/16/32/64 |
| `CHERI` type | `uint32_t` | `uint32_t` | `struct CHERI` |

For Templates 1/2 you also choose the T width: `T = 1 + x`, `B = T + 2` (i.e. `B = x + 3`), and any leftover spare bits are left unused. Inner bound layout, from the LSB:

- Template 1: `BE(2) | B | TE(2) | T | L7 | IE | wasted`
- Template 2: `BE(3) | B | TE(3) | T | IE | wasted`

## After the build: running CHERI-Zephyr samples

The QEMU build produces `qemu32-vp`. A CHERI-Zephyr sample is built for the purecap board and its `zephyr.elf` is run on that binary, for example:

```bash
cmake -GNinja -DBOARD=qemu_riscv32cheri_purecap <path-to>/samples/cheri/<sample>
ninja
<vp>/vp/build/bin/qemu32-vp ... build/zephyr/zephyr.elf     # exact VP command line depends on your setup
```

The samples are `buffer_overflow`, `k_heap_overflow`, `k_malloc_overflow`, `mem_blocks_overflow`, `mem_slab_overflow`, `stack_overflow`, `sys_heap_overflow` and `sys_multi_heap_overflow`. A sample that is meant to demonstrate a bounds violation should end in a CHERI fault.

## Known limitations

- `run_build()` contains the step `["rm", "-rf", "*"]`. It is started without a shell, so `*` is not expanded and the build folder is **not** cleaned. Delete `vp/build/CMakeCache.txt` (or tick *Show all cmake arguments*) if old settings stick.
- Template 3 slots are storage-aligned, so unused bits inside a slot are padding.
- `generated/` holds one example output only; regenerate it rather than relying on it.
- There is no automated test suite in the repository yet.

## Troubleshooting

- **No logo / default theme**: install Pillow (`pip install pillow`) and keep `GenCHERI_logo.jpg` next to `GenCHeri_gui.py`.
- **`No module named tkinter`**: install `python3-tk`. With conda, `conda install tk`.
- **`cmake`/`make` not found**: install them and make sure they are on your `PATH`.
- **Port & Build says the VP folder is wrong**: select the riscv-vp checkout itself (the folder that contains `vp/`).
- **A name is refused while typing**: it is a duplicate (case-insensitive) of another user name, or a built-in such as `Sealed`; the red message under the name boxes says which.
- **Old build settings seem to stick**: delete `vp/build/CMakeCache.txt` or tick *Show all cmake arguments*.

## License

See [LICENSE](LICENSE).
