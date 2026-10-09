"""Pure logic of the CHERI header generator: limits, derived values and config validation.

No input() / print() in here, so the terminal prompts (GenCHeri.py) and the tkinter GUI
(GenCHeri_gui.py) share exactly the same rules.
"""
import re
from itertools import permutations

from Backend.gen_general import HW_PERMS, BOUND_RESERVED, type_bits
from Backend.helper import layout_gen

#Sayak: Limit macros (moved here from GenCHeri.py so the terminal version and the GUI use the same numbers)
PERM_MIN, OTYPE_MIN, FLAG_MIN = 11, 2, 1  # lower limits
T3_BOUND_MAX = 64   # template 3: max bound width
T12_META_BITS = 32  # templates 1/2: fixed metadata width
T3_FIELD_MAX = 32   # Template 3 perms, otype and flag bits max width
# Templates 1/2: number of extra bits (slack) that perm/otype/flag may consume above
# their minimums. Each field's max depends on what the previous fields already used:
#   perm  : PERM_MIN  <= x <= PERM_MIN  + S
#   otype : OTYPE_MIN <= y <= OTYPE_MIN + S - (x - PERM_MIN)
#   flag  : FLAG_MIN  <= z <= FLAG_MIN  + S - (x - PERM_MIN) - (y - OTYPE_MIN)
T12_SLACK = {1: 8, 2: 7}  #Sayak: Template 1 has 8 bits of slack, Template 2 has 7 bits of slack

FIELD_LABEL = {"P": "Perm", "O": "Otype", "F": "Flag", "B": "Bound"}
DEFAULT_ORDER = "PFOB"  # written MSB -> LSB (matches the dummy header)
ORDERS = ["".join(p) for p in permutations("POFB")]   # all 24 possible field orders
HW_PERM_COUNT = len(HW_PERMS)  # 12

# Sayak: reserved names for the permission fields --> Check for duplicates across all groups (perm, otype, flag) and reserved names
RESERVED_NAMES = set(HW_PERMS) | {"UNSEALED", "SEALED", "RESERVED", "CAP_MODE"}


# ---- allowed ranges (lo, hi) --------------------------------------------------------------
def perm_range(template):
    if template == 3:
        return PERM_MIN, T3_FIELD_MAX
    return PERM_MIN, PERM_MIN + T12_SLACK[template]


def otype_range(template, p):
    if template == 3:
        return OTYPE_MIN, T3_FIELD_MAX
    return OTYPE_MIN, OTYPE_MIN + T12_SLACK[template] - (p - PERM_MIN)


def flag_range(template, p, o):
    if template == 3:
        return FLAG_MIN, T3_FIELD_MAX
    return FLAG_MIN, FLAG_MIN + T12_SLACK[template] - (p - PERM_MIN) - (o - OTYPE_MIN)


# ---- derived values -------------------------------------------------------------------------
#Sayak: helper function for Template 3 //Mich
def round_bound(w):
    """Template 3: round the requested bound width up to 8/16/32/64 bits."""
    for cand in (8, 16, 32, 64):
        if w <= cand:
            return cand


def bound_and_meta(template, p, o, f, bound_raw=None):
    """Returns (bound_w, meta_w, sizes). sizes = storage bits of P/O/F/B for template 3, else None."""
    if template == 3:
        bound_w = round_bound(bound_raw)
        sizes = [type_bits(w) for w in (p, o, f, bound_w)]
        return bound_w, sum(sizes), sizes          # template 3: sum of the storage sizes
    return T12_META_BITS - (p + o + f), T12_META_BITS, None   # Sayak: whatever is left of 32; total is constant 32


def t_range(template, bound_w):
    """Templates 1/2: returns (spare, t_max). T can be at least 1 bit and at most 1 + spare//2 bits."""
    spare = bound_w - BOUND_RESERVED[template]
    return spare, 1 + spare // 2


def t_split(t_bits, spare):
    """Templates 1/2: T = 1 + x, B = 3 + x. Returns (x, b_bits, leftover spare bits)."""
    x = t_bits - 1
    return x, t_bits + 2, spare - 2 * x


def bound_layout(template, bound_w, t_bits=None):
    """Inner division of the BOUND field as [(name, width)], LSB first.
    T1: BE(2) B TE(2) T L7 IE | wasted      T2: BE(3) B TE(3) T IE | wasted      T3: one plain field."""
    if template == 3:
        return [("Bound", bound_w)]
    spare, _ = t_range(template, bound_w)
    x, b_bits, left = t_split(t_bits, spare)
    w = 2 if template == 1 else 3
    parts = [("BE", w), ("B", b_bits), ("TE", w), ("T", t_bits)]
    parts += [("L7", 1), ("IE", 1)] if template == 1 else [("IE", 1)]
    if left:
        parts.append(("wasted", left))
    return parts


def layout(order, widths):
    """order is MSB->LSB; returns {field: (bot, top)} with bit 0 = LSB."""
    pos, bit = {}, 0
    for f in reversed(order):
        pos[f] = (bit, bit + widths[f] - 1)
        bit += widths[f]
    return pos


