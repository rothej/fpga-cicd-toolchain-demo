# FPGA CI/CD Toolchain Demo

[![CI](https://github.com/rothej/fpga-cicd-toolchain-demo/actions/workflows/ci.yml/badge.svg)](https://github.com/rothej/fpga-cicd-toolchain-demo/actions/workflows/ci.yml)

A minimal but complete SystemVerilog development environment demonstrating [Verible](https://github.com/chipsalliance/verible), [Verilator](https://www.veripool.org/verilator/), and [cocotb](https://www.cocotb.org/) working together with a pre-commit linting and formatting pipeline.

The DUT is a parameterizable synchronous counter (`rtl/counter.sv`), included as a simple example to demonstrate toolchain functionality.

## Folder Structure

```
fpga-cicd-toolchain-demo/
├── .github/
│   └── workflows/          # CI/CD workflows
├── rtl/                    # RTL source files (SystemVerilog)
│   └── counter.sv          # Parameterizable synchronous counter (DUT)
├── tb/                     # Cocotb testbench
│   └── test_counter.py     # 8-test suite covering all counter behaviors
├── scripts/
│   ├── setup.sh            # Top-level setup entrypoint
│   ├── setup_tools.sh      # Orchestrates EDA tool installation
│   ├── setup_verible.sh    # Downloads and installs Verible
│   └── setup_verilator.sh  # Builds Verilator 5.036 from source
├── .envrc                  # direnv: activates venv and adds .tools/ to PATH
├── .pre-commit-config.yaml # Pre-commit hook definitions
├── pyproject.toml          # Python project metadata, tool config (mypy, black, isort)
├── Makefile                # Project automation (sim, lint, format, waves, clean)
└── .verible-lint.rules     # Verible lint rule configuration
```

## Tools

### Required

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.12+ | Cocotb testbench and runner |
| Verilator | 5.040 (built from source) | SystemVerilog simulation backend |
| Verible | Latest release | SV formatting and linting |
| direnv | Any | Automatic venv activation per-directory |
| gtkwave | >= 3.3 | Waveform visualization |

> Verilator and Verible are installed into `.tools/` by `scripts/setup.sh` — no system-wide installation required. This is good practice as different repos and projects may use a different set of dependencies/versions.

### Python Dependencies

Managed via `pyproject.toml`. Installed automatically during setup.

| Package | Purpose |
|---|---|
| cocotb | Hardware co-simulation framework |
| cocotb-tools | Verilator runner integration |
| black | Python formatter |
| isort | Import sorter |
| mypy | Static type checker |
| pre-commit | Git hook manager |

## Setup

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
3. Build Verilator 5.036 from source into `.tools/verilator/`
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

Run `make help` to print all targets.

| Target | Description |
|---|---|
| `make setup` | First-time bootstrap (after `direnv allow`) |
| `make sim` / `make test` | Compile and run all cocotb tests |
| `make waves` | Run sim then open FST dump in GTKWave |
| `make lint` | Run all pre-commit hooks against all files |
| `make format` | Auto-format SV files (Verible) and Python files (black, isort) |
| `make clean` | Remove all build, sim, and cache artifacts |
| `make clean-sim` | Remove only simulation artifacts (`sim_build/`, `*.fst`, `*.vcd`) |
| `make clean-tools` | Remove installed tools (`.tools/`) |

## Running the Simulation

```bash
make sim
```

This compiles `rtl/counter.sv` with Verilator and runs all 8 cocotb tests.

### Waveforms

```bash
make waves
```

Runs the simulation and opens the FST dump in GTKWave. Requires `gtkwave`:

```bash
sudo apt-get install -y gtkwave
```

### Test Coverage

| Test | Behavior Verified |
|---|---|
| `test_reset_clears_outputs` | Reset overrides `en`, drives `count` and `overflow` to 0 |
| `test_count_increments_when_enabled` | Count increments by 1 per rising edge when `en=1` |
| `test_count_holds_when_disabled` | Count holds its value when `en=0` |
| `test_overflow_timing` | `overflow` is registered — pulses one cycle after `count` reaches MAX |
| `test_overflow_clears_when_disabled` | Deasserting `en` while `overflow=1` clears it on the next edge |
| `test_reset_mid_count` | Reset clears state from any mid-run value, not just from initial state |
| `test_multiple_overflow_cycles` | Overflow pulses correctly and consistently across 3 consecutive wraps |
| `test_reenable_resumes_from_held_value` | Re-enabling resumes from the held value, not from zero |

## Pre-Commit Hooks

Hooks run automatically on `git commit`. To run manually against all files:
```bash
make lint
```

If a hook auto-fixes a file (e.g. trailing whitespace, formatting), the commit will be aborted. `git add` the fixed files and commit again.

| Hook | Tool | Scope |
|---|---|---|
| Trailing whitespace, EOF, YAML, merge conflicts, line endings | pre-commit-hooks | All files |
| Python formatting | black | `*.py` |
| Import sorting | isort | `*.py` |
| Static type checking | mypy | `tb/` |
| SV auto-formatting | verible-verilog-format | `*.sv`, `*.v` |
| SV linting | verible-verilog-lint | `*.sv`, `*.v` |

## License

MIT License (MIT) — see [LICENSE](LICENSE) file for details.

## Author

[Joshua Rothe](https://joshrothe.us)
