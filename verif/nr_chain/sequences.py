# verif/nr_chain/sequences.py

from __future__ import annotations

import random

from pyuvm import ConfigDB, uvm_sequence

from verif.common.config_utils import _cfg
from verif.nr_chain.seq_item import NrChainSeqItem


class SingleBlockLoopbackSeq(uvm_sequence):
    """
    One transport block of payload_len random bytes.

    ConfigDB keys: payload_len, cp_len, scrambler_seed, data_w
    """

    async def body(self) -> None:
        payload_len = _cfg(self, "payload_len", 64)
        cp_len = _cfg(self, "cp_len", 9)
        scrambler_seed = _cfg(self, "scrambler_seed", 0x00_0001)
        data_w = _cfg(self, "data_w", 8)
        mask = (1 << data_w) - 1

        item = NrChainSeqItem()
        item.payload = [random.randint(0, mask) for _ in range(payload_len)]
        item.cp_len = cp_len
        item.scrambler_seed = scrambler_seed
        item.data_w = data_w
        await self.start_item(item)
        await self.finish_item(item)


class MultiBlockLoopbackSeq(uvm_sequence):
    """
    count transport blocks of payload_len random bytes, driven back-to-back.

    Primary integration regression for inter-block contamination: payload
    bytes from block N must not appear in the recovered output of block N+1.

    ConfigDB keys: payload_len, cp_len, scrambler_seed, data_w, count
    """

    async def body(self) -> None:
        payload_len = _cfg(self, "payload_len", 64)
        cp_len = _cfg(self, "cp_len", 9)
        scrambler_seed = _cfg(self, "scrambler_seed", 0x00_0001)
        data_w = _cfg(self, "data_w", 8)
        count = _cfg(self, "count", 16)
        mask = (1 << data_w) - 1

        for _ in range(count):
            item = NrChainSeqItem()
            item.payload = [random.randint(0, mask) for _ in range(payload_len)]
            item.cp_len = cp_len
            item.scrambler_seed = scrambler_seed
            item.data_w = data_w
            await self.start_item(item)
            await self.finish_item(item)


class VaryingCpLoopbackSeq(uvm_sequence):
    """
    One transport block per cp_len in cp_lens, driven back-to-back.

    Models the 5G NR slot structure end-to-end: symbol 0 has the extended CP,
    symbols 1-13 have the normal CP.  Both TX cp_inserter and RX cp_remover
    receive the same cp_len sideband at each symbol boundary.

    ConfigDB keys: payload_len, scrambler_seed, data_w, cp_lens (list[int])
    """

    async def body(self) -> None:
        payload_len = _cfg(self, "payload_len", 64)
        scrambler_seed = _cfg(self, "scrambler_seed", 0x00_0001)
        data_w = _cfg(self, "data_w", 8)
        cp_lens = _cfg(self, "cp_lens", [0, 4, 8, 12, 16])
        mask = (1 << data_w) - 1

        for cp_len in cp_lens:
            item = NrChainSeqItem()
            item.payload = [random.randint(0, mask) for _ in range(payload_len)]
            item.cp_len = cp_len
            item.scrambler_seed = scrambler_seed
            item.data_w = data_w
            await self.start_item(item)
            await self.finish_item(item)


class MinPayloadLoopbackSeq(uvm_sequence):
    """
    Single transport block with a one-byte payload.

    Stresses the minimum-length path: CRC attach must produce exactly
    1 + POLY_W/8 bytes regardless of payload size; QAM mapper must handle
    the resulting short bit vector without dropping the final partial symbol.

    ConfigDB keys: cp_len, scrambler_seed, data_w
    """

    async def body(self) -> None:
        cp_len = _cfg(self, "cp_len", 9)
        scrambler_seed = _cfg(self, "scrambler_seed", 0x00_0001)
        data_w = _cfg(self, "data_w", 8)
        mask = (1 << data_w) - 1

        item = NrChainSeqItem()
        item.payload = [random.randint(0, mask)]
        item.cp_len = cp_len
        item.scrambler_seed = scrambler_seed
        item.data_w = data_w
        await self.start_item(item)
        await self.finish_item(item)


class SeedSweepLoopbackSeq(uvm_sequence):
    """
    Same fixed payload, one block per seed in scrambler_seeds.

    Same-payload / varying-seed regression: every recovered output must equal
    the original payload despite different on-the-wire representations.
    A single byte error localises to the descrambler seed-loading logic.

    ConfigDB keys: payload_len, cp_len, data_w, scrambler_seeds (list[int])
    """

    async def body(self) -> None:
        payload_len = _cfg(self, "payload_len", 64)
        cp_len = _cfg(self, "cp_len", 9)
        data_w = _cfg(self, "data_w", 8)
        scrambler_seeds = _cfg(
            self,
            "scrambler_seeds",
            [0x00_0001, 0x00_0003, 0xAB_CDEF, 0xFF_FFFF],
        )
        mask = (1 << data_w) - 1
        payload = [random.randint(0, mask) for _ in range(payload_len)]

        for seed in scrambler_seeds:
            item = NrChainSeqItem()
            item.payload = list(payload)  # identical payload every time
            item.cp_len = cp_len
            item.scrambler_seed = seed
            item.data_w = data_w
            await self.start_item(item)
            await self.finish_item(item)


# Virtual sequences


class NrChainVirtualSeqBase(uvm_sequence):
    """
    Base class for nr_chain virtual sequences.

    Concrete subclasses start primitive sequences via self.tx_seqr, which
    resolves to the NrChainVirtualSequencer's tx_sequencer handle.
    This attribute is None until NrChainEnv.connect_phase completes -
    virtual sequences are safe to call only from run_phase.
    """

    @property
    def tx_seqr(self):
        return self.sequencer.tx_sequencer


class DefaultLoopbackVSeq(NrChainVirtualSeqBase):
    """16 random transport blocks at ConfigDB defaults."""

    async def body(self) -> None:
        await MultiBlockLoopbackSeq("multi_blk").start(self.tx_seqr)


class VaryingCpVSeq(NrChainVirtualSeqBase):
    """One block per CP length in [0, 4, 8, 12, 16]."""

    async def body(self) -> None:
        await VaryingCpLoopbackSeq("varying_cp").start(self.tx_seqr)


class SeedSweepVSeq(NrChainVirtualSeqBase):
    """Four scrambler seeds, same payload."""

    async def body(self) -> None:
        await SeedSweepLoopbackSeq("seed_sweep").start(self.tx_seqr)


class StressVSeq(NrChainVirtualSeqBase):
    """
    Three-phase stress: seed sweep -> varying CP -> 32 back-to-back blocks.

    Exercises the full set of parameter transitions the physical layer
    encounters across a 5G NR slot boundary - first demonstrating that
    scrambler re-seeding is independent of CP length, then saturating
    the pipeline with the maximum back-to-back block count.
    """

    async def body(self) -> None:
        await SeedSweepLoopbackSeq("stress_seed").start(self.tx_seqr)
        await VaryingCpLoopbackSeq("stress_cp").start(self.tx_seqr)
        ConfigDB().set(self, "*", "count", 32)
        await MultiBlockLoopbackSeq("stress_multi").start(self.tx_seqr)