# ---- user-defined names ------------------------------------------------------------------------
def name_ok(nm, taken=()):
    """A valid, unused C identifier that does not clash with the built-in permission names."""
    nm_upper = nm.upper()
    return bool(re.fullmatch(r"[A-Za-z_]\w*", nm)) and nm_upper not in RESERVED_NAMES and nm_upper not in taken

#Sayak: Function to check duplicate names across all groups and reserved names
def find_name_problems(groups):
    """groups = [("perm", names), ("otype", names), ("flag", names)]. Returns a list of readable problems.
    Names are C identifiers: two names must differ in at least one character, across ALL groups,
    and must not clash with a name the generated header already defines."""
    problems, seen = [], {}
    for kind, names in groups:
        for nm in names:
            nm_upper = nm.upper()
            if not re.fullmatch(r"[A-Za-z_]\w*", nm):
                problems.append(f"'{nm}' ({kind}) is not a valid C identifier")
            elif nm_upper in RESERVED_NAMES:
                problems.append(f"'{nm}' ({kind}) is already defined by the generated header")
            elif nm_upper in seen:
                # Find the first kind that used this name, and report the problem in a readable way.
                where = f"twice in {kind}s" if seen[nm_upper] == kind else f"in both {seen[nm_upper]}s and {kind}s"
                problems.append(f"'{nm}' is used {where}")
            else:
                seen[nm_upper] = kind
    return problems

# ---- everything together -----------------------------------------------------------------------------
def _check(label, v, lo, hi):
    if v is None or not (lo <= v <= hi):
        raise ValueError(f"{label} must be between {lo} and {hi} (got {v})")


def build_cfg(template, compressed, p, o, f, order, perm_names=(), otype_names=(), flag_names=(),
              bound_bits=None, t_bits=None, general_name="general.h"):
    """Validate all inputs and return the cfg dict for generate() / generate_utils().

    bound_bits: template 3 only (1..64, rounded up to 8/16/32/64).
    t_bits:     templates 1/2 only (1..t_max).
    Raises ValueError with a readable message for the first problem found.
    """
    if template not in (1, 2, 3):
        raise ValueError(f"Template must be 1, 2 or 3 (got {template})")
    _check("Perm bits", p, *perm_range(template))
    _check("Otype bits", o, *otype_range(template, p))
    _check("Flag bits", f, *flag_range(template, p, o))
    if template == 3:
        _check("Bound bits", bound_bits, 1, T3_BOUND_MAX)
    bound_w, meta_w, _ = bound_and_meta(template, p, o, f, bound_bits)
    assert meta_w % 8 == 0, "total metadata width must be divisible by 8"

    x = None
    if template in (1, 2):
        spare, t_max = t_range(template, bound_w)
        _check("T bits", t_bits, 1, t_max)
        x, _, _ = t_split(t_bits, spare)

    max_uperm = p - HW_PERM_COUNT
    if len(perm_names) > max_uperm:
        raise ValueError(f"At most {max_uperm} user-defined perms fit in {p} perm bits (got {len(perm_names)})")
    max_user = (1 << o) - 3
    if len(otype_names) > max_user:
        raise ValueError(f"At most {max_user} user-defined otypes fit in {o} otype bits (got {len(otype_names)})")
    max_flag = f - FLAG_MIN # CAP_MODE=0, other flags take 1..(f-1)
    if len(flag_names) > max_flag:
        raise ValueError(f"At most {max_flag} user-defined flags fit in {f} flag bits (got {len(flag_names)})")
    
    #Sayak: Check for duplicate names across all groups and reserved names
    problems = find_name_problems([("perm", perm_names), ("otype", otype_names), ("flag", flag_names)])
    if problems:
        raise ValueError("\n".join(problems))
    # seen = set()
    # for kind, names in (("perm", perm_names), ("otype", otype_names), ("flag", flag_names)):
    #     for nm in names:
    #         if not name_ok(nm, seen):
    #             raise ValueError(f"'{nm}' is not usable as a {kind} name: it must be a unique valid C identifier "
    #                              "that is not already used")
    # seen.add(nm)

    if sorted(order) != sorted("POFB"):
        raise ValueError("Field order must use each of P, O, F, B exactly once")

    widths = {"P": p, "O": o, "F": f, "B": bound_w}
    if template == 3:
        gen_widths = {"P": type_bits(p), "O": type_bits(o), "F": type_bits(f), "B": type_bits(bound_w)}
        return dict(x=x, template=template, meta_w=meta_w, addr_w=32, compressed=compressed,
                        widths=widths, order=order, pos=layout_gen(order, widths, gen_widths),
                        perm_names=list(perm_names), otype_names=list(otype_names), flag_names=list(flag_names), general_name=general_name)
    
    return dict(x=x, template=template, meta_w=meta_w, addr_w=32, compressed=compressed,
                widths=widths, order=order, pos=layout(order, widths),
                perm_names=list(perm_names), otype_names=list(otype_names), flag_names=list(flag_names), general_name=general_name)

    