"""Amaranth HDL equivalent of the Gowin FIFO IP found in FIFO/data/.

- :class:`Edc`     <-> edc.v      (SECDED error detection and correction)
- :class:`Fifo`    <-> fifo.v     (dual-clock FIFO core)
- :class:`FifoTop` <-> fifo_top.v (top-level wrapper)
"""

from .edc import Edc, edc_pwidth, hamming_positions
from .fifo import Fifo
from .fifo_top import FifoTop
from .soc_fifos import fifo_top_128to32, fifo_top_32to128

__all__ = ["Edc", "Fifo", "FifoTop", "edc_pwidth", "hamming_positions",
           "fifo_top_128to32", "fifo_top_32to128"]
