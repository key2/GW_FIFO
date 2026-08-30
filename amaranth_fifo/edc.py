"""Amaranth translation of ``FIFO/data/edc.v`` (Gowin FIFO ECC encoder/decoder).

The original Verilog hardcodes, for every DSIZE in 1..64, the equations of a
Hamming SECDED code in which data bit ``i`` is placed at the ``i``-th
non-power-of-two Hamming position (3, 5, 6, 7, 9, ...).  The last check bit is
an overall (double-error-detect) parity over data and the other check bits.
This module generates exactly the same equations algorithmically, so it is
parametrable for any DSIZE in 1..64 and produces the same logic as the
per-DSIZE ``generate`` branches of the Verilog.

Options (Verilog `defines -> constructor parameters):
    `En_Reset               -> en_reset
    `Reset_Synchronization  -> reset_synchronization
    `Enable_force_error     -> enable_force_error
Parameter DSIZE -> dsize.

Ports keep the Verilog names (RdClk, WrClk, Ein, Eout, P_out, Din, Dout,
P_in, error, and RST / Reset+RPReset / force_error depending on options).
"""

from functools import reduce
from operator import xor

from amaranth.hdl import (
    C,
    Cat,
    ClockDomain,
    ClockSignal,
    Elaboratable,
    Module,
    ResetSignal,
    Signal,
)

__all__ = ["Edc", "edc_pwidth", "hamming_positions", "single_error_threshold"]


def edc_pwidth(dsize):
    """PWIDTH localparam of edc.v (number of check bits incl. overall parity)."""
    if dsize == 1:
        return 3
    if 2 <= dsize <= 4:
        return 4
    if 5 <= dsize <= 11:
        return 5
    if 12 <= dsize <= 26:
        return 6
    if 27 <= dsize <= 57:
        return 7
    if 58 <= dsize <= 64:
        return 8
    raise ValueError(f"DSIZE must be in 1..64, not {dsize}")


def hamming_positions(dsize):
    """Hamming position of each data bit: the non-power-of-two integers >= 3."""
    positions = []
    p = 3
    while len(positions) < dsize:
        if p & (p - 1):  # not a power of two
            positions.append(p)
        p += 1
    return positions


def _xor(terms):
    return reduce(xor, terms)


def single_error_threshold(dsize):
    """Highest syndrome value (without its MSB) that edc.v accepts as a valid
    single-bit error.  This is the Hamming position of the last data bit,
    except for DSIZE == 32 where edc.v checks ``syndrome[5:3] >= 5`` which
    makes the effective threshold 39 instead of 38 (quirk replicated for
    exact equivalence)."""
    if dsize == 32:
        return 39
    return hamming_positions(dsize)[-1]


