# FPGA CI/CD Toolchain Demo

[![Lint](https://github.com/rothej/fpga-cicd-toolchain-demo/actions/workflows/lint.yml/badge.svg)](https://github.com/rothej/fpga-cicd-toolchain-demo/actions/workflows/lint.yml)
[![Unit Sim](https://github.com/rothej/fpga-cicd-toolchain-demo/actions/workflows/unit_sim.yml/badge.svg)](https://github.com/rothej/fpga-cicd-toolchain-demo/actions/workflows/unit_sim.yml)
[![Integration Sim](https://github.com/rothej/fpga-cicd-toolchain-demo/actions/workflows/integration_sim.yml/badge.svg)](https://github.com/rothej/fpga-cicd-toolchain-demo/actions/workflows/integration_sim.yml)

A complete SystemVerilog development environment demonstrating [Verible](https://github.com/chipsalliance/verible), [Verilator](https://www.veripool.org/verilator/), [cocotb](https://www.cocotb.org/), and [pyuvm](https://github.com/pyuvm/pyuvm) working together with a pre-commit linting and formatting pipeline.

The DUT is a parameterizable 5G NR physical-layer chain implemented across multiple SystemVerilog modules under `rtl/`. This includes CRC generation/checking, scrambling, QAM mapping/demapping, and cyclic prefix insertion/removal.

## Quick Start

### First Time
Install:
```
sudo apt install direnv expect
```

Run:
```bash
make setup
direnv allow
```

### Full Test Pass
```bash
# Static analysis: Verible lint/format + ruff + mypy
make lint
# Python reference model tests
make test
# All unit TBs + nr_chain integration loopback
make sim
```

### Waveform Generation
```bash
make waves MODULE=crc_engine
```
Replace module as appropriate.

## Folder Structure

```
fpga-cicd-toolchain-demo/
├── .github/
│ └── workflows/
│ ├── ci.yml                # Orchestrator
│ ├── lint.yml              # Verible lint + format check
│ ├── unit_sim.yml          # Matrix over 7 unit TBs (needs: lint)
│ └── integration_sim.yml   # nr_chain loopback (needs: unit_sim)
├── rtl/                    # RTL source files (SystemVerilog)
│ ├── crc_pkg.sv            # CRC polynomial package
│ ├── crc_engine.sv         # CRC generator
│ ├── crc_checker.sv        # CRC verifier
│ ├── scrambler.sv          # Gold-code scrambler
│ ├── qam_mapper.sv         # QAM modulator (QPSK-256QAM)
│ ├── qam_demapper.sv       # QAM soft demapper
│ ├── cp_inserter.sv        # Cyclic prefix insertion
│ ├── cp_remover.sv         # Cyclic prefix removal
│ ├── nr_tx_chain.sv        # TX integration wrapper
│ └── nr_rx_chain.sv        # RX integration wrapper
├── verif/                  # pyuvm testbenches (one subdir per module)
│ ├── common/               # Shared UVM components
│ │ ├── axis_agent.py       # Reusable AXI4-Stream agent
│ │ ├── base_test.py        # Base test class
│ │ └── nr_ref_model.py     # Golden reference model
│ ├── crc_engine/
│ ├── crc_checker/
│ ├── scrambler/
│ ├── qam_mapper/
│ ├── qam_demapper/
│ ├── cp_inserter/
│ ├── cp_remover/
│ └── nr_chain/             # Integration TB (virtual sequencer)
├── sim/                    # Per-module Makefiles
│ ├── common.mk             # Shared Verilator/cocotb config
│ ├── crc_engine/
│ ├── crc_checker/
│ ├── scrambler/
│ ├── qam_mapper/
│ ├── qam_demapper/
│ ├── cp_inserter/
│ ├── cp_remover/
│ └── nr_chain/
├── scripts/
│ ├── setup.sh              # Top-level setup entrypoint
│ ├── setup_tools.sh        # Handles EDA tool installation
│ ├── setup_verible.sh      # Downloads and installs Verible
│ └── setup_verilator.sh    # Builds Verilator from source
├── .envrc                  # direnv: activates venv and adds .tools/ to PATH
├── .pre-commit-config.yaml # Pre-commit hook definitions
├── pyproject.toml          # Python project metadata, tool config (mypy, ruff)
├── Makefile                # Project automation (sim, lint, format, waves, clean)
└── .verible-lint.rules     # Verible lint rule configuration
```

## Tools

### Required

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.12+ | cocotb testbenches and pyuvm |
| Verilator | 5.040 (built from source) | SystemVerilog simulation backend |
| Verible | Latest release | SV formatting and linting |
| direnv | Any | Automatic venv activation per-directory |
| gtkwave | >= 3.3 | Waveform visualization |

> Verilator and Verible are installed into `.tools/` by `scripts/setup.sh` - no system-wide installation required. This is good practice as different repos and projects may use a different set of dependencies/versions.

### Python Dependencies

Managed via `pyproject.toml`. Installed automatically during setup.

| Package | Purpose |
|---|---|
| cocotb | Hardware co-simulation framework |
| cocotb-tools | Verilator runner integration |
| pyuvm | Python UVM framework |
| ruff | Python linter and formatter |
| mypy | Static type checker |
| pre-commit | Git hook manager |

## Setup

For makefile functionality, run:
```
sudo apt install expect
```
This package lets the terminal print green/red colors while exporting plain text to log files.

### Method 1: With direnv (Recommended)

[direnv](https://direnv.net/) automatically activates the Python virtual environment and updates `PATH` with `.tools/` binaries whenever you `cd` into the repository. No manual `source .venv/bin/activate` needed.

Install direnv system-wide if not already present:
```bash
sudo apt install direnv
echo 'eval "$(direnv hook bash)"' >> ~/.bashrc
source ~/.bashrc
```

Then from within the cloned repository:
```bash
make setup
direnv allow
```

`make setup` will:
1. Create and populate `.venv/`
2. Install Python dependencies and pre-commit hooks
3. Build Verilator 5.040 from source into `.tools/verilator/`
4. Download the Verible release binary into `.tools/verible/`

After `direnv allow`, your shell prompt will automatically activate the environment on every subsequent `cd` into the repo.

### Method 2: Without direnv

```bash
make setup
source .venv/bin/activate
export PATH="$PWD/.tools/verilator/bin:$PWD/.tools/verible/bin:$PATH"
```

> **Note:** Without direnv, you will need to re-run the `source` and `export` lines in each new shell session.

## Makefile Targets

Run `make help` to print all targets. All make commands output logs into the `logs/` folder.

| Target | Description |
|---|---|
| `make setup` | First-time bootstrap (after `direnv allow`) |
| `make sim` | Run all unit TBs + nr_chain integration TB |
| `make unit-sim` | Run all unit TBs via cocotb/Verilator |
| `make integration-sim` | Run nr_chain loopback TB |
| `make sim-<module>` | Run a single unit TB e.g. `make sim-crc_engine` |
| `make test` | pytest verif/common/tests/ (no simulator) |
| `make waves MODULE=<m>` | Run sim with FST dump + open GTKWave |
| `make lint` | Run all pre-commit hooks against all files |
| `make format` | Auto-format SV files (Verible) and Python files (ruff) |
| `make clean` | Remove all build, sim, and cache artifacts |
| `make clean-sim` | Remove only simulation artifacts (`sim_build/`, `*.fst`, `*.vcd`) |
| `make clean-tools` | Remove installed tools (`.tools/`) |

## Running the Simulation

```bash
make sim
```

Runs all unit TBs followed by the nr_chain loopback integration TB. Individual modules can be ran by using `make sim-scrambler`, `make sim-crc_engine` etc.

### Waveforms

```bash
make waves MODULE=crc_engine
```

Runs the simulation for the specified module with FST tracing enabled and opens the dump in GTKWave. Requires `gtkwave`:

```bash
sudo apt-get install -y gtkwave
```

### Coverage

Verilator is invoked with --coverage (line, toggle, and branch) on every sim run. Functional coverage is collected per-module by a uvm_coverage_collector component via pyuvm.

### UVM Architecture

Each unit TB follows the same layered structure:

uvm_test
└── uvm_env
    ├── TX uvm_agent (AXI4-Stream)       # verif/common/axis_agent.py
    │   ├── Driver
    │   ├── Monitor -> uvm_analysis_port
    │   └── uvm_sequencer
    ├── RX uvm_agent (AXI4-Stream)       # verif/common/axis_agent.py
    │   ├── Driver
    │   ├── Monitor -> uvm_analysis_port
    │   └── uvm_sequencer
    ├── uvm_scoreboard
    │   └── uvm_tlm_analysis_fifo        # TX monitor -> scoreboard -> check
    └── uvm_coverage_collector

The nr_chain integration TB adds a virtual sequencer at the top level to coordinate TX and RX stimulus across the full loopback path.

All configuration is passed via `ConfigDB.set/get`, not constructor arguments. Factory registration uses `@pyuvm.test` and `@pyuvm.uvm_component_utils`.

## Pre-Commit Hooks

Hooks run automatically on `git commit`. To run manually against all files:
```bash
make lint
```

If a hook auto-fixes a file (e.g. trailing whitespace, formatting), the commit will be aborted. `git add` the fixed files and commit again.

| Hook | Tool | Scope |
|---|---|---|
| Trailing whitespace, EOF, YAML, TOML, merge conflicts, line endings | pre-commit-hooks | All files |
| Python linting and import sorting | ruff-check (--fix) | `*.py` |
| Python formatting | ruff-format | `*.py` |
| Static type checking | mypy | `verif/` |
| SV auto-formatting | verible-verilog-format | `*.sv`, `*.v` |
| SV linting | verible-verilog-lint | `*.sv`, `*.v` |

## License

MIT License (MIT) - see [LICENSE](LICENSE) file for details.

## Author

[Joshua Rothe](https://joshrothe.us)
