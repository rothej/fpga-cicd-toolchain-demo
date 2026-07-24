# verif/cp_remover/sequences.py

from __future__ import annotations

import random

from pyuvm import uvm_sequence

from verif.common.config_utils import _cfg
from verif.cp_remover.seq_item import CpRemoverSeqItem


class RandomSingleSymbolSeq(uvm_sequence):
    """
    One packet of (cp_len + N_FFT) random samples at a fixed cp_len.

    ConfigDB keys: n_fft, cp_len, samp_w
    """

    async def body(self) -> None:
        n_fft = _cfg(self, "n_fft", 64)
        cp_len = _cfg(self, "cp_len", 9)
        samp_w = _cfg(self, "samp_w", 16)
        mask = (1 << samp_w) - 1

        item = CpRemoverSeqItem()
        item.full_samples = [random.randint(0, mask) for _ in range(cp_len + n_fft)]
        item.cp_len = cp_len
        item.samp_w = samp_w
        await self.start_item(item)
        await self.finish_item(item)


class MultiSymbolSeq(uvm_sequence):
    """
    count back-to-back packets, each (cp_len + N_FFT) random samples.

    Primary regression for inter-symbol contamination: no sample from the
    payload of packet N may appear in the output of packet N+1.

    ConfigDB keys: n_fft, cp_len, samp_w, count
    """

    async def body(self) -> None:
        n_fft = _cfg(self, "n_fft", 64)
        cp_len = _cfg(self, "cp_len", 9)
        samp_w = _cfg(self, "samp_w", 16)
        count = _cfg(self, "count", 16)
        mask = (1 << samp_w) - 1

        for _ in range(count):
            item = CpRemoverSeqItem()
            item.full_samples = [random.randint(0, mask) for _ in range(cp_len + n_fft)]
            item.cp_len = cp_len
            item.samp_w = samp_w
            await self.start_item(item)
            await self.finish_item(item)


class CountingPatternSeq(uvm_sequence):
    """
    One packet where full_samples[i] = i & mask.

    CP region  -> [0, 1, .., cp_len-1]                   (discarded)
    Payload    -> [cp_len, cp_len+1, .., cp_len+N_FFT-1] (expected output)

    The discard boundary is trivially verifiable on a waveform viewer:
    the first output beat must equal cp_len, not 0.

    ConfigDB keys: n_fft, cp_len, samp_w
    """

    async def body(self) -> None:
        n_fft = _cfg(self, "n_fft", 64)
        cp_len = _cfg(self, "cp_len", 9)
        samp_w = _cfg(self, "samp_w", 16)
        mask = (1 << samp_w) - 1

        item = CpRemoverSeqItem()
        item.full_samples = [i & mask for i in range(cp_len + n_fft)]
        item.cp_len = cp_len
        item.samp_w = samp_w
        await self.start_item(item)
        await self.finish_item(item)


class VaryingCpLenSeq(uvm_sequence):
    """
    One packet per cp_len value in the cp_lens list, driven back-to-back.

    Models the 5G NR slot structure: symbol 0 arrives with the extended CP,
    symbols 1-13 arrive with the normal CP. Exercises runtime cp_len
    reconfiguration between consecutive received packets.

    ConfigDB keys: n_fft, samp_w, cp_lens (list[int])
    """

    async def body(self) -> None:
        n_fft = _cfg(self, "n_fft", 64)
        samp_w = _cfg(self, "samp_w", 16)
        cp_lens = _cfg(self, "cp_lens", [0, 4, 8, 16])
        mask = (1 << samp_w) - 1

        for cp_len in cp_lens:
            item = CpRemoverSeqItem()
            item.full_samples = [random.randint(0, mask) for _ in range(cp_len + n_fft)]
            item.cp_len = cp_len
            item.samp_w = samp_w
            await self.start_item(item)
            await self.finish_item(item)


class ZeroCpSeq(uvm_sequence):
    """
    count packets with cp_len=0 - pure passthrough.

    Output must equal input verbatim; DUT must assert output tlast at beat
    N_FFT-1 without suppressing any input samples.

    ConfigDB keys: n_fft, samp_w, count
    """

    async def body(self) -> None:
        n_fft = _cfg(self, "n_fft", 64)
        samp_w = _cfg(self, "samp_w", 16)
        count = _cfg(self, "count", 8)
        mask = (1 << samp_w) - 1

        for _ in range(count):
            item = CpRemoverSeqItem()
            item.full_samples = [random.randint(0, mask) for _ in range(n_fft)]
            item.cp_len = 0
            item.samp_w = samp_w
            await self.start_item(item)
            await self.finish_item(item)


class MaxCpLenSeq(uvm_sequence):
    """
    Single packet with cp_len=CP_LEN_MAX.

    Stresses the discard counter at its maximum depth: the DUT must suppress
    exactly CP_LEN_MAX leading beats before emitting the first output sample.

    ConfigDB keys: n_fft, cp_len, samp_w
    """

    async def body(self) -> None:
        n_fft = _cfg(self, "n_fft", 64)
        cp_len = _cfg(self, "cp_len", 16)
        samp_w = _cfg(self, "samp_w", 16)
        mask = (1 << samp_w) - 1

        item = CpRemoverSeqItem()
        item.full_samples = [random.randint(0, mask) for _ in range(cp_len + n_fft)]
        item.cp_len = cp_len
        item.samp_w = samp_w
        await self.start_item(item)
        await self.finish_item(item)
