#include <cstdint>
#include <cassert>
#include "general.h"
#include "instr.h"


#ifndef _CHERI_UTILS
#define _CHERI_UTILS

inline const CHERI NULL_CAP(
    0,
    Unsealed,
    0,
    0xFFFFFFFF00000000
);

inline const CHERI INF_CAP( 
    ((BIT_SLICE((~0), (CAP_PERM_TOP - CAP_PERM_BOT), 0))),
    Unsealed,
    0,
    0xFFFFFFFF00000000
);

namespace cheri32 {

//Find the base address of the given capability.
inline uint32_t get_base(uint32_t addr, CHERI metadata) {
	return ( static_cast<uint32_t>(metadata.get_bounds() & static_cast<uint64_t>(0xFFFFFFFF)) );
}

//Find the top address of the given capability. Note that,
//top can be a 33 bit value at max, hence represented as 64 bit signed integer.
inline int64_t get_top(uint32_t addr, CHERI metadata) {
	int64_t top = static_cast<int64_t>(metadata.get_bounds() >> 32) + 1;
	return (top);
}

//Does not exactly set the address. Mainly does the fast representability
//check to find whether the offset rs2 will take the address out of the
//representable range.
//If setoffset is true, rs2 is added to cs1 base, else to cs1 address.
inline bool set_offset(Capability cs1, int64_t imm, bool setoffset) {
	return true;
}

//To check if address is within bounds of the capability.
inline bool cap_inbounds(Capability cs) {
	uint32_t base = get_base(cs.addr, cs.caps);
	int64_t top = get_top(cs.addr, cs.caps);
	if ( (cs.addr >= base) && (cs.addr < top) ) return true;
	else return false;
}

//Create a new capability with base as cs.addr and length as len.
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
inline SetBound_Ret set_bounds(Capability cs, uint64_t len, SetBound_flag choice) {
	SetBound_Ret final;
	uint32_t new_b = cs.addr;
	int64_t new_t = (cs.addr + len);

	final.baseMask = static_cast<uint32_t>(~0);
	final.exact = true;
	final.newlen = len;

	if ((choice.mask) || (choice.len)) return (final);

	final.cd.addr = cs.addr;
	final.cd.caps = cs.caps;
	final.cd.caps.set_bounds(((static_cast<uint64_t>(new_t - 1) << 32) | static_cast<uint64_t>(new_b)));

	return (final);
}

}

#else

#endif