class Edc(Elaboratable):
    """SECDED encoder/decoder, equivalent to ``edc`` in edc.v.

    error encoding (registered on RdClk):
        00 = no error / data corrected
        01 = single bit error (corrected)
        10 = double bit error
        11 = invalid single-error syndrome (multiple errors)
    """

    def __init__(self, dsize=32, *, en_reset=False, reset_synchronization=False,
                 enable_force_error=False):
        self.dsize = dsize
        self.pwidth = edc_pwidth(dsize)
        self._en_reset = bool(en_reset)
        self._reset_sync = bool(reset_synchronization)
        self._force_error = bool(enable_force_error)

        pw = self.pwidth
        # Ports (same names/order as the Verilog module).
        self.RdClk = Signal()
        self.WrClk = Signal()
        self.Ein = Signal(dsize)          # data to encode (write side)
        self.Eout = Signal(dsize)         # encoded data out
        self.P_out = Signal(pw)           # encoder check bits out
        self.Din = Signal(dsize)          # data to decode (read side)
        self.Dout = Signal(dsize)         # corrected data out
        if self._force_error:
            self.force_error = Signal(2)
        self.error = Signal(2)
        if self._en_reset:
            if self._reset_sync:
                self.RST = Signal()
            else:
                self.Reset = Signal()
                self.RPReset = Signal()
        self.P_in = Signal(pw)            # check bits to decode

    def ports(self):
        ports = [self.RdClk, self.WrClk, self.Ein, self.Eout, self.P_out,
                 self.Din, self.Dout]
        if self._force_error:
            ports.append(self.force_error)
        ports.append(self.error)
        if self._en_reset:
            if self._reset_sync:
                ports.append(self.RST)
            else:
                ports += [self.Reset, self.RPReset]
        ports.append(self.P_in)
        return ports

    def elaborate(self, platform):
        m = Module()
        dsize, pw = self.dsize, self.pwidth
        pos = hamming_positions(dsize)

        # ------------------------------------------------------------------
        # Internal Reset (write side) / RPReset (read side)
        # ------------------------------------------------------------------
        if self._en_reset and self._reset_sync:
            # Two-FF reset synchronizers, async assert on RST (posedge clocks,
            # exactly as in edc.v).
            m.domains += ClockDomain("edc_sw", async_reset=True, local=True)
            m.d.comb += [
                ClockSignal("edc_sw").eq(self.WrClk),
                ResetSignal("edc_sw").eq(self.RST),
            ]
            q1 = Signal(2, init=0b11)
            m.d.edc_sw += q1.eq(Cat(C(0, 1), q1[0]))
            reset = q1[1]

            m.domains += ClockDomain("edc_sr", async_reset=True, local=True)
            m.d.comb += [
                ClockSignal("edc_sr").eq(self.RdClk),
                ResetSignal("edc_sr").eq(self.RST),
            ]
            q2 = Signal(2, init=0b11)
            m.d.edc_sr += q2.eq(Cat(C(0, 1), q2[0]))
            rpreset = q2[1]
        elif self._en_reset:
            reset = self.Reset
            rpreset = self.RPReset
        else:
            reset = C(0)
            rpreset = C(0)

        # Clock domains for the sequential logic.
        m.domains += ClockDomain("edc_rd", async_reset=True, local=True)
        m.d.comb += [
            ClockSignal("edc_rd").eq(self.RdClk),
            ResetSignal("edc_rd").eq(rpreset),
        ]

        # ------------------------------------------------------------------
        # Input gating (combinational, as in edc.v)
        # ------------------------------------------------------------------
        Din_reg = Signal(dsize)
        P_in_reg = Signal(pw)
        Ein_reg = Signal(dsize)
        mask = Signal(dsize)

        with m.If(rpreset):
            m.d.comb += [Din_reg.eq(0), P_in_reg.eq(0), self.Dout.eq(0)]
        with m.Else():
            m.d.comb += [
                Din_reg.eq(self.Din),
                P_in_reg.eq(self.P_in),
                self.Dout.eq(mask ^ Din_reg),
            ]

        with m.If(reset):
            m.d.comb += Ein_reg.eq(0)
        with m.Else():
            m.d.comb += Ein_reg.eq(self.Ein)

        # ------------------------------------------------------------------
        # Syndrome creation (decoder)
        # ------------------------------------------------------------------
        syndrome = Signal(pw)
        syndrome_chk = Signal(pw)

        for j in range(pw - 1):
            terms = [Din_reg[i] for i in range(dsize) if (pos[i] >> j) & 1]
            m.d.comb += syndrome_chk[j].eq(_xor(terms))
        # Overall parity bit: all data bits ^ all incoming check bits but MSB.
        m.d.comb += syndrome_chk[pw - 1].eq(
            _xor([Din_reg[i] for i in range(dsize)]
                 + [P_in_reg[j] for j in range(pw - 1)]))
        m.d.comb += syndrome.eq(syndrome_chk ^ P_in_reg)

        # ------------------------------------------------------------------
        # Error status (registered on RdClk, async RPReset)
        # ------------------------------------------------------------------
        with m.If(~syndrome[pw - 1]):
            with m.If(syndrome[:pw - 1] == 0):
                m.d.edc_rd += self.error.eq(0b00)   # no error
            with m.Else():
                m.d.edc_rd += self.error.eq(0b10)   # double error
        with m.Else():
            if dsize >= 5:
                # Syndromes above the highest used Hamming position are not
                # valid single errors (edc.v performs this check for DSIZE>=5).
                with m.If(syndrome[:pw - 1] > single_error_threshold(dsize)):
                    m.d.edc_rd += self.error.eq(0b11)
                with m.Else():
                    m.d.edc_rd += self.error.eq(0b01)  # single error
            else:
                m.d.edc_rd += self.error.eq(0b01)      # single error

        # ------------------------------------------------------------------
        # Correction mask (combinational)
        # ------------------------------------------------------------------
        with m.If(rpreset):
            m.d.comb += mask.eq(0)
        with m.Else():
            with m.Switch(syndrome):
                for i in range(dsize):
                    with m.Case((1 << (pw - 1)) | pos[i]):
                        m.d.comb += mask.eq(1 << i)
                with m.Default():
                    m.d.comb += mask.eq(0)

        # ------------------------------------------------------------------
        # Encoder check bit generator equations
        # ------------------------------------------------------------------
        enc_chkbits = Signal(pw)
        for j in range(pw - 1):
            terms = [Ein_reg[i] for i in range(dsize) if (pos[i] >> j) & 1]
            m.d.comb += enc_chkbits[j].eq(_xor(terms))
        m.d.comb += enc_chkbits[pw - 1].eq(
            _xor([Ein_reg[i] for i in range(dsize)]
                 + [enc_chkbits[j] for j in range(pw - 1)]))

        # ------------------------------------------------------------------
        # Encoder output (with optional error injection walk-through)
        # ------------------------------------------------------------------
        if self._force_error:
            m.domains += ClockDomain("edc_wr", async_reset=True, local=True)
            m.d.comb += [
                ClockSignal("edc_wr").eq(self.WrClk),
                ResetSignal("edc_wr").eq(reset),
            ]
            n = dsize + pw
            single_error = Signal(n, init=0x1)
            double_error = Signal(n, init=0x3)
            triple_error = Signal(n, init=0x7)
            for sig in (single_error, double_error, triple_error):
                m.d.edc_wr += sig.eq(Cat(sig[n - 1], sig[:n - 1]))  # rotate left

            P_out_reg = Signal(pw)
            with m.If(reset):
                m.d.comb += [self.Eout.eq(0), P_out_reg.eq(0)]
            with m.Else():
                with m.Switch(self.force_error):
                    with m.Case(0b00):  # 0 error feedthrough
                        m.d.comb += [self.Eout.eq(Ein_reg),
                                     P_out_reg.eq(enc_chkbits)]
                    with m.Case(0b01):  # 1-bit error walk-thru
                        m.d.comb += [
                            self.Eout.eq(Ein_reg ^ single_error[:dsize]),
                            P_out_reg.eq(enc_chkbits ^ single_error[dsize:]),
                        ]
                    with m.Case(0b10):  # 2-bit error walk-thru
                        m.d.comb += [
                            self.Eout.eq(Ein_reg ^ double_error[:dsize]),
                            P_out_reg.eq(enc_chkbits ^ double_error[dsize:]),
                        ]
                    with m.Case(0b11):  # 3-bit error walk-thru
                        m.d.comb += [
                            self.Eout.eq(Ein_reg ^ triple_error[:dsize]),
                            P_out_reg.eq(enc_chkbits ^ triple_error[dsize:]),
                        ]
            m.d.comb += self.P_out.eq(P_out_reg)
        else:
            m.d.comb += [
                self.Eout.eq(Ein_reg),
                self.P_out.eq(enc_chkbits),
            ]

        return m
