"""
Called from GenCHeri.py: Helper Functions supplier
"""

import re
import os
from Backend.gen_general import HW_PERMS


DEFAULT_ORDER = "PFOB"  # written MSB -> LSB (matches the dummy header)
HW_PERM_COUNT = len(HW_PERMS)  # 11
RESERVED_NAMES = set(HW_PERMS) #| {"Unsealed", "Sealed", "Reserved", "CAP_MODE"}

UTILS_HEAD = r"""#include <cstdint>
#include <cassert>
#include "instr.h"


#ifndef _CHERI_UTILS
#define _CHERI_UTILS

"""

UTILS_DEFS_T1 = r"""#define CAP_IE @IE@
#define CAP_L7 @L7@
#define CAP_TE_TOP @TE_TOP@
#define CAP_TE_BOT @TE_BOT@
#define CAP_T_TOP @T_TOP@
#define CAP_T_BOT @T_BOT@
#define CAP_BE_TOP @BE_TOP@
#define CAP_BE_BOT @BE_BOT@
#define CAP_B_TOP @B_TOP@
#define CAP_B_BOT @B_BOT@
#define R_TOP CAP_B_TOP
#define R_BOT (R_TOP - 2)
#define REG_FIELD_LEN 5 // Register field in an instruction

#define E_MAX (ADDR_BITS - (CAP_B_TOP - CAP_B_BOT) - (CAP_BE_TOP - CAP_BE_BOT))

#define NULL_CAP (0b0 << CAP_PERM_BOT) | (0b0 << CAP_FLAG_BOT) | (Unsealed << CAP_OTYPE_BOT) | (0b1 << CAP_IE) | \
				 (0b1 << CAP_L7) | (0b0 << CAP_T_BOT) | (0b10 << CAP_TE_BOT) | (0b0 << CAP_B_BOT) | (0b10 << CAP_BE_BOT)
#define INF_CAP (@PERM_ONES@ << CAP_PERM_BOT) | (0b0 << CAP_FLAG_BOT) | (Unsealed << CAP_OTYPE_BOT) | \
				(0b1 << CAP_IE) | (0b1 << CAP_L7) | (0b0 << CAP_T_BOT) | (0b10 << CAP_TE_BOT) | (0b0 << CAP_B_BOT) | (0b10 << CAP_BE_BOT)



"""

UTILS_DEFS_T2 = r"""#define CAP_IE @IE@
//#define CAP_L7 @L7@
#define CAP_TE_TOP @TE_TOP@
#define CAP_TE_BOT @TE_BOT@
#define CAP_T_TOP @T_TOP@
#define CAP_T_BOT @T_BOT@
#define CAP_BE_TOP @BE_TOP@
#define CAP_BE_BOT @BE_BOT@
#define CAP_B_TOP @B_TOP@
#define CAP_B_BOT @B_BOT@
#define R_TOP CAP_B_TOP
#define R_BOT (R_TOP - 2)
#define REG_FIELD_LEN 5 // Register field in an instruction

#define E_MAX (ADDR_BITS - (CAP_B_TOP - CAP_B_BOT) - (CAP_BE_TOP - CAP_BE_BOT))

#define NULL_CAP (0b0 << CAP_PERM_BOT) | (0b0 << CAP_FLAG_BOT) | (Unsealed << CAP_OTYPE_BOT) | (0b1 << CAP_IE) | \
				 (0b0 << CAP_T_BOT) | (0b11 << CAP_TE_BOT) | (0b0 << CAP_B_BOT) | (0b10 << CAP_BE_BOT)
#define INF_CAP (@PERM_ONES@ << CAP_PERM_BOT) | (0b0 << CAP_FLAG_BOT) | (Unsealed << CAP_OTYPE_BOT) | \
				(0b1 << CAP_IE) | (0b0 << CAP_T_BOT) | (0b11 << CAP_TE_BOT) | (0b0 << CAP_B_BOT) | (0b10 << CAP_BE_BOT)



"""

