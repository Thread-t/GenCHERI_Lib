#include <cstdint>
#include <cassert>
#include "instr.h"


#ifndef _CHERI_UTILS
#define _CHERI_UTILS

#define CAP_IE 19
#define CAP_L7 18
#define CAP_TE_TOP 13
#define CAP_TE_BOT 12
#define CAP_T_TOP 17
#define CAP_T_BOT 14
#define CAP_BE_TOP 5
#define CAP_BE_BOT 4
#define CAP_B_TOP 11
#define CAP_B_BOT 6
#define R_TOP CAP_B_TOP
#define R_BOT (R_TOP - 2)
#define REG_FIELD_LEN 5 // Register field in an instruction

#define E_MAX (ADDR_BITS - (CAP_B_TOP - CAP_B_BOT) - (CAP_BE_TOP - CAP_BE_BOT))

#define NULL_CAP (0b0 << CAP_PERM_BOT) | (0b0 << CAP_FLAG_BOT) | (Unsealed << CAP_OTYPE_BOT) | (0b1 << CAP_IE) | \
				 (0b1 << CAP_L7) | (0b0 << CAP_T_BOT) | (0b10 << CAP_TE_BOT) | (0b0 << CAP_B_BOT) | (0b10 << CAP_BE_BOT)
#define INF_CAP (0b111111111111 << CAP_PERM_BOT) | (0b0 << CAP_FLAG_BOT) | (Unsealed << CAP_OTYPE_BOT) | \
				(0b1 << CAP_IE) | (0b1 << CAP_L7) | (0b0 << CAP_T_BOT) | (0b10 << CAP_TE_BOT) | (0b0 << CAP_B_BOT) | (0b10 << CAP_BE_BOT)



namespace cheri32 {

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
SetBound_Ret set_bounds(Capability cs, uint64_t len, SetBound_flag choice);

}

#endif
