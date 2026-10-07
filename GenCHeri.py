#!/usr/bin/env python3
"""Generate CHERI headers (general.h, cheri_utils.h) from terminal input.

Files:
    GenCHeri.py   - this file: user prompts, limits, orchestration
    gen_general.py - general.h generation
    gen_utils.py   - cheri_utils.h generation

Usage:
    python3 GenCHeri.py                                  # interactive prompts (asks for the output folder)
    python3 GenCHeri.py -d ~/proj/include                # write both headers into this folder
    python3 GenCHeri.py -d out -o general.h -u cheri_utils.h   # also choose the file names
"""
import argparse
import os
# import re
import sys

from gen_general import OTYPES, FLAGS, FIELD_NAMES, BOUND_RESERVED, generate, type_bits
from gen_utils import *
from helper import *

#Sayak: Limit macros
PERM_MIN, OTYPE_MIN, FLAG_MIN, BOUND_MIN = 11, 2, 1, 10  # lower limits only (no upper limit)
T3_BOUND_MAX = 64  # template 3: fixed bound width
T12_META_BITS = 32  # templates 1/2: fixed metadata width
T3_FIELD_MAX = 32 # Template 3 perms, otype and flag bits max width
# Templates 1/2: number of extra bits (slack) that perm/otype/flag may consume above
# their minimums. Each field's max depends on what the previous fields already used:
#   perm  : PERM_MIN  <= x <= PERM_MIN  + S
#   otype : OTYPE_MIN <= y <= OTYPE_MIN + S - (x - PERM_MIN)
#   flag  : FLAG_MIN  <= z <= FLAG_MIN  + S - (x - PERM_MIN) - (y - OTYPE_MIN)
T12_SLACK = {1: 8, 2: 7}  #Sayak: Template 1 has 7 bits of slack, Template 2 has 6 bits of slack



