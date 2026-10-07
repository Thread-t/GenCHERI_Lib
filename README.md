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
| `general.h` | `CAP_*_TOP/BOT` bit-position macros, permission and otype enums, `PERM`/`OTYPE`/`FLAG`/`CHERI` typedefs, `MIN_INSTR_BYTES` |
| `cheri_utils.h` | Template-specific macros (`CAP_IE`, `CAP_TE_*`, `CAP_T_*`, `CAP_BE_*`, `CAP_B_*`), `NULL_CAP`, `INF_CAP` and the `cheri32` namespace declarations |

It then copies them into the right folders of your riscv-vp checkout (replacing the old ones) and runs `cmake` and `make` for you.

## Features

- **Three capability templates**
  - **Template 1 / 2**: fixed 32-bit metadata. The limits of the permission, otype and flag widths depend on each other, and the remaining bits become the bound.
  - **Template 3**: variable layout (`struct CHERI`). Perm/otype/flag up to 32 bits each, bound up to 64 bits (rounded up to 8/16/32/64).
- **User-defined permissions and otypes**, appended after the 12 hardware permissions and after `Unsealed`/`Sealed`/`Reserved`.
- **Any field order**: pick one of the 24 orderings of Perm / Otype / Flag / Bound (MSB → LSB).
- **Smallest storage type** (`uint8_t` … `uint64_t`) chosen automatically for every field.
- **Compressed-instruction switch** (`MIN_INSTR_BYTES` 2 or 4).
- **Tkinter GUI** with live validation, a logo-themed look, a CMake options dropdown and a build log.
- **Command-line mode** with the same rules (shared in `gen_config.py`).
- **Safe porting**: everything is checked before the first copy, and replaced files can be kept as `.bak`.

## Requirements

- Python 3.8+
- `tkinter` for the GUI (`sudo apt install python3-tk` on Debian/Ubuntu)
- `pillow` for the logo (`pip install pillow`; the GUI also runs without it)
- `cmake`, `make` and a C++ toolchain, to build the VP

## Quick start (GUI)

```bash
git clone <this-repo-url>
cd GenCHERI_Lib
python3 GenCHeri_gui.py
```

1. **Generate headers**
   Choose the template, bit widths, optional user-defined perms/otypes and the field order, pick a staging folder and press **Generate headers**.
2. **Port into riscv-vp and build**
   Select the VP folder: the `vp` directory of your riscv-vp checkout (the one that contains `CMakeLists.txt`, `src/` and `build/`), for example `~/Documents/riscv-vp/vp`.
   Tick the CMake options you need and press **Port & Build**.

Porting goes to:

| File | Destination |
|------|-------------|
| `general.h` | `<vp>/src/core/GenCHERI/` |
| `cheri_utils.h` | `<vp>/src/core/GenCHERI/Template<N>/` |
| build | `<vp>/build`: `cmake -D<option>=ON/OFF … ..` then `make -jN` |

The CMake options are read from `<vp>/CMakeLists.txt`. Every option is passed explicitly as `ON` or `OFF`, so stale values in `CMakeCache.txt` can't leak into a build. The exact command is shown before you run it.

## Command line

```bash
# interactive prompts, headers written to ./out
python3 GenCHeri.py -d out

# choose the file names too
python3 GenCHeri.py -d out -o general.h -u cheri_utils.h

# port and build without the GUI
python3 port_build.py out/general.h --dst ~/Documents/riscv-vp/vp/src/core/GenCHERI
python3 port_build.py out/cheri_utils.h --dst ~/Documents/riscv-vp/vp/src/core/GenCHERI/Template2 \
        --build-dir ~/Documents/riscv-vp/vp/build --cmake-arg=-DUSE_QEMU=ON -j8
```

## Project layout

```
GenCHERI_Lib/
├── GenCHeri_gui.py    # tkinter front end
├── GenCHeri.py        # command-line front end + generate_headers()
├── gen_config.py      # limits, derived values and validation (shared by CLI and GUI)
├── gen_general.py     # general.h generation
├── gen_utils.py       # cheri_utils.h generation (templates 1, 2, 3)
├── helper.py          # terminal prompt helpers
├── port_build.py      # stage 2: copy headers into the VP tree, run cmake + make
├── GenCHERI_logo.jpg  # logo used by the GUI and this README
├── LICENSE
└── README.md
```

Generation (stage 1) and porting/building (stage 2) are deliberately independent: `port_build.py` only needs file paths and uses the standard library only.

## Template cheat-sheet

| | Template 1 | Template 2 | Template 3 |
|---|---|---|---|
| Metadata width | 32 bits | 32 bits | sum of field storage sizes |
| Extra bound-region bits | 10 reserved (`BE2, TE2, L7, IE`) | 11 reserved (`BE3, TE3, IE`) | none |
| Spare bits for perm/otype/flag | 8 | 7 | n/a |
| Perm / otype / flag range | dependent limits | dependent limits | up to 32 bits each |
| Bound | `32 − (p+o+f)` bits | `32 − (p+o+f)` bits | 1–64 bits, rounded to 8/16/32/64 |
| `CHERI` type | `uint32_t` | `uint32_t` | `struct CHERI` |

For Templates 1/2 you also choose the T width: `T = 1 + x`, `B = T + 2`, and any leftover spare bits are left unused.

## Troubleshooting

- **No logo / default blue theme**: install Pillow (`pip install pillow`) and keep `GenCHERI_logo.jpg` next to `GenCHeri_gui.py`.
- **`No module named tkinter`**: install `python3-tk`. With conda, `conda install tk`.
- **`cmake`/`make` not found**: install them and make sure they are on your `PATH`.
- **Options list shows a built-in default**: the VP folder is wrong or `CMakeLists.txt` has no `option(...)` lines; check the path.

## License

See [LICENSE](LICENSE).
