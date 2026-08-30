# GW_FIFO

A parametric [Amaranth HDL](https://github.com/amaranth-lang/amaranth) port of the
**Gowin dual-clock FIFO IP** (`FIFO HS` / `fifo_top`), including its SECDED ECC
encoder/decoder. Every compile-time `` `define `` and parameter of the original
Verilog IP is exposed as a Python constructor argument, and the generated logic is
behaviorally **cycle-exact** with the original.

```
amaranth_fifo/
├── edc.py        <->  edc.v       SECDED (Hamming + overall parity) encoder/decoder
├── fifo.py       <->  fifo.v     dual-clock FIFO core (all options)
├── fifo_top.py   <->  fifo_top.v top-level wrapper + Verilog generation CLI
└── soc_fifos.py                  drop-in configs used by the Gowin RiscV AE350 SOC
generated/                        pre-generated Verilog for the two AE350 SOC FIFOs
tests/                            Amaranth simulator tests (no external files needed)
verify/                           equivalence-check harness against the Gowin IP
```

## Features

- Asynchronous (dual-clock) FIFO with gray-code pointer CDC
- Asymmetric read/write widths and depths (`WDEPTH×WDSIZE == RDEPTH×RDSIZE`,
  e.g. 64×128 → 256×32 or 256×36 → 64×144)
- Standard or FWFT (first-word fall-through) read semantics
- `Empty`/`Full` plus programmable `Almost_Empty`/`Almost_Full` flags:
  static or dynamic thresholds, single threshold or dual (set/clear hysteresis)
- Write/read data counts (`Wnum`, `Rnum`)
- Optional output register, optionally gated by `RdEn`
- Single reset with built-in falling-edge 2-FF synchronizers
  (`Reset_Synchronization`), dual `WrReset`/`RdReset`, or no reset
- SECDED ECC (`En_ECC`, DSIZE 1..64) with 2-bit error status and optional
  error-injection walk-through (`Enable_force_error`)

## Requirements

- Python ≥ 3.9, `amaranth >= 0.5`
- Optional: [Icarus Verilog](http://iverilog.icarus.com/) for the `verify/` harness

## Usage

```python
from amaranth_fifo import Fifo, FifoTop, Edc

fifo = FifoTop(
    wdepth=256, wdsize=36, rdepth=64, rdsize=144,   # 36-bit -> 144-bit
    en_reset=True, reset_synchronization=True,
    fwft=True, count_w=True,
    almost_empty_flag=True, empty_th_mode="static_single", aempt=24,
    almost_full_flag=True,  full_th_mode="static_single", afull=200,
)
# Ports keep the Verilog names: fifo.Data, fifo.WrClk, fifo.RdClk, fifo.WrEn,
# fifo.RdEn, fifo.Q, fifo.Empty, fifo.Full, fifo.Wnum, fifo.Almost_*, ...
```

Generate Verilog from the command line:

```sh
python -m amaranth_fifo.fifo_top --wdepth 128 --wdsize 36 --rdepth 32 --rdsize 144 \
    --memory-style ebr --almost-empty static_single --aempt 1 \
    --almost-full static_single --afull 1 --en-reset --reset-synchronization \
    -o fifo_top.v
```

## Parameter mapping (Gowin IP -> constructor arguments)

| Verilog parameter / `define`          | Constructor argument |
|---------------------------------------|----------------------|
| `WDEPTH` / `WDSIZE`                   | `wdepth` / `wdsize` |
| `RDEPTH` / `RDSIZE`                   | `rdepth` / `rdsize` |
| `ASIZE` / `RASIZE`                    | `asize` / `rasize` (default: log2 of depth) |
| `AEMPT` / `AFULL`                     | `aempt` / `afull` |
| `AssertEmptyTh` / `DeassertEmptyTh`   | `assert_empty_th` / `deassert_empty_th` |
| `AssertFullTh` / `DeassertFullTh`     | `assert_full_th` / `deassert_full_th` |
| `EBR_BASED` / `DSR_BASED` / `LUT_BASED` | `memory_style="ebr"/"dsr"/"lut"` |
| `En_Reset`                            | `en_reset` |
| `Reset_Synchronization`               | `reset_synchronization` |
| `Al_Empty_Flag` + `Empty_{S,D}_{Single,Dual}_Th` | `almost_empty_flag` + `empty_th_mode` |
| `Al_Full_Flag` + `Full_{S,D}_{Single,Dual}_Th`   | `almost_full_flag` + `full_th_mode` |
| `Count_W` / `Count_R`                 | `count_w` / `count_r` |
| `En_ECC`                              | `en_ecc` |
| `Enable_force_error`                  | `enable_force_error` |
| `En_Output_Reg` / `Ctrl_By_RdEn`      | `en_output_reg` / `ctrl_by_rden` |
| `FWFT`                                | `fwft` |

`empty_th_mode`/`full_th_mode` take `"static_single"`, `"static_dual"`,
`"dynamic_single"` or `"dynamic_dual"` (dynamic modes add threshold input ports).

## The ECC core (`Edc`)

The original `edc.v` hardcodes ~18 000 lines of per-DSIZE equations. They all
implement one scheme: a Hamming SECDED code in which data bit *i* sits at the
*i*-th non-power-of-two Hamming position (3, 5, 6, 7, 9, ...), with a final
overall-parity check bit. `Edc` generates these equations algorithmically for
any DSIZE in 1..64 and reproduces the original exactly — including the
DSIZE=32 quirk where the invalid-single-error threshold is 39 instead of 38.

Error status (registered on `RdClk`): `00` no error / corrected, `01` single
bit error (corrected), `10` double bit error, `11` invalid single-error
syndrome.

## AE350 SOC drop-in FIFOs

`soc_fifos.py` provides the two FIFO configurations used by the Gowin
*RiscV AE350 SOC* reference design DDR3 datapath, recovered from its
GowinSynthesis netlists (`fifo_top_128to32.v`, `fifo_top_32to128.v`):

| | `fifo_top_128to32` (DDR3 read) | `fifo_top_32to128` (DDR3 write) |
|---|---|---|
| Geometry | 64×128 → 256×32 | 256×36 → 64×144 |
| Mode | standard | FWFT |
| Flags | `Almost_Full` (AFULL=48) | `Almost_Empty` (AEMPT=24), `Almost_Full` (AFULL=200), `Wnum` |
| Reset | sync-release single `Reset` | same |

Pre-generated Verilog with identical top-level module names/ports is in
`generated/`; regenerate with:

```sh
python -m amaranth_fifo.soc_fifos <output_directory>
```

## Validation

- **`verify/verify_edc.py`** parses the original `edc.v` and checks that the
  algorithmic generator reproduces every equation, correction-mask entry and
  error threshold of **all 64 DSIZE branches** (pass).
- **`tests/`** (Amaranth simulator, self-contained): EDC encode/decode with
  single/double error injection across 15 widths; FIFO read/write order for
  equal/big/small depth ratios; FWFT; output-register modes; ECC data
  integrity; Full/Almost flags; counts; asynchronous reset assert/recovery;
  plus an elaboration/conversion matrix of ~200 option combinations.
- **`verify/tb_cmp_*.v`** co-simulate the AE350 SOC Gowin netlists against the
  generated RTL **cycle-exactly** (iverilog, behavioral models of the Gowin
  LUT/DFF/ALU/SDPB/SDPX9B primitives in `verify/gowin_prims.v`, asynchronous
  write/read clocks, near-empty / mid / near-full stimulus): **0 mismatches**
  on `Empty`/`Full`/`Almost_*`/`Wnum`/`Q`.

Run the self-contained tests:

```sh
python3 tests/test_edc_sim.py
python3 tests/test_fifo_sim.py
python3 tests/test_convert.py
```

The equivalence harness needs the original Gowin files (IP sources from
`<Gowin IDE>/ipcore/FIFO/data/` and/or the SOC netlists), which are **not**
redistributed in this repository:

```sh
python3 verify/verify_edc.py <path>/ipcore/FIFO/data/edc.v
python3 verify/gen_rtl.py 128to32 48 rtl_128to32.v
iverilog -g2005 -o cmp.vvp verify/gowin_prims.v verify/tb_cmp_128to32.v \
    rtl_128to32.v <path>/fifo_top_128to32.v && vvp cmp.vvp
```

## Notes and known deviations

- `memory_style` is accepted for interface parity; the Synplify
  `syn_ramstyle` attribute mapping is left to the synthesis tool.
- The memory read path is modeled as an async-read port plus an explicit
  enable-gated register (exactly matching the IP's BSRAM behavior); whether a
  synthesis flow merges it back into a block-RAM synchronous read port
  depends on the tool.
- ECC requires `wdepth == rdepth` and `memory_style="ebr"` (the only
  combination the original IP supports with consistent widths).
- Gowin quirks are reproduced deliberately, e.g. the `Ctrl_By_RdEn`
  output-register lag and the DSIZE=32 ECC threshold.

## Provenance

This is an independent behavioral re-implementation, in Amaranth, of the
interface and behavior of the Gowin FIFO IP, created for porting designs that
use that IP to Amaranth. No Gowin source code or netlists are included.
