"""cheri_utils.h generation (templates 1 and 2).

Called from GenCHeri.py:  generate_utils(cfg) -> text of cheri_utils.h (None for template 3)
"""

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
#Sayak: Update for the generation of the utils.h in case of template 3
UTILS_HEAD_T3 = r"""#include <cstdint>
#include <cassert>
#include "@GENERAL@"
#include "instr.h"


#ifndef _CHERI_UTILS
#define _CHERI_UTILS

"""

UTILS_DEFS_T3 = r"""inline CHERI NULL_CAP = {0, Unsealed, 0, @BOUNDS_INIT@};

inline CHERI INF_CAP = {(BIT_SLICE((~0), (CAP_PERM_TOP - CAP_PERM_BOT), 0)), Unsealed, 0, @BOUNDS_INIT@};

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

# Sayak < Function for MACRO calculation in utils.h>
def utils_positions(cfg):
    """Absolute bit positions of the compressed-bound sub-fields (templates 1/2).
    From the bottom of the BOUND field (l) upward:
      T1: BE(2) | B(x+3) | TE(2) | T(x+1) | L7(1) | IE(1) | [wasted spare bit(s)]
      T2: BE(3) | B(x+3) | TE(3) | T(x+1) | IE(1)         | [wasted spare bit(s)]
    x = (T bits chosen by user) - 1, with 2*x <= spare bits."""
    l, x = cfg["pos"]["B"][0], cfg["x"]
    # Based on template w will be either 2 or 3
    w = 2 if cfg["template"] == 1 else 3        # BE and TE width
    r = {}
    r["BE_BOT"] = l;                 r["BE_TOP"] = l + w - 1
    r["B_BOT"] = l + w;              r["B_TOP"] = r["B_BOT"] + (x + 3) - 1
    r["TE_BOT"] = r["B_TOP"] + 1;    r["TE_TOP"] = r["TE_BOT"] + w - 1
    r["T_BOT"] = r["TE_TOP"] + 1;    r["T_TOP"] = r["T_BOT"] + (x + 1) - 1
    
    # Sayak: L7 will be there in case of template 1 and the l7 macro will be commented out in case of template 2,3
    if cfg["template"] == 1:
        r["L7"] = r["T_TOP"] + 1
        r["IE"] = r["L7"] + 1
    else:
        r["IE"] = r["T_TOP"] + 1
        r["L7"] = r["IE"]                        # only used in the commented-out macro
    return r


# def generate_utils(cfg):
#     """cheri_utils.h text for template 1/2; None for template 3 (not defined yet)."""
#     if cfg["template"] == 3:
#         return None
#     defs = UTILS_DEFS_T1 if cfg["template"] == 1 else UTILS_DEFS_T2
#     ns = UTILS_NS_T1 if cfg["template"] == 1 else UTILS_NS_T2
#     for k, v in utils_positions(cfg).items():
#         defs = defs.replace(f"@{k}@", str(v))
#     defs = defs.replace("@PERM_ONES@", "0b" + "1" * cfg["widths"]["P"])  # all perm bits set
#     return UTILS_HEAD + defs + ns + UTILS_NS_COMMON

#Sayak : Update for the generation of the utils.h in case of template 3
def bounds_init(bound_bits):
    """Template 3 NULL_CAP/INF_CAP bounds constant: upper half all ones, lower half zero
    (64-bit bound -> 0xFFFFFFFF00000000, 32 -> 0xFFFF0000, 16 -> 0xFF00, 8 -> 0xF0)."""
    half = bound_bits // 2
    return "0x" + format(((1 << half) - 1) << half, f"0{bound_bits // 4}X")
 
 # Sayak: Main function to orchestrate the generation of cheri_utils.h for all three templates
def generate_utils(cfg):
    """cheri_utils.h text for templates 1, 2 and 3."""
    # Sayak: Update for the generation of the utils.h in case of template 3
    if cfg["template"] == 3:
        head = UTILS_HEAD_T3.replace("@GENERAL@", cfg.get("general_name", "general.h"))
        defs = UTILS_DEFS_T3.replace("@BOUNDS_INIT@", bounds_init(cfg["widths"]["B"]))
        return head + defs + UTILS_NS_T2 + UTILS_NS_COMMON
    # Sayak: Logic for template 1 and 2 remains the same
    defs = UTILS_DEFS_T1 if cfg["template"] == 1 else UTILS_DEFS_T2
    ns = UTILS_NS_T1 if cfg["template"] == 1 else UTILS_NS_T2
    for k, v in utils_positions(cfg).items():
        defs = defs.replace(f"@{k}@", str(v))
    defs = defs.replace("@PERM_ONES@", "0b" + "1" * cfg["widths"]["P"])  # all perm bits set
    return UTILS_HEAD + defs + ns + UTILS_NS_COMMON