# verif/common/tests/test_nr_ref_model.py

"""
Pure-Python pytest unit tests for verif/common/nr_ref_model.py.

No simulator required: all functions are stateless pure Python.
Run with: make test  (delegates to pytest verif/common/tests/)
"""

from __future__ import annotations

import random

import pytest

from verif.common.nr_ref_model import (
    CrcPoly,
    cp_insert,
    cp_remove,
    crc_compute,
    nr_loopback_check,
    qam_demap,
    qam_map,
    scramble,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MOD_ORDERS = [2, 4, 6, 8]


# ---------------------------------------------------------------------------
# crc_compute
# ---------------------------------------------------------------------------


class TestCrcCompute:
    @pytest.mark.parametrize(
        "poly,width",
        [
            (CrcPoly.CRC24A, 24),
            (CrcPoly.CRC24B, 24),
            (CrcPoly.CRC24C, 24),
            (CrcPoly.CRC16, 16),
        ],
    )
    def test_output_in_range(self, poly: CrcPoly, width: int) -> None:
        result = crc_compute(list(range(16)), poly, width)
        assert 0 <= result < (1 << width)

    def test_empty_data_returns_init(self) -> None:
        assert crc_compute([], CrcPoly.CRC24A, 24) == 0
        assert crc_compute([], CrcPoly.CRC24A, 24, init=0xABCDEF) == 0xABCDEF

    def test_all_zero_input_with_zero_init_gives_zero(self) -> None:
        # All bits are 0 -> feedback is always 0 -> LFSR stays 0
        for length in [1, 8, 64]:
            assert crc_compute([0x00] * length, CrcPoly.CRC24A, 24) == 0

    def test_deterministic(self) -> None:
        data = list(range(32))
        assert crc_compute(data, CrcPoly.CRC24A, 24) == crc_compute(data, CrcPoly.CRC24A, 24)

    def test_different_polys_give_different_results(self) -> None:
        data = list(range(1, 17))
        r24a = crc_compute(data, CrcPoly.CRC24A, 24)
        r24b = crc_compute(data, CrcPoly.CRC24B, 24)
        r16 = crc_compute(data, CrcPoly.CRC16, 16)
        assert r24a != r24b
        assert r24a != r16

    def test_all_ones_single_byte_nonzero(self) -> None:
        for poly, width in [
            (CrcPoly.CRC24A, 24),
            (CrcPoly.CRC24B, 24),
            (CrcPoly.CRC16, 16),
        ]:
            assert crc_compute([0xFF], poly, width) != 0

    def test_integer_poly_accepted(self) -> None:
        data = [0xAB, 0xCD]
        assert crc_compute(data, int(CrcPoly.CRC24A), 24) == crc_compute(data, CrcPoly.CRC24A, 24)

    def test_length_sensitivity(self) -> None:
        # Appending 0x00 must change the CRC (the LFSR shifts even on zero input)
        r1 = crc_compute([0x01], CrcPoly.CRC24A, 24)
        r2 = crc_compute([0x01, 0x00], CrcPoly.CRC24A, 24)
        assert r1 != r2

    def test_output_never_exceeds_width(self) -> None:
        for poly, width in [(CrcPoly.CRC24A, 24), (CrcPoly.CRC16, 16)]:
            result = crc_compute([0xFF] * 64, poly, width)
            assert result < (1 << width)
            assert result & ~((1 << width) - 1) == 0


# ---------------------------------------------------------------------------
# scramble
# ---------------------------------------------------------------------------


class TestScramble:
    def test_self_inverse(self) -> None:
        data = list(range(64))
        cinit = 0x12345678 & 0x7FFFFFFF
        assert scramble(scramble(data, cinit), cinit) == data

    def test_output_length_preserved(self) -> None:
        for n in [1, 8, 64, 256]:
            assert len(scramble([0xAB] * n, 0x00000001)) == n

    def test_all_zeros_input_not_all_zeros_output(self) -> None:
        # scramble([0]*n, cinit) == Gold sequence; non-trivial for any real cinit
        result = scramble([0x00] * 16, 0x00000001)
        assert not all(b == 0 for b in result)

    def test_different_cinit_different_output(self) -> None:
        data = [0xAB] * 32
        assert scramble(data, 0x00000001) != scramble(data, 0x00000002)

    def test_output_in_byte_range(self) -> None:
        result = scramble(list(range(32)), 0x12345678 & 0x7FFFFFFF)
        assert all(0 <= b <= 255 for b in result)

    def test_data_w_masks_output(self) -> None:
        result = scramble([0xFF] * 8, 0x1, data_w=4)
        mask = (1 << 4) - 1
        assert all(b <= mask for b in result)

    def test_self_inverse_with_data_w_4(self) -> None:
        data = [random.randint(0, 0xF) for _ in range(32)]
        cinit = 0x5A5A5A5A & 0x7FFFFFFF
        assert scramble(scramble(data, cinit, data_w=4), cinit, data_w=4) == data


# ---------------------------------------------------------------------------
# qam_map / qam_demap
# ---------------------------------------------------------------------------


class TestQamMap:
    @pytest.mark.parametrize("mo", _MOD_ORDERS)
    def test_output_length_matches_input(self, mo: int) -> None:
        data = list(range(1 << mo))
        assert len(qam_map(data, mo)) == len(data)

    @pytest.mark.parametrize("mo", _MOD_ORDERS)
    def test_outputs_in_signed_8bit_range(self, mo: int) -> None:
        mask = (1 << mo) - 1
        data = [random.randint(0, mask) for _ in range(64)]
        for i_val, q_val in qam_map(data, mo):
            assert -128 <= i_val <= 127
            assert -128 <= q_val <= 127

    @pytest.mark.parametrize("mo", _MOD_ORDERS)
    def test_all_constellation_points_distinct(self, mo: int) -> None:
        data = list(range(1 << mo))
        symbols = qam_map(data, mo)
        assert len(set(symbols)) == len(data)

    def test_qpsk_uses_only_ninety_levels(self) -> None:
        symbols = qam_map([0, 1, 2, 3], 2)
        for i_val, q_val in symbols:
            assert i_val in (90, -90)
            assert q_val in (90, -90)


class TestQamDemap:
    @pytest.mark.parametrize("mo", _MOD_ORDERS)
    def test_roundtrip_random(self, mo: int) -> None:
        mask = (1 << mo) - 1
        data = [random.randint(0, mask) for _ in range(64)]
        assert qam_demap(qam_map(data, mo), mo) == data

    @pytest.mark.parametrize("mo", _MOD_ORDERS)
    def test_all_constellation_points_roundtrip(self, mo: int) -> None:
        data = list(range(1 << mo))
        assert qam_demap(qam_map(data, mo), mo) == data

    def test_output_length_matches_input(self) -> None:
        symbols = [(90, 90), (-90, 90), (90, -90), (-90, -90)]
        assert len(qam_demap(symbols, 2)) == 4

    @pytest.mark.parametrize("mo", _MOD_ORDERS)
    def test_output_values_in_valid_range(self, mo: int) -> None:
        mask = (1 << mo) - 1
        data = [random.randint(0, mask) for _ in range(32)]
        result = qam_demap(qam_map(data, mo), mo)
        assert all(0 <= b <= mask for b in result)


# ---------------------------------------------------------------------------
# cp_insert / cp_remove
# ---------------------------------------------------------------------------


class TestCpInsert:
    def test_output_length(self) -> None:
        samples = list(range(64))
        for cp_len in [0, 1, 4, 9, 16]:
            assert len(cp_insert(samples, cp_len)) == len(samples) + cp_len

    def test_prefix_is_tail_copy(self) -> None:
        samples = list(range(64))
        cp_len = 9
        result = cp_insert(samples, cp_len)
        assert result[:cp_len] == samples[-cp_len:]

    def test_payload_region_unchanged(self) -> None:
        samples = list(range(64))
        cp_len = 9
        result = cp_insert(samples, cp_len)
        assert result[cp_len:] == samples

    def test_zero_cp_passthrough(self) -> None:
        samples = list(range(64))
        assert cp_insert(samples, 0) == samples

    def test_negative_cp_raises(self) -> None:
        with pytest.raises(ValueError):
            cp_insert(list(range(64)), -1)

    def test_cp_exceeds_length_raises(self) -> None:
        with pytest.raises(ValueError):
            cp_insert(list(range(8)), 9)


class TestCpRemove:
    def test_output_length(self) -> None:
        for cp_len in [0, 1, 4, 9, 16]:
            full = list(range(cp_len + 64))
            assert len(cp_remove(full, cp_len)) == 64

    def test_discards_leading_samples(self) -> None:
        cp_len = 9
        full = list(range(cp_len + 64))
        assert cp_remove(full, cp_len) == full[cp_len:]

    def test_zero_cp_passthrough(self) -> None:
        samples = list(range(64))
        assert cp_remove(samples, 0) == samples

    def test_negative_cp_raises(self) -> None:
        with pytest.raises(ValueError):
            cp_remove(list(range(64)), -1)

    def test_cp_exceeds_length_raises(self) -> None:
        with pytest.raises(ValueError):
            cp_remove(list(range(8)), 9)


class TestCpRoundtrip:
    @pytest.mark.parametrize("cp_len", [0, 1, 4, 9, 16])
    def test_insert_then_remove_recovers_original(self, cp_len: int) -> None:
        random.seed(0xC0DE)
        samples = [random.randint(0, 0xFFFF) for _ in range(64)]
        assert cp_remove(cp_insert(samples, cp_len), cp_len) == samples


# ---------------------------------------------------------------------------
# nr_loopback_check
# ---------------------------------------------------------------------------


class TestNrLoopbackCheck:
    def test_pass_when_data_matches_and_crc_ok(self) -> None:
        data = [1, 2, 3]
        assert nr_loopback_check(data, data, crc_ok=True) is True

    def test_fail_when_crc_bad(self) -> None:
        data = [1, 2, 3]
        assert nr_loopback_check(data, data, crc_ok=False) is False

    def test_fail_when_data_differs(self) -> None:
        assert nr_loopback_check([1, 2, 3], [1, 2, 4], crc_ok=True) is False

    def test_fail_when_both_wrong(self) -> None:
        assert nr_loopback_check([1, 2], [3, 4], crc_ok=False) is False

    def test_fail_when_length_mismatch(self) -> None:
        assert nr_loopback_check([1, 2, 3], [1, 2], crc_ok=True) is False

    def test_empty_payload_passes(self) -> None:
        assert nr_loopback_check([], [], crc_ok=True) is True

    def test_empty_payload_fails_on_bad_crc(self) -> None:
        assert nr_loopback_check([], [], crc_ok=False) is False
