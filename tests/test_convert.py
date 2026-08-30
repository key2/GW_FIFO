"""Elaborate + convert-to-Verilog a matrix of FIFO configurations."""
import itertools
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from amaranth.back import verilog
from amaranth_fifo import Edc, Fifo, FifoTop

# Standalone EDC for every DSIZE and option combination.
for d in (1, 4, 11, 12, 26, 27, 32, 57, 58, 64):
    for en_rst, sync, force in itertools.product((False, True), repeat=3):
        if sync and not en_rst:
            continue
        e = Edc(dsize=d, en_reset=en_rst, reset_synchronization=sync,
                enable_force_error=force)
        verilog.convert(e, name="edc", ports=e.ports())
print("EDC conversion: OK")

# exfifo1..4 configuration (Big path, EBR/DSR/LUT, reset sync, counts)
for style in ("ebr", "dsr", "lut"):
    top = FifoTop(wdepth=128, wdsize=36, rdepth=32, rdsize=144,
                  asize=7, rasize=5, memory_style=style,
                  almost_empty_flag=True, empty_th_mode="static_single", aempt=1,
                  almost_full_flag=True, full_th_mode="static_single", afull=1,
                  count_w=True,
                  en_reset=True, reset_synchronization=True)
    v = verilog.convert(top, name="fifo_top", ports=top.ports())
print("exfifo1-4 configuration: OK")

# Depth-ratio x reset x fwft x output-reg matrix
shapes = [
    dict(wdepth=16, wdsize=8, rdepth=16, rdsize=8),    # equal
    dict(wdepth=32, wdsize=4, rdepth=8, rdsize=16),    # big
    dict(wdepth=8, wdsize=16, rdepth=32, rdsize=4),    # small
]
resets = [
    dict(),
    dict(en_reset=True),
    dict(en_reset=True, reset_synchronization=True),
]
for shape, rst, fwft, oreg, ctrl in itertools.product(
        shapes, resets, (False, True), (False, True), (False, True)):
    f = Fifo(**shape, **rst, fwft=fwft, en_output_reg=oreg, ctrl_by_rden=ctrl)
    verilog.convert(f, name="fifo", ports=f.ports())
print("depth/reset/fwft/output-reg matrix: OK")

# Threshold modes
for emode in ("static_single", "static_dual", "dynamic_single", "dynamic_dual"):
    for fmode in ("static_single", "static_dual", "dynamic_single", "dynamic_dual"):
        f = Fifo(wdepth=64, wdsize=8, rdepth=64, rdsize=8,
                 almost_empty_flag=True, empty_th_mode=emode,
                 aempt=2, assert_empty_th=2, deassert_empty_th=4,
                 almost_full_flag=True, full_th_mode=fmode,
                 afull=60, assert_full_th=60, deassert_full_th=58,
                 count_w=True, count_r=True)
        verilog.convert(f, name="fifo", ports=f.ports())
print("threshold modes: OK")

# ECC configurations
for dsize in (1, 8, 36, 64):
    for rst in resets:
        for force in (False, True):
            f = Fifo(wdepth=16, wdsize=dsize, rdepth=16, rdsize=dsize,
                     en_ecc=True, enable_force_error=force, **rst)
            verilog.convert(f, name="fifo", ports=f.ports())
print("ECC configurations: OK")

print("All conversions OK")
