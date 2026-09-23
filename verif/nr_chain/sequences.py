# verif/nr_chain/sequences.py

from __future__ import annotations

import random

from pyuvm import uvm_sequence

from verif.nr_chain.seq_item import NrChainSeqItem

# ---------------------------------------------------------------------------
# Primitive sequences
# ---------------------------------------------------------------------------


class SingleBlockLoopbackSeq(uvm_sequence):
    """One transport block of payload_len random bytes."""

    def __init__(self, name: str = "SingleBlockLoopbackSeq") -> None:
        super().__init__(name)
        self.payload_len: int = 64
        self.cp_len: int = 9
        self.scrambler_seed: int = 0x00_0001
        self.data_w: int = 8
        self.mod_order: int = 8  # set to RTL MOD_ORDER; controls payload bit width

    async def body(self) -> None:
        mask = (1 << self.mod_order) - 1  # was: (1 << self.data_w) - 1
        item = NrChainSeqItem()
        item.payload = [random.randint(0, mask) for _ in range(self.payload_len)]
        item.cp_len = self.cp_len
        item.scrambler_seed = self.scrambler_seed
        item.data_w = self.data_w
        await self.start_item(item)
        await self.finish_item(item)


class MultiBlockLoopbackSeq(uvm_sequence):
    """
    count transport blocks of payload_len random bytes, driven back-to-back.

    Primary integration regression for inter-block contamination: payload
    bytes from block N must not appear in the recovered output of block N+1.
    """

    def __init__(self, name: str = "MultiBlockLoopbackSeq") -> None:
        super().__init__(name)
        self.payload_len: int = 64
        self.cp_len: int = 9
        self.scrambler_seed: int = 0x00_0001
        self.data_w: int = 8
        self.mod_order: int = 8  # set to RTL MOD_ORDER; controls payload bit width
        self.count: int = 16

    async def body(self) -> None:
        mask = (1 << self.mod_order) - 1  # was: (1 << self.data_w) - 1
        for _ in range(self.count):
            item = NrChainSeqItem()
            item.payload = [random.randint(0, mask) for _ in range(self.payload_len)]
            item.cp_len = self.cp_len
            item.scrambler_seed = self.scrambler_seed
            item.data_w = self.data_w
            await self.start_item(item)
            await self.finish_item(item)


class VaryingCpLoopbackSeq(uvm_sequence):
    """
    One transport block per cp_len in cp_lens, driven back-to-back.

    Models the 5G NR slot structure end-to-end: symbol 0 has the extended CP,
    symbols 1-13 have the normal CP. Both TX cp_inserter and RX cp_remover
    receive the same cp_len sideband at each symbol boundary.
    """

    def __init__(self, name: str = "VaryingCpLoopbackSeq") -> None:
        super().__init__(name)
        self.payload_len: int = 64
        self.scrambler_seed: int = 0x00_0001
        self.data_w: int = 8
        self.mod_order: int = 8  # set to RTL MOD_ORDER; controls payload bit width
        self.cp_lens: list[int] = [0, 4, 8, 12, 16]

    async def body(self) -> None:
        mask = (1 << self.mod_order) - 1  # was: (1 << self.data_w) - 1
        for cp_len in self.cp_lens:
            item = NrChainSeqItem()
            item.payload = [random.randint(0, mask) for _ in range(self.payload_len)]
            item.cp_len = cp_len
            item.scrambler_seed = self.scrambler_seed
            item.data_w = self.data_w
            await self.start_item(item)
            await self.finish_item(item)


class MinPayloadLoopbackSeq(uvm_sequence):
    """
    Single transport block with a one-byte payload.

    Stresses the minimum-length path through every stage of both chains.
    """

    def __init__(self, name: str = "MinPayloadLoopbackSeq") -> None:
        super().__init__(name)
        self.n_fft: int = 64  # one complete OFDM symbol
        self.cp_len: int = 9
        self.scrambler_seed: int = 0x00_0001
        self.data_w: int = 8
        self.mod_order: int = 8  # set to RTL MOD_ORDER; controls payload bit width

    async def body(self) -> None:
        mask = (1 << self.mod_order) - 1  # was: (1 << self.data_w) - 1
        item = NrChainSeqItem()
        item.payload = [random.randint(0, mask) for _ in range(self.n_fft)]
        item.cp_len = self.cp_len
        item.scrambler_seed = self.scrambler_seed
        item.data_w = self.data_w
        await self.start_item(item)
        await self.finish_item(item)


class SeedSweepLoopbackSeq(uvm_sequence):
    """
    Same fixed payload, one block per seed in scrambler_seeds.

    Same-payload / varying-seed regression: every recovered output must equal
    the original payload despite different on-the-wire representations.
    """

    def __init__(self, name: str = "SeedSweepLoopbackSeq") -> None:
        super().__init__(name)
        self.payload_len: int = 64
        self.cp_len: int = 9
        self.data_w: int = 8
        self.mod_order: int = 8  # set to RTL MOD_ORDER; controls payload bit width
        self.scrambler_seeds: list[int] = [0x00_0001, 0x00_0003, 0xAB_CDEF, 0xFF_FFFF]

    async def body(self) -> None:
        mask = (1 << self.mod_order) - 1  # was: (1 << self.data_w) - 1
        payload = [random.randint(0, mask) for _ in range(self.payload_len)]
        for seed in self.scrambler_seeds:
            item = NrChainSeqItem()
            item.payload = list(payload)  # identical payload each time
            item.cp_len = self.cp_len
            item.scrambler_seed = seed
            item.data_w = self.data_w
            await self.start_item(item)
            await self.finish_item(item)