UTILS_NS_T1 = r"""namespace cheri32 {

//Find the base address of the given capability
uint32_t get_base(uint32_t addr, CHERI metadata);

//Find the top address of the given capability. Note that,
//top can be a 33 bit value at max, hence represented as 64 bit signed integer
int64_t get_top(uint32_t addr, CHERI metadata);

//Does not exactly set the address. Mainly does the fast rep check
//If setoffset is true, rs2 is added to cs1 base, else to cs1 address
bool set_offset(Capability cs1, int64_t imm, bool setoffset);

//To check if address is within bounds of the capability
bool cap_inbounds(Capability cs);

"""

UTILS_NS_T2 = r"""namespace cheri32 {

//Find the base address of the given capability.
uint32_t get_base(uint32_t addr, CHERI metadata);

//Find the top address of the given capability. Note that,
//top can be a 33 bit value at max, hence represented as 64 bit signed integer.
int64_t get_top(uint32_t addr, CHERI metadata);

//Does not exactly set the address. Mainly does the fast representability
//check to find whether the offset rs2 will take the address out of the
//representable range.
//If setoffset is true, rs2 is added to cs1 base, else to cs1 address.
bool set_offset(Capability cs1, int64_t imm, bool setoffset);

//To check if address is within bounds of the capability.
bool cap_inbounds(Capability cs);

"""

UTILS_NS_COMMON = r"""//Create a new capability with base as cs.addr and length as len.
//In case base cannot be set exactly to cs.addr, it is reduced to 
//the next representable base. 
//In case top cannot be exactly set to (cs.addr + len), it is increased
//to the next representable top.
//SetBound_Ret.cd contains the final capability.
//SetBound_Ret.exact is true/false depending on the exact/inexact 
//representation of the wanted capability.
//SetBound_Ret.newlen provides the actual length of the new capability.
//SetBounds_Ret.baseMask provides the mask required to create the new
//base from the desired one (cs.addr).
//If SetBound_flag.len is true then only SetBound_Ret.newlen is accessed.
//If SetBound_flag.mask is true then only SetBound_Ret.baseMask is accessed.
SetBound_Ret set_bounds(Capability cs, uint64_t len, SetBound_flag choice);

}

#endif
"""

# def utils_positions(cfg):
#     """Absolute bit positions of the compressed-bound sub-fields (templates 1/2).
#     From the bottom of the BOUND field (l) upward:
#       T1: BE(2) | B(x+3) | TE(2) | T(x+1) | L7(1) | IE(1) | [wasted spare bit(s)]
#       T2: BE(3) | B(x+3) | TE(3) | T(x+1) | IE(1)         | [wasted spare bit(s)]
#     x = (T bits chosen by user) - 1, with 2*x <= spare bits."""
#     l, x = cfg["pos"]["B"][0], cfg["x"]
#     w = 2 if cfg["template"] == 1 else 3        # BE and TE width
#     r = {}
#     r["BE_BOT"] = l;                 r["BE_TOP"] = l + w - 1
#     r["B_BOT"] = l + w;              r["B_TOP"] = r["B_BOT"] + (x + 3) - 1
#     r["TE_BOT"] = r["B_TOP"] + 1;    r["TE_TOP"] = r["TE_BOT"] + w - 1
#     r["T_BOT"] = r["TE_TOP"] + 1;    r["T_TOP"] = r["T_BOT"] + (x + 1) - 1
#     if cfg["template"] == 1:
#         r["L7"] = r["T_TOP"] + 1
#         r["IE"] = r["L7"] + 1
#     else:
#         r["IE"] = r["T_TOP"] + 1
#         r["L7"] = r["IE"]                        # only used in the commented-out macro
#     return r


# def generate_utils(cfg):
#     """cheri_utils.h text for template 1/2/3; """
#     if cfg["template"] == 3:
#         return None
#     defs = UTILS_DEFS_T1 if cfg["template"] == 1 else UTILS_DEFS_T2
#     ns = UTILS_NS_T1 if cfg["template"] == 1 else UTILS_NS_T2
#     for k, v in utils_positions(cfg).items():
#         defs = defs.replace(f"@{k}@", str(v))
#     defs = defs.replace("@PERM_ONES@", "0b" + "1" * cfg["widths"]["P"])  # all perm bits set
#     return UTILS_HEAD + defs + ns + UTILS_NS_COMMON