#Sayak: Main function to orchestrate the generation of general.h and cheri_utils.h for all three templates
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-d", "--outdir", default=None,
                    help="folder for the generated files (created if missing); asked interactively if omitted")
    ap.add_argument("-o", "--output", default="general.h", help="file name of general.h")
    ap.add_argument("-u", "--utils", default="cheri_utils.h", help="file name of cheri_utils.h")
    args = ap.parse_args()

    # Check a folder given on the command line up front, before any prompts
    outdir = None
    if args.outdir:
        outdir, err = prepare_dir(args.outdir)
        if err:
            sys.exit(f"Cannot use output directory '{outdir}': {err}")

    print("Which template do you want to use?  1 (Spandan) / 2 (Sail) / 3 (General)")
    template = ask_int("Template", 1, 3)

    # Spandan: BOUND_MIN depends on the template
    if template == 1: BOUND_MIN = 10
    elif template == 2: BOUND_MIN = 11
    else: BOUND_MIN = 0

    #addr_w = ask_int("Address bits", 1, 64, 32)
    compressed = ask_yes_no("Is compressed instruction on?", "n")

    if template != 3:
        print(f"Template {template} requires minimum {PERM_MIN} Permission bits, {OTYPE_MIN} Otype bits,", end = " ")
        print(f"{FLAG_MIN} Flag bits and {BOUND_MIN} Bounds bits,", end = " ")
        print(f"totalling {PERM_MIN + OTYPE_MIN + FLAG_MIN + BOUND_MIN} bits.")
        print(f"This leaves {T12_META_BITS - (PERM_MIN + OTYPE_MIN + FLAG_MIN + BOUND_MIN)} spare bits", end = " ")
        print(f"for Template {template}, which can be distributed between the fields.")

    if template == 3:
        # lower limits only; bound fixed at 64 bits
        p = ask_int(f"Perm bits (min {PERM_MIN})", PERM_MIN, T3_FIELD_MAX, 12) #Sayak: Upper limit for 32 bits
        o = ask_int(f"Otype bits (min {OTYPE_MIN})", OTYPE_MIN, T3_FIELD_MAX, 3)
        f = ask_int(f"Flag bits (min {FLAG_MIN})", FLAG_MIN, T3_FIELD_MAX, 1)
        #Sayak: Ask user for the bit length of bound
        raw_b = ask_int(f"Bound bits (0-{T3_BOUND_MAX}, rounded up to 8/16/32/64)", 0, T3_BOUND_MAX, T3_BOUND_MAX)
        bound_w = round_bound(raw_b)
        if bound_w != raw_b:
            print(f"  -> bound bits rounded up to {bound_w}")
        sizes = [type_bits(w) for w in (p, o, f, bound_w)]
        meta_w = sum(sizes)
        print(f"  -> bound = {bound_w} bits; storage PERM {sizes[0]} + OTYPE {sizes[1]} + FLAG {sizes[2]} + BOUND {sizes[3]}")
    else:
        # Templates 1/2: dynamic max limits, each depends on the earlier choices
        # Sayak : Max possible number of slack bits for Template 1--> 7 and Template 2 --> 6
        s = T12_SLACK[template]
        p = ask_limited("Perm", PERM_MIN, PERM_MIN + s, 12)
        o = ask_limited("Otype", OTYPE_MIN, OTYPE_MIN + s - (p - PERM_MIN), 3)
        f = ask_limited("Flag", FLAG_MIN, FLAG_MIN + s - (p - PERM_MIN) - (o - OTYPE_MIN), 1)

        bound_w = T12_META_BITS - (p + o + f)   # Sayak: whatever is left of 32
        meta_w = T12_META_BITS                  # templates 1/2: constant 32
        print(f"  -> maximum bounds bits = {bound_w} bits")
    assert meta_w % 8 == 0, "total metadata width must be divisible by 8"
    print(f"  -> total metadata = {meta_w} bits")
    # meta_w = p + o + f + bound_w
    # print(f"  -> bound = {bound_w} bits, total metadata = {meta_w} bits")

    # Templates 1/2: split the spare bits equally between T and B.
    # T = 1 + x, B = 3 + x, 2*x <= spare  ->  x <= floor(spare / 2)
    x = None

    if template in (1, 2):
        spare = bound_w - BOUND_RESERVED[template]
        #Sayak: T can be at least 1 bit and at most 1 + spare//2 bits
        t_max = 1 + spare // 2
        
        # Print calculations to the user before prompting for T
        print(f"  -> {BOUND_RESERVED[template]} bound bits assigned according to template.")
        print(f"  -> Spare bits left for T and B allocation: {spare} bits")
        print(f"  -> You can select 1 to {t_max} bits for T.")
        print(f"  -> That +2 bits will be automatically assigned to B.")

        t_bits = ask_limited("T", 1, t_max, t_max)
        b_fld = t_bits + 2    # B = T + 2
                               
        print(f"  -> T = {t_bits} bits, so B = {b_fld} bits")
        leftover = spare - 2 * (t_bits - 1)
        # extra = leftover // 2                     # split the leftover equally between T and B
        # t_bits += extra
        # b_fld += extra
        # wasted = leftover - 2 * extra             # 0 or 1 bit goes to waste
        x = t_bits - 1                            # keeps T = 1 + x, B = 3 + x for utils_positions()
        #print(f"  -> Extra {leftover} bits got distributed between T and B (+{extra} each, {wasted} wasted)")

        print(f"  -> Final: T = {t_bits} bits, B = {b_fld} bits ({leftover} bits wasted)")

    # user-defined perms are appended after the 11 hardware perms
    max_uperm = p - HW_PERM_COUNT
    nperm = 0  # default when the prompt is skipped
    if (p > PERM_MIN): #Sayak : Give option only when user defined perm is there
        nperm = ask_int(f"Number of user-defined perms (<={max_uperm})", 0, max_uperm, 0)
    perm_names_ip = ask_names(nperm, "perm", set())
    perm_names = [nm.upper() for nm in perm_names_ip]  # all perms are upper-case

    # Sayak: Unsealed, Sealed, Reserved + n  and (user types must fit in 2^o values)
    max_user = (1 << o) - 3  #basically (2^0 -3)
    notype = 0  # default when the prompt is skipped
    if (o > OTYPE_MIN): #Sayak : Give option only when user defined otype is there
        notype = ask_int(f"Number of user-defined otypes (<={max_user})", 0, max_user, 0)
    otype_names = ask_names(notype, "otype", set(OTYPES))

    max_flag = f - FLAG_MIN
    nflag = 0 # default when the prompt is skipped
    if (f > FLAG_MIN): #Sayak : Give option only when user defined flag is there
        nflag = ask_int(f"Number of user-defined flags (<={max_flag})", 0, max_flag, 0)
    flag_names_ip = ask_names(nflag, "flag", set(FLAGS))
    flag_names = [nm.upper() for nm in flag_names_ip]  # all flags are upper-case

    order = ask_order()
    widths = {"P": p, "O": o, "F": f, "B": bound_w}
    if (template == 3):
        gen_widths = {"P": type_bits(p), "O": type_bits(o), "F": type_bits(f), "B": type_bits(bound_w)}
        pos = layout_gen(order, widths, gen_widths)
    else:
        pos = layout(order, widths)

    #Sayak : Add general_name to the cfg dictionary to be used in utils.h generation for template 3
    cfg = dict(x=x, template=template, meta_w=meta_w, addr_w= 32, compressed=compressed,
               widths=widths, order=order, pos=pos,
               perm_names=perm_names, otype_names=otype_names, flag_names=flag_names, 
               general_name= os.path.basename(args.output))
    if outdir is None:
        outdir = ask_outdir()
    general_path = os.path.join(outdir, args.output)   # an absolute -o path overrides the folder
    utils_path = os.path.join(outdir, args.utils)

    with open(general_path, "w") as fh:
        fh.write(generate(cfg))
    print(f"Wrote {general_path}  (bound width = {widths['B']})")
    utils = generate_utils(cfg)
    # if utils is None:
    #     print("cheri_utils.h: not generated for template 3 yet")
    # else:
    with open(utils_path, "w") as fh:
        fh.write(utils)
    print(f"Wrote {utils_path}")
    for k in order:
        print(f"  {FIELD_NAMES[k]:5s} [{pos[k][1]}:{pos[k][0]}]")

if __name__ == "__main__":
    sys.exit(main())