# ---------------------------------------------------------------------------
# Virtual sequences
# ---------------------------------------------------------------------------


class NrChainVirtualSeqBase(uvm_sequence):
    """
    Base class for nr_chain virtual sequences.

    tx_seqr resolves to the NrChainVirtualSequencer's tx_sequencer handle,
    which is wired during NrChainEnv.connect_phase. Safe to use only from
    run_phase (i.e. inside body()).
    """

    @property
    def tx_seqr(self):
        return self.sequencer.tx_sequencer


class DefaultLoopbackVSeq(NrChainVirtualSeqBase):
    """count random transport blocks at fixed cp_len and scrambler_seed."""

    def __init__(self, name: str = "DefaultLoopbackVSeq") -> None:
        super().__init__(name)
        self.payload_len: int = 64
        self.cp_len: int = 9
        self.scrambler_seed: int = 0x00_0001
        self.data_w: int = 8
        self.mod_order: int = 8  # propagated to inner sequence
        self.count: int = 16

    async def body(self) -> None:
        seq = MultiBlockLoopbackSeq("multi_blk")
        seq.payload_len = self.payload_len
        seq.cp_len = self.cp_len
        seq.scrambler_seed = self.scrambler_seed
        seq.data_w = self.data_w
        seq.mod_order = self.mod_order  # propagate
        seq.count = self.count
        await seq.start(self.tx_seqr)


class VaryingCpVSeq(NrChainVirtualSeqBase):
    """One block per CP length in cp_lens."""

    def __init__(self, name: str = "VaryingCpVSeq") -> None:
        super().__init__(name)
        self.payload_len: int = 64
        self.scrambler_seed: int = 0x00_0001
        self.data_w: int = 8
        self.mod_order: int = 8  # propagated to inner sequence
        self.cp_lens: list[int] = [0, 4, 8, 12, 16]

    async def body(self) -> None:
        seq = VaryingCpLoopbackSeq("varying_cp")
        seq.payload_len = self.payload_len
        seq.scrambler_seed = self.scrambler_seed
        seq.data_w = self.data_w
        seq.mod_order = self.mod_order  # propagate
        seq.cp_lens = self.cp_lens
        await seq.start(self.tx_seqr)


class SeedSweepVSeq(NrChainVirtualSeqBase):
    """One block per seed in scrambler_seeds, same payload each time."""

    def __init__(self, name: str = "SeedSweepVSeq") -> None:
        super().__init__(name)
        self.payload_len: int = 64
        self.cp_len: int = 9
        self.data_w: int = 8
        self.mod_order: int = 8  # propagated to inner sequence
        self.scrambler_seeds: list[int] = [0x00_0001, 0x00_0003, 0xAB_CDEF, 0xFF_FFFF]

    async def body(self) -> None:
        seq = SeedSweepLoopbackSeq("seed_sweep")
        seq.payload_len = self.payload_len
        seq.cp_len = self.cp_len
        seq.data_w = self.data_w
        seq.mod_order = self.mod_order  # propagate
        seq.scrambler_seeds = self.scrambler_seeds
        await seq.start(self.tx_seqr)


class StressVSeq(NrChainVirtualSeqBase):
    """
    Three-phase stress: seed sweep -> varying CP -> multi back-to-back.

    Exercises the full set of parameter transitions the physical layer
    encounters across a 5G NR slot boundary.
    """

    def __init__(self, name: str = "StressVSeq") -> None:
        super().__init__(name)
        self.payload_len: int = 64
        self.cp_len: int = 9
        self.data_w: int = 8
        self.mod_order: int = 8  # propagated to all inner sequences
        self.scrambler_seeds: list[int] = [0x00_0001, 0x00_0003, 0xAB_CDEF, 0xFF_FFFF]
        self.cp_lens: list[int] = [0, 4, 8, 12, 16]
        self.multi_count: int = 32

    async def body(self) -> None:
        # Phase 1: seed sweep - isolates scrambler re-seed from CP logic
        seed_seq = SeedSweepLoopbackSeq("stress_seed")
        seed_seq.payload_len = self.payload_len
        seed_seq.cp_len = self.cp_len
        seed_seq.data_w = self.data_w
        seed_seq.mod_order = self.mod_order  # propagate
        seed_seq.scrambler_seeds = self.scrambler_seeds
        await seed_seq.start(self.tx_seqr)

        # Phase 2: varying CP - exercises cp_inserter/cp_remover reconfiguration
        cp_seq = VaryingCpLoopbackSeq("stress_cp")
        cp_seq.payload_len = self.payload_len
        cp_seq.scrambler_seed = self.scrambler_seeds[0]
        cp_seq.data_w = self.data_w
        cp_seq.mod_order = self.mod_order  # propagate
        cp_seq.cp_lens = self.cp_lens
        await cp_seq.start(self.tx_seqr)

        # Phase 3: saturate pipeline with back-to-back blocks
        multi_seq = MultiBlockLoopbackSeq("stress_multi")
        multi_seq.payload_len = self.payload_len
        multi_seq.cp_len = self.cp_len
        multi_seq.scrambler_seed = self.scrambler_seeds[0]
        multi_seq.data_w = self.data_w
        multi_seq.mod_order = self.mod_order  # propagate
        multi_seq.count = self.multi_count
        await multi_seq.start(self.tx_seqr)
