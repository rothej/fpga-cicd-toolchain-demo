# verif/common/base_test.py

"""
verif/common/base_test.py

Base test class for all pyuvm testbenches in fpga-cicd-toolchain-demo.

Provides clock generation, synchronous active-low reset, an optional
drain window, and a pre_body() hook to concrete subclasses via the
body() template method.  Subclasses are decorated with @pyuvm.test();
BaseTest itself is not a runnable test.

Required ConfigDB key:
    "dut"          : cocotb SimHandle - set by the cocotb entry point before
                                        uvm_root starts the test

Optional ConfigDB keys (defaults in parentheses):
    "clk_period"   : int (10) - clock period in nanoseconds
    "rst_cycles"   : int (5)  - number of cycles to hold rst_n low
    "drain_cycles" : int (0)  - idle cycles after body() before dropping
                                the objection; set per-TB to cover pipeline
                                depth (e.g. 32 for unit TBs, 4000 for
                                nr_chain integration)
"""

from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge
from pyuvm import ConfigDB, uvm_test

from verif.common.config_utils import _cfg

__all__ = ["BaseTest"]


class BaseTest(uvm_test):
    """
    Abstract base test.

    Lifecycle:
        build_phase  - retrieves dut, clk_period, rst_cycles, drain_cycles
        run_phase    - raises objection, calls _init_dut(), pre_body(),
                       body(), optional drain, then drops objection
        _init_dut()  - starts clock coroutine, asserts/de-asserts rst_n
        pre_body()   - no-op; override to set DUT-specific input signals
                       to their idle state after reset and before stimulus
        body()       - no-op; override in concrete subclasses
    """

    def build_phase(self) -> None:
        self.dut = ConfigDB().get(self, "", "dut")
        self.clk_period: int = _cfg(self, "clk_period", 10)
        self.rst_cycles: int = _cfg(self, "rst_cycles", 5)
        self.drain_cycles: int = _cfg(self, "drain_cycles", 0)

    async def run_phase(self) -> None:
        self.raise_objection()
        await self._init_dut()
        await self.pre_body()
        await self.body()
        if self.drain_cycles:
            await ClockCycles(self.dut.clk, self.drain_cycles)
        self.drop_objection()

    async def _init_dut(self) -> None:
        """Start clock and drive synchronous active-low reset."""
        cocotb.start_soon(Clock(self.dut.clk, self.clk_period, unit="ns").start())
        self.dut.rst_n.value = 0
        await ClockCycles(self.dut.clk, self.rst_cycles)
        self.dut.rst_n.value = 1
        await RisingEdge(self.dut.clk)

    async def pre_body(self) -> None:
        """
        Override to drive DUT-specific input signals to their idle state.

        Called once, after reset de-asserts and before body() starts.
        Useful for signals that drivers initialise in run_phase but that
        need to be explicitly idle before the first sequence item is sent.
        """

    async def body(self) -> None:
        """
        Override in concrete test classes to run test-specific sequences.

        Called after _init_dut() and pre_body(), while the run_phase
        objection is raised.
        """
