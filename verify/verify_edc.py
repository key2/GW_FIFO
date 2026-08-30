"""Parse edc.v and verify the Amaranth Edc generator reproduces exactly the
same equations for every DSIZE in 1..64."""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from amaranth_fifo.edc import edc_pwidth, hamming_positions, single_error_threshold

if len(sys.argv) != 2:
    sys.exit("usage: verify_edc.py <path/to/Gowin/IDE/ipcore/FIFO/data/edc.v>")
SRC = open(sys.argv[1]).read()

# Split into per-DSIZE generate branches.
branches = list(re.finditer(r"if\s*\(DSIZE\s*==\s*(\d+)\)\s*begin\s*:\s*DSIZE_\d+", SRC))
blocks = {}
for k, mm in enumerate(branches):
    end = branches[k + 1].start() if k + 1 < len(branches) else len(SRC)
    blocks[int(mm.group(1))] = SRC[mm.end():end]

assert sorted(blocks) == list(range(1, 65)), sorted(blocks)

failures = []
for d, text in sorted(blocks.items()):
    pw = edc_pwidth(d)
    pos = hamming_positions(d)

    # --- encoder check bits ---
    enc = {}
    for j, rhs in re.findall(r"assign\s+enc_chkbits\[(\d+)\]\s*=\s*([^;]+);", text):
        enc[int(j)] = rhs
    if sorted(enc) != list(range(pw)):
        failures.append(f"DSIZE={d}: enc_chkbits indices {sorted(enc)}")
        continue
    for j in range(pw - 1):
        got = sorted(int(i) for i in re.findall(r"Ein_reg\[(\d+)\]", enc[j]))
        exp = sorted(i for i in range(d) if (pos[i] >> j) & 1)
        if got != exp:
            failures.append(f"DSIZE={d}: enc_chkbits[{j}] got {got} exp {exp}")
    got = sorted(int(i) for i in re.findall(r"Ein_reg\[(\d+)\]", enc[pw - 1]))
    gotc = sorted(int(i) for i in re.findall(r"enc_chkbits\[(\d+)\]", enc[pw - 1]))
    if got != list(range(d)) or gotc != list(range(pw - 1)):
        failures.append(f"DSIZE={d}: enc_chkbits[{pw-1}] data {got} chk {gotc}")

    # --- syndrome check bits ---
    syn = {}
    for j, rhs in re.findall(r"assign\s+syndrome_chk\[(\d+)\]\s*=\s*([^;]+);", text):
        syn[int(j)] = rhs
    for j in range(pw - 1):
        got = sorted(int(i) for i in re.findall(r"Din_reg\[(\d+)\]", syn[j]))
        exp = sorted(i for i in range(d) if (pos[i] >> j) & 1)
        if got != exp:
            failures.append(f"DSIZE={d}: syndrome_chk[{j}] got {got} exp {exp}")
    got = sorted(int(i) for i in re.findall(r"Din_reg\[(\d+)\]", syn[pw - 1]))
    gotp = sorted(int(i) for i in re.findall(r"P_in_reg\[(\d+)\]", syn[pw - 1]))
    if got != list(range(d)) or gotp != list(range(pw - 1)):
        failures.append(f"DSIZE={d}: syndrome_chk[{pw-1}] data {got} P_in {gotp}")

    # --- correction mask ---
    entries = re.findall(
        r"\d+'b([01]+)\s*:\s*begin\s*mask\s*<?=\s*\d+'h([0-9a-fA-F]+)", text)
    if len(entries) != d:
        failures.append(f"DSIZE={d}: {len(entries)} mask entries, expected {d}")
    else:
        for i, (case_bits, mask_hex) in enumerate(entries):
            exp_case = (1 << (pw - 1)) | pos[i]
            if int(case_bits, 2) != exp_case or int(mask_hex, 16) != (1 << i):
                failures.append(
                    f"DSIZE={d}: mask entry {i}: case {case_bits} mask {mask_hex}"
                    f" exp case {exp_case:b} mask {1 << i:x}")

    # --- invalid-single-error threshold ---
    es = text.split("correction_mask")[0]
    thr = re.search(r"syndrome\[\d+:0\]\s*>\s*\d+'b([01]+)", es)
    case = re.search(r"case\s*\(syndrome\[(\d+):3\]\)(.*?)endcase", es, re.S)
    if thr:
        T = int(thr.group(1), 2)
    elif case:
        vals = sorted(int(v, 2) for v in re.findall(r"\d+'b([01]+)\s*:", case.group(2)))
        assert vals == list(range(min(vals), 2 ** (int(case.group(1)) - 2))), (d, vals)
        T = 8 * min(vals) - 1
    else:
        T = None
    if d >= 5:
        if T is None:
            failures.append(f"DSIZE={d}: threshold check missing")
        elif T != single_error_threshold(d):
            failures.append(
                f"DSIZE={d}: threshold {T} exp {single_error_threshold(d)}")
    else:
        if T is not None:
            failures.append(f"DSIZE={d}: unexpected threshold check")

if failures:
    print("FAIL:")
    for f in failures:
        print(" ", f)
    sys.exit(1)
print("OK: all 64 DSIZE branches of edc.v match the algorithmic generator")
