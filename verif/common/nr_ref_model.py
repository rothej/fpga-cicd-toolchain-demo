# verif/common/nr_ref_model.py

"""
verif/common/nr_ref_model.py

Python reference models for 5G NR physical-layer processing blocks.

Each function is a pure, stateless computation that matches the bit-exact
behaviour of the corresponding RTL module.  Scoreboard implementations
import these functions rather than re-implementing correctness logic inline.

Implemented:
    crc_compute    - parameterised CRC (CRC24A/B/C and CRC16 presets)
    scramble       - Gold-sequence XOR scrambler / descrambler
    qam_map        - QPSK / 16-QAM / 64-QAM / 256-QAM mapper
    qam_demap      - hard-decision nearest-neighbour demapper
    cp_insert      - cyclic prefix insertion
    cp_remove      - cyclic prefix removal
    nr_loopback_check - end-to-end loopback correctness invariant
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import IntEnum

__all__ = [
    "CrcPoly",
    "IQSample",
    "crc_compute",
    "scramble",
    "qam_map",
    "qam_demap",
    "cp_insert",
    "cp_remove",
    "nr_loopback_check",
]


# ---------------------------------------------------------------------------
# CRC  (TS 38.212 S5.1)
# ---------------------------------------------------------------------------


class CrcPoly(IntEnum):
    """
    Standard 5G NR CRC generator polynomials (TS 38.212 S5.1).

    Values are the polynomial coefficients excluding the implicit leading
    x^n term - the same representation used in the crc_pkg.sv parameter.

    CRC24A : 0x864CFB - transport-block CRC for large code blocks
    CRC24B : 0x800063 - code-block CRC
    CRC24C : 0xB2B117 - small transport-block CRC
    CRC16  : 0x11021  - UCI on PUSCH
    """

    CRC24A = 0x864CFB
    CRC24B = 0x800063
    CRC24C = 0xB2B117
    CRC16 = 0x11021


@dataclass(frozen=True)
class _CrcParams:
    poly: int
    width: int
    init: int = 0


_POLY_PARAMS: dict[CrcPoly, _CrcParams] = {
    CrcPoly.CRC24A: _CrcParams(poly=int(CrcPoly.CRC24A), width=24),
    CrcPoly.CRC24B: _CrcParams(poly=int(CrcPoly.CRC24B), width=24),
    CrcPoly.CRC24C: _CrcParams(poly=int(CrcPoly.CRC24C), width=24),
    CrcPoly.CRC16: _CrcParams(poly=int(CrcPoly.CRC16), width=16),
}


def crc_compute(
    data: Sequence[int],
    poly: int | CrcPoly,
    width: int,
    *,
    init: int = 0,
) -> int:
    """
    Compute a CRC over *data* using a bit-serial LFSR model (MSB-first).

    This matches the shift-register implementation in crc_engine.sv: each
    input byte is fed MSB-first into the LFSR, so the result is bit-exact
    with the hardware output without any additional bit-reversal.

    Args:
        data:  Sequence of integer byte values (0-255).
        poly:  Generator polynomial (excluding leading term).
               Pass a CrcPoly member for standard 5G NR presets.
        width: CRC width in bits (24 for CRC24x, 16 for CRC16).
        init:  Initial LFSR value.  Default 0 matches crc_engine.sv reset.

    Returns:
        CRC integer in the range [0, 2**width).
    """
    mask = (1 << width) - 1
    crc = int(init) & mask

    for byte in data:
        for bit_idx in range(7, -1, -1):  # MSB first
            bit = (byte >> bit_idx) & 1
            if ((crc >> (width - 1)) & 1) ^ bit:
                crc = ((crc << 1) ^ int(poly)) & mask
            else:
                crc = (crc << 1) & mask

    return crc


# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------

# (i_value, q_value) as signed 8-bit integers - matches logic signed [7:0]
# in qam_mapper.sv / qam_demapper.sv.
IQSample = tuple[int, int]


# ---------------------------------------------------------------------------
# Scrambler  (TS 38.211 S7.3.1.1)
# ---------------------------------------------------------------------------

# X1 fixed seed: x1[0]=1, x1[1..30]=0  (scrambler.sv: localparam X1_INIT)
_X1_INIT: int = 0x0000001
_MASK_31: int = 0x7FFFFFFF  # 31-bit mask


def _scr_step(s1: int, s2: int) -> tuple[int, int, int]:
    """
    Output one gold bit and advance both x1/x2 LFSRs by one step.

    x1 feedback : nb = s[3] ^ s[0]
    x2 feedback : nb = s[3] ^ s[2] ^ s[1] ^ s[0]
    State update: s  = {nb, s[30:1]}

    Returns:
        (gold_bit, new_s1, new_s2)
    """
    b1 = s1 & 1
    b2 = s2 & 1
    nb1 = ((s1 >> 3) ^ s1) & 1
    nb2 = ((s2 >> 3) ^ (s2 >> 2) ^ (s2 >> 1) ^ s2) & 1
    new_s1 = ((nb1 << 30) | (s1 >> 1)) & _MASK_31
    new_s2 = ((nb2 << 30) | (s2 >> 1)) & _MASK_31
    return b1 ^ b2, new_s1, new_s2


def scramble(data: Sequence[int], c_init: int, data_w: int = 8) -> list[int]:
    """
    XOR-scramble (or descramble) *data* with the 5G NR Gold sequence.

    Self-inverse: scramble(scramble(data, c_init), c_init) == list(data).

    Matches scrambler.sv exactly:
        x1 feedback : x1[n+31] = x1[n+3] ^ x1[n]
        x2 feedback : x2[n+31] = x2[n+3] ^ x2[n+2] ^ x2[n+1] ^ x2[n]
        LFSR convention: sr[0] is oldest (next output); new bit inserted at sr[30].
        8 gold bits are consumed per input word, bit[7] = first LFSR output.

    Note: The Nc=1600 warm-up required by TS 38.211 S7.3.1.1 is omitted to
    match scrambler.sv, which seeds the LFSRs directly from c_init.

    Args:
        data:   Sequence of input words (0 to 2**data_w - 1).
        c_init: 31-bit x2 LFSR seed (matches the cinit port of scrambler.sv).
        data_w: Word width in bits; matches RTL DATA_W parameter (default 8).

    Returns:
        List of scrambled (or descrambled) words, same length as *data*.
    """
    mask = (1 << data_w) - 1
    s1 = _X1_INIT
    s2 = int(c_init) & _MASK_31

    result: list[int] = []
    for word in data:
        gold = 0
        # Consume 8 bits MSB-first: bit[7] = first LFSR output.
        # Matches get_x1_byte / get_x2_byte in scrambler.sv.
        for i in range(7, -1, -1):
            bit, s1, s2 = _scr_step(s1, s2)
            gold |= bit << i
        result.append((word ^ gold) & mask)
    return result


# ---------------------------------------------------------------------------
# QAM mapper  (TS 38.211 S7.3.1.2)
# ---------------------------------------------------------------------------

# Gray-coded axis-value lookup tables matching qam_mapper.sv.
# Key   = Gray-coded bit pattern for one axis.
# Value = signed integer amplitude (range -127 ... +127).

_QPSK_TABLE: dict[int, int] = {
    0: 90,
    1: -90,
}

_QAM16_TABLE: dict[int, int] = {
    0b00: 72,
    0b01: 24,
    0b11: -24,
    0b10: -72,
}

_QAM64_TABLE: dict[int, int] = {
    0b000: 84,
    0b001: 60,
    0b011: 36,
    0b010: 12,
    0b110: -12,
    0b111: -36,
    0b101: -60,
    0b100: -84,
}

_QAM256_TABLE: dict[int, int] = {
    0b0000: 90,
    0b0001: 78,
    0b0011: 66,
    0b0010: 54,
    0b0110: 42,
    0b0111: 30,
    0b0101: 18,
    0b0100: 6,
    0b1100: -6,
    0b1101: -18,
    0b1111: -30,
    0b1110: -42,
    0b1010: -54,
    0b1011: -66,
    0b1001: -78,
    0b1000: -90,
}


def qam_map(bytes_in: Sequence[int], mod_order: int) -> list[IQSample]:
    """
    Map each input byte to a Gray-coded QAM constellation point.

    Bit-packing convention (mirrors qam_mapper.sv):
        mod_order=2 : byte[1]   = I bit,    byte[0]   = Q bit
        mod_order=4 : byte[3:2] = I 2-bit,  byte[1:0] = Q 2-bit
        mod_order=6 : byte[5:3] = I 3-bit,  byte[2:0] = Q 3-bit
        mod_order=8 : byte[7:4] = I 4-bit,  byte[3:0] = Q 4-bit

    Amplitude scaling matches qam_mapper.sv (peak +/-90 within 8-bit signed range).

    Args:
        bytes_in:  Sequence of input bytes.  Only the lower mod_order bits
                   of each byte are used; upper bits are ignored.
        mod_order: Bits per symbol: 2 (QPSK), 4 (16-QAM), 6 (64-QAM),
                   8 (256-QAM).

    Returns:
        List of (i_value, q_value) integer tuples, one per input byte.
        Values are in the signed 8-bit range (-128 ... 127).
    """
    result: list[IQSample] = []
    for byte in bytes_in:
        if mod_order == 2:
            i = _QPSK_TABLE[(byte >> 1) & 0x1]
            q = _QPSK_TABLE[byte & 0x1]
        elif mod_order == 4:
            i = _QAM16_TABLE[(byte >> 2) & 0x3]
            q = _QAM16_TABLE[byte & 0x3]
        elif mod_order == 6:
            i = _QAM64_TABLE[(byte >> 3) & 0x7]
            q = _QAM64_TABLE[byte & 0x7]
        elif mod_order == 8:
            i = _QAM256_TABLE[(byte >> 4) & 0xF]
            q = _QAM256_TABLE[byte & 0xF]
        else:
            i, q = 0, 0
        result.append((i, q))
    return result


# ---------------------------------------------------------------------------
# QAM demapper  (TS 38.211 S7.3.1.2)
# ---------------------------------------------------------------------------

# Threshold-based decision functions - one per modulation order - matching
# qam_demapper.sv exactly.  Decision boundaries are midpoints between
# adjacent qam_mapper.sv output levels.


def _demap_qpsk(v: int) -> int:
    # Threshold at 0.  +90 -> 0b0; -90 -> 0b1.
    return 0 if v >= 0 else 1


def _demap_qam16(v: int) -> int:
    # Thresholds at 0, +/-48 (midpoints of +/-24, +/-72).
    if v > 48:
        return 0b00
    elif v > 0:
        return 0b01
    elif v > -48:
        return 0b11
    else:
        return 0b10


def _demap_qam64(v: int) -> int:
    # Thresholds at 0, +/-24, +/-48, +/-72
    # (midpoints of +/-12, +/-36, +/-60, +/-84).
    if v > 72:
        return 0b000
    elif v > 48:
        return 0b001
    elif v > 24:
        return 0b011
    elif v > 0:
        return 0b010
    elif v > -24:
        return 0b110
    elif v > -48:
        return 0b111
    elif v > -72:
        return 0b101
    else:
        return 0b100


def _demap_qam256(v: int) -> int:
    # Thresholds at 0, +/-12, +/-24, +/-36, +/-48, +/-60, +/-72, +/-84
    # (midpoints of +/-6, +/-18, ..., +/-90).
    if v > 84:
        return 0b0000
    elif v > 72:
        return 0b0001
    elif v > 60:
        return 0b0011
    elif v > 48:
        return 0b0010
    elif v > 36:
        return 0b0110
    elif v > 24:
        return 0b0111
    elif v > 12:
        return 0b0101
    elif v > 0:
        return 0b0100
    elif v > -12:
        return 0b1100
    elif v > -24:
        return 0b1101
    elif v > -36:
        return 0b1111
    elif v > -48:
        return 0b1110
    elif v > -60:
        return 0b1010
    elif v > -72:
        return 0b1011
    elif v > -84:
        return 0b1001
    else:
        return 0b1000


def qam_demap(symbols: Sequence[IQSample], mod_order: int) -> list[int]:
    """
    Hard-decision demap each (I, Q) symbol to a byte.

    Inverts qam_map() via nearest-neighbour threshold comparison on each
    axis independently.  Bit-packing mirrors qam_demapper.sv:
        mod_order=2 : byte = {6'b0, I_bit,   Q_bit}
        mod_order=4 : byte = {4'b0, I_2bits, Q_2bits}
        mod_order=6 : byte = {2'b0, I_3bits, Q_3bits}
        mod_order=8 : byte = {     I_4bits,  Q_4bits}

    Args:
        symbols:   Sequence of (i_value, q_value) integer tuples.
                   Values must be in the RTL amplitude scale (+/-90, etc.).
        mod_order: Bits per symbol: 2, 4, 6, or 8.

    Returns:
        List of recovered bytes, one per input symbol.
    """
    result: list[int] = []
    for i_val, q_val in symbols:
        if mod_order == 2:
            byte = (_demap_qpsk(i_val) << 1) | _demap_qpsk(q_val)
        elif mod_order == 4:
            byte = (_demap_qam16(i_val) << 2) | _demap_qam16(q_val)
        elif mod_order == 6:
            byte = (_demap_qam64(i_val) << 3) | _demap_qam64(q_val)
        elif mod_order == 8:
            byte = (_demap_qam256(i_val) << 4) | _demap_qam256(q_val)
        else:
            byte = 0
        result.append(byte)
    return result


# ---------------------------------------------------------------------------
# Cyclic prefix  (TS 38.211 S5.3.1)
# ---------------------------------------------------------------------------


def cp_insert(samples: list[int], cp_len: int) -> list[int]:
    """
    Cyclic prefix insertion: prepend the last cp_len samples to the symbol.

    Matches cp_inserter.sv: the CP is the last cp_len samples of the symbol
    buffer, prepended to the full symbol.  Output layout:
        [ samples[-cp_len:] ] + [ samples[0:] ]
    for a total of cp_len + len(samples) output samples.

    cp_len=0 is valid: output equals input verbatim (no-prefix passthrough).

    Args:
        samples: list of N_FFT integer sample words (one OFDM symbol).
        cp_len:  number of samples to copy from the tail and prepend.

    Returns:
        list of (cp_len + len(samples)) integer sample words.
    """
    if cp_len < 0:
        raise ValueError(f"cp_len must be >= 0; got {cp_len}")
    if cp_len > len(samples):
        raise ValueError(f"cp_len {cp_len} exceeds symbol length {len(samples)}")
    if cp_len == 0:
        return list(samples)
    return list(samples[-cp_len:]) + list(samples)


def cp_remove(full_samples: list[int], cp_len: int) -> list[int]:
    """
    Cyclic prefix removal: discard the first cp_len samples of the packet.

    Matches cp_remover.sv: the first cp_len samples of each burst are
    discarded; the remaining samples are forwarded.  Input layout:
        [ full_samples[0:cp_len] (CP, discarded) ] + [ payload (kept) ]

    cp_len=0 is valid: output equals input verbatim (no-prefix passthrough).

    Args:
        full_samples: list of (cp_len + N_FFT) integer sample words.
        cp_len:       number of leading samples to discard.

    Returns:
        list of N_FFT integer sample words (the payload).
    """
    if cp_len < 0:
        raise ValueError(f"cp_len must be >= 0; got {cp_len}")
    if cp_len > len(full_samples):
        raise ValueError(f"cp_len {cp_len} exceeds packet length {len(full_samples)}")
    if cp_len == 0:
        return list(full_samples)
    return list(full_samples[cp_len:])


# ---------------------------------------------------------------------------
# End-to-end loopback check
# ---------------------------------------------------------------------------


def nr_loopback_check(
    payload_in: list[int],
    payload_out: list[int],
    crc_ok: bool,
) -> bool:
    """
    End-to-end loopback correctness invariant for an error-free channel.

    For an ideal TX->RX chain (no quantisation error, no channel noise):
        payload_out == payload_in  AND  crc_ok == True

    Args:
        payload_in:  original bytes driven into nr_tx_chain
        payload_out: bytes recovered from nr_rx_chain output
        crc_ok:      DUT's CRC check result sampled at m_axis_tlast

    Returns:
        True iff both the content and CRC status invariants hold.
    """
    return crc_ok and (payload_out == payload_in)