#Sayak: function for checking input from user
def ask_int(prompt, lo=None, hi=None, default=None):
    while True:
        s = input(f"{prompt}" + (f" [{default}]" if default is not None else "") + ": ").strip()
        if not s and default is not None:
            return default
        try:
            v = int(s)
        except ValueError:
            print("  -> enter an integer")
            continue
        if (lo is not None and v < lo) or (hi is not None and v > hi):
            print(f"  -> must be between {lo} and {hi}")
            continue
        return v


def ask_yes_no(prompt, default="n"):
    while True:
        s = input(f"{prompt} (y/n) [{default}]: ").strip().lower() or default
        if s in ("y", "yes"):
            return True
        if s in ("n", "no"):
            return False
        print("  -> answer y or n")


#Sayak: helper function for Template 3 //Mich
def round_bound(w):
    """Template 3: round the requested bound width up to 8/16/32/64 bits."""
    for cand in (8, 16, 32, 64):
        if w <= cand:
            return cand


def ask_order():
    while True:
        s = input(f"Field order MSB->LSB using P,O,F,B [{DEFAULT_ORDER}]: ").strip().upper()
        s = s.replace("|", "").replace(" ", "") or DEFAULT_ORDER
        if sorted(s) == sorted("POFB"):
            return s
        print("  -> use each of P, O, F, B exactly once (e.g. PFOB or OPFB)")

#Sayak: Helper function added to get the user defined perms and otypes //Mich
def ask_names(n, label, taken):
    names = []
    names_upper = []
    taken_upper = [nm.upper() for nm in taken]
    for i in range(n):
        while True:
            nm = input(f"  Name of user-defined {label} #{i + 1}: ").strip()
            nm_upper = nm.upper()
            if re.fullmatch(r"[A-Za-z_]\w*", nm) and nm_upper not in RESERVED_NAMES \
                    and nm_upper not in taken_upper and nm_upper not in names_upper:
                names.append(nm)
                names_upper.append(nm_upper)
                break
            print("  -> must be a unique valid C identifier (not already used)")
    return names


def layout(order, widths):
    """order is MSB->LSB; returns {field: (bot, top)} with bit 0 = LSB."""
    pos, bit = {}, 0
    for f in reversed(order):
        pos[f] = (bit, bit + widths[f] - 1)
        bit += widths[f]
    return pos


def layout_gen(order, widths, gen_widths):
    """order is MSB->LSB; returns {field: (bot, top)} with bit 0 = LSB."""
    pos, bit = {}, 0
    for f in reversed(order):
        pos[f] = (bit, bit + widths[f] - 1)
        bit += gen_widths[f]
    return pos


def ask_limited(label, lo, hi, default):
    """Prompt within [lo, hi]; if no choice is left (lo == hi) assign the minimum automatically."""
    if lo == hi:
        print(f"  -> {label} bits fixed to {lo} (no bits left to choose)")
        return lo
    return ask_int(f"{label} bits ({lo}-{hi})", lo, hi, min(default, hi))


#Sayak: output folder handling
def prepare_dir(path):
    """Expand ~ and relative paths and create the folder if needed. Returns (abs_path, error_or_None)."""
    d = os.path.abspath(os.path.expanduser(path))
    try:
        os.makedirs(d, exist_ok=True)
    except OSError as e:
        return d, e.strerror or str(e)
    if not os.access(d, os.W_OK):
        return d, "directory is not writable"
    return d, None


def ask_outdir(default="."):
    while True:
        s = input(f"Output directory for the generated headers (created if missing) [{default}]: ").strip() or default
        d, err = prepare_dir(s)
        if err is None:
            return d
        print(f"  -> cannot use '{d}': {err}")

#Sayak: function to write the generated files to the specific directory
def port_headers(outdir, file_map):
    """
    Port (write) in-memory generated files to a target directory.
    """
    target_dir, err = prepare_dir(outdir)
    if err:
        return False, f"Failed to prepare directory '{target_dir}': {err}"
    # Write each file to the target directory
    written_paths = []
    try:
        for filename, content in file_map.items():
            file_path = os.path.join(target_dir, filename)
            with open(file_path, "w") as fh:
                fh.write(content)
            written_paths.append(file_path)
        return True, written_paths
    except Exception as e:
        return False, f"Error writing files: {str(e)}"
