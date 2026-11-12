# verif/nr_chain/sequences.py

from __future__ import annotations

import random

from pyuvm import uvm_sequence

from verif.nr_chain.seq_item import NrChainSeqItem

# ---------------------------------------------------------------------------
# Primitive sequences
# ---------------------------------------------------------------------------


class MultiBlockLoopbackSeq(uvm_sequence):
    """
    Count transport blocks of payload_len random bytes, driven back-to-back.

    payload_len must be a non-zero multiple of N_FFT (see NrChainDriver).
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
        mask = (1 << self.mod_order) - 1
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

    cp_len is a per-block sideband: the driver presents it before each block and holds
    it until the block leaves the RX chain, so TX cp_inserter and RX cp_remover always
    see the same value. Exercises runtime cp_len reconfiguration between blocks
    (including the cp_len=0 passthrough). It does not model a per-symbol CP pattern
    within a block.
    """

    def __init__(self, name: str = "VaryingCpLoopbackSeq") -> None:
        super().__init__(name)
        self.payload_len: int = 64
        self.scrambler_seed: int = 0x00_0001
        self.data_w: int = 8
        self.mod_order: int = 8  # set to RTL MOD_ORDER; controls payload bit width
        self.cp_lens: list[int] = [0, 4, 8, 12, 16]

    async def body(self) -> None:
        mask = (1 << self.mod_order) - 1
        for cp_len in self.cp_lens:
            item = NrChainSeqItem()
            item.payload = [random.randint(0, mask) for _ in range(self.payload_len)]
            item.cp_len = cp_len
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
        mask = (1 << self.mod_order) - 1
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


class MultiSymbolBlockLoopbackSeq(uvm_sequence):
    """
    One transport block spanning multiple OFDM symbols
    (payload_len = n_symbols * n_fft). n_fft must match the RTL N_FFT.

    The other sequences use payload_len == n_fft (one symbol per block), which
    leaves two behaviours unexercised:

      - nr_tx_chain.sv: with more input bytes still arriving for the same block,
        s_axis_tready must drop (sym_hold / sym_ready=0) while cp_inserter emits
        symbol N, then resume for symbol N+1.
      - nr_rx_chain.sv: the descrambler must reseed only on the block-start tuser
        and keep its LFSR running across intra-block symbol boundaries. A spurious
        reseed there corrupts every byte after the first symbol.

    n_symbols=3 gives two intra-block boundaries for each. The scoreboard also
    checks the loopback sample count and that tuser fires exactly once, at
    sample index cp_len.
    """

    def __init__(self, name: str = "MultiSymbolBlockLoopbackSeq") -> None:
        super().__init__(name)
        self.n_fft: int = 64
        self.n_symbols: int = 3
        self.cp_len: int = 9
        self.scrambler_seed: int = 0x00_0001
        self.data_w: int = 8
        self.mod_order: int = 8

    async def body(self) -> None:
        mask = (1 << self.mod_order) - 1
        item = NrChainSeqItem()
        item.payload = [random.randint(0, mask) for _ in range(self.n_fft * self.n_symbols)]
        item.cp_len = self.cp_len
        item.scrambler_seed = self.scrambler_seed
        item.data_w = self.data_w
        await self.start_item(item)
        await self.finish_item(item)


class MultiSymbolBlockVSeq(NrChainVirtualSeqBase):
    """Virtual sequence wrapper for MultiSymbolBlockLoopbackSeq."""

    def __init__(self, name: str = "MultiSymbolBlockVSeq") -> None:
        super().__init__(name)
        self.n_fft: int = 64
        self.n_symbols: int = 3
        self.cp_len: int = 9
        self.scrambler_seed: int = 0x00_0001
        self.data_w: int = 8
        self.mod_order: int = 8

    async def body(self) -> None:
        seq = MultiSymbolBlockLoopbackSeq("multi_sym_inner")
        seq.n_fft = self.n_fft
        seq.n_symbols = self.n_symbols
        seq.cp_len = self.cp_len
        seq.scrambler_seed = self.scrambler_seed
        seq.data_w = self.data_w
        seq.mod_order = self.mod_order
        await seq.start(self.tx_seqr)
