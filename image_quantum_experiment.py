import argparse
import json
import random
import statistics
import time
from pathlib import Path
from typing import Dict, List, Tuple

from qiskit import ClassicalRegister, transpile
from qiskit_aer import AerSimulator

from main_round import ArithmeticParams, build_rounding_circuit


# ---------------------------------------------------------------------------
# Image helpers (BMP, 8-bit grayscale)
# ---------------------------------------------------------------------------

def read_bmp_grayscale(path: Path) -> List[List[int]]:
    """Minimal BMP loader (8-bit or 24-bit, uncompressed)."""
    data = path.read_bytes()
    if data[:2] != b"BM":
        raise ValueError("Expected BMP header (BM)")

    pixel_offset = int.from_bytes(data[10:14], "little")
    dib_header_size = int.from_bytes(data[14:18], "little")
    width = int.from_bytes(data[18:22], "little", signed=True)
    height = int.from_bytes(data[22:26], "little", signed=True)
    planes = int.from_bytes(data[26:28], "little")
    bits_per_pixel = int.from_bytes(data[28:30], "little")
    compression = int.from_bytes(data[30:34], "little")

    if planes != 1 or compression != 0 or bits_per_pixel not in (8, 24):
        raise ValueError("Only uncompressed 8-bit/24-bit BMP files are supported")

    top_down = height < 0
    height = abs(height)
    row_stride = ((bits_per_pixel * width + 31) // 32) * 4

    palette = None
    if bits_per_pixel == 8:
        palette_entries = (pixel_offset - 14 - dib_header_size) // 4
        palette = [
            data[14 + dib_header_size + idx * 4 + 2] for idx in range(palette_entries)
        ]
        if len(palette) < 256:
            palette.extend(range(256 - len(palette)))

    pixels = [[0] * width for _ in range(height)]
    for row in range(height):
        src_row = row if top_down else height - 1 - row
        row_start = pixel_offset + src_row * row_stride
        row_bytes = data[row_start : row_start + row_stride]
        for col in range(width):
            if bits_per_pixel == 8:
                index = row_bytes[col]
                pixels[row][col] = palette[index] if palette else index
            else:
                base = col * 3
                b, g, r = row_bytes[base : base + 3]
                pixels[row][col] = (r + g + b) // 3
    return pixels


def quantize_pixels(pixels: List[List[int]], bit_depth: int) -> List[List[int]]:
    shift = max(0, 8 - bit_depth)
    return [[value >> shift for value in row] for row in pixels]


# ---------------------------------------------------------------------------
# Quantum simulation helpers
# ---------------------------------------------------------------------------

def simulate_block(
    a: int,
    b: int,
    c: int,
    d: int,
    data_bits: int,
    simulator: AerSimulator,
    shots: int,
) -> Dict[str, int]:
    params = ArithmeticParams(data_bits=data_bits, a=a, b=b, c=c, d=d)
    qc = build_rounding_circuit(params)
    n = params.arith_bits

    cr_a = ClassicalRegister(n, "c_a")
    cr_d = ClassicalRegister(n, "c_d")
    cr_res1 = ClassicalRegister(n, "c_res1")
    cr_res2 = ClassicalRegister(n, "c_res2")
    qc.add_register(cr_a, cr_d, cr_res1, cr_res2)

    reg_a = next(reg for reg in qc.qregs if reg.name == "a")
    reg_d = next(reg for reg in qc.qregs if reg.name == "d")
    res1 = next(reg for reg in qc.qregs if reg.name == "res1")
    res2 = next(reg for reg in qc.qregs if reg.name == "res2")
    qc.measure(reg_a, cr_a)
    qc.measure(reg_d, cr_d)
    qc.measure(res1, cr_res1)
    qc.measure(res2, cr_res2)
    transpiled = transpile(qc, simulator, optimization_level=0)
    result = simulator.run(transpiled, shots=shots).result()
    counts = result.get_counts(transpiled)
    meas_result = max(counts.items(), key=lambda item: item[1])[0]

    bits = meas_result.split(" ")[::-1]
    mask = params.modulus - 1
    reg_a = int(bits[0], 2) & mask
    reg_d = int(bits[1], 2) & mask
    res1 = int(bits[2], 2) & mask
    res2 = int(bits[3], 2) & mask
    return {"reg_a": reg_a, "reg_d": reg_d, "res1": res1, "res2": res2}


def classical_block(a: int, b: int, c: int, d: int, data_bits: int) -> Dict[str, int]:
    modulus = 1 << data_bits
    res1 = ((a - b + c - d) % modulus) // 2
    res2 = ((a - b - (c - d)) % modulus) // 2
    reg_a = ((a + b - c - d) % modulus) // 2
    reg_d = min(a, b, c, d)
    return {"reg_a": reg_a, "reg_d": reg_d, "res1": res1, "res2": res2}


def block_energy(values: Dict[str, int]) -> int:
    return abs(values["res1"]) + abs(values["res2"]) + abs(values["reg_a"])


def percentile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(round((len(sorted_vals) - 1) * q))
    idx = max(0, min(len(sorted_vals) - 1, idx))
    return sorted_vals[idx]


def save_pgm(path: Path, pixels: List[List[int]], upsample: bool):
    if upsample:
        pixels = upsample_blocks(pixels)
    height = len(pixels)
    width = len(pixels[0])
    header = f"P2\n{width} {height}\n255\n"
    lines = [" ".join(str(v) for v in row) for row in pixels]
    path.write_text(header + "\n".join(lines))


def upsample_blocks(block_pixels: List[List[int]]) -> List[List[int]]:
    h = len(block_pixels)
    w = len(block_pixels[0])
    upsampled = [[0] * (w * 2) for _ in range(h * 2)]
    for y in range(h):
        for x in range(w):
            value = block_pixels[y][x]
            upsampled[2 * y][2 * x] = value
            upsampled[2 * y][2 * x + 1] = value
            upsampled[2 * y + 1][2 * x] = value
            upsampled[2 * y + 1][2 * x + 1] = value
    return upsampled


# ---------------------------------------------------------------------------
# Experiment runner
# ---------------------------------------------------------------------------

def run_experiment(args: argparse.Namespace):
    image_path = Path(args.image)
    pixels = read_bmp_grayscale(image_path)
    quant = quantize_pixels(pixels, args.bit_depth)
    height = len(quant)
    width = len(quant[0])
    block_h = height // 2
    block_w = width // 2
    all_blocks: List[Tuple[int, int, Tuple[int, int, int, int]]] = []

    for by in range(block_h):
        for bx in range(block_w):
            block = (
                quant[2 * by][2 * bx],
                quant[2 * by][2 * bx + 1],
                quant[2 * by + 1][2 * bx],
                quant[2 * by + 1][2 * bx + 1],
            )
            all_blocks.append((by, bx, block))

    total_blocks = len(all_blocks)
    if args.max_blocks > 0 and args.max_blocks < total_blocks:
        rng = random.Random(args.seed)
        selected = rng.sample(all_blocks, args.max_blocks)
    else:
        selected = all_blocks

    simulator = AerSimulator(method="matrix_product_state")

    quantum_energy_map = [[0] * block_w for _ in range(block_h)]
    classical_energy_map = [[0] * block_w for _ in range(block_h)]
    quantum_energies: List[int] = []
    classical_energies: List[int] = []
    reg_d_values: List[int] = []
    timings: List[float] = []

    start = time.time()
    for idx, (by, bx, block) in enumerate(selected, start=1):
        a, b, c, d = block
        classical = classical_block(a, b, c, d, args.bit_depth)
        classical_energy = block_energy(classical)
        classical_energy_map[by][bx] = classical_energy
        classical_energies.append(classical_energy)

        t0 = time.time()
        quantum = simulate_block(a, b, c, d, args.bit_depth, simulator, args.shots)
        timings.append(time.time() - t0)
        energy_q = block_energy(quantum)
        quantum_energy_map[by][bx] = energy_q
        quantum_energies.append(energy_q)
        reg_d_values.append(quantum["reg_d"])

        if args.verbose and idx % max(1, len(selected) // 10) == 0:
            print(f"[{idx}/{len(selected)}] blocks processed…")

    total_time = time.time() - start

    summary = {
        "image": str(image_path),
        "width": width,
        "height": height,
        "block_rows": block_h,
        "block_cols": block_w,
        "total_blocks": total_blocks,
        "sampled_blocks": len(selected),
        "bit_depth": args.bit_depth,
        "shots": args.shots,
        "avg_quantum_energy": statistics.fmean(quantum_energies),
        "p90_quantum_energy": percentile(quantum_energies, 0.9),
        "avg_classical_energy": statistics.fmean(classical_energies),
        "p90_classical_energy": percentile(classical_energies, 0.9),
        "avg_reg_d": statistics.fmean(reg_d_values),
        "median_runtime_per_block_sec": statistics.median(timings),
        "total_runtime_sec": total_time,
    }

    summary_path = image_path.with_name(f"{image_path.stem}_quantum_summary.json")
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"Saved summary to {summary_path}")

    if len(selected) == total_blocks:
        q_map = normalize_map(quantum_energy_map)
        c_map = normalize_map(classical_energy_map)
        quantum_pgm = image_path.with_name(f"{image_path.stem}_quantum_energy.pgm")
        classical_pgm = image_path.with_name(f"{image_path.stem}_classical_energy.pgm")
        save_pgm(quantum_pgm, q_map, upsample=args.upsample)
        save_pgm(classical_pgm, c_map, upsample=args.upsample)
        print(f"Saved energy maps:\n  Quantum:   {quantum_pgm}\n  Classical: {classical_pgm}")
    else:
        print("Energy maps skipped (sampling mode). Use --max-blocks 0 for full export.")


def normalize_map(values: List[List[int]]) -> List[List[int]]:
    flat = [v for row in values for v in row]
    vmax = max(flat) if flat else 1
    if vmax == 0:
        vmax = 1
    return [[int(round(255 * val / vmax)) for val in row] for row in values]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the quantum morphological Haar circuit on an image."
    )
    parser.add_argument("--image", type=str, default="cameraman.bmp", help="Input BMP")
    parser.add_argument("--bit-depth", type=int, default=4, help="Logical data bits")
    parser.add_argument(
        "--shots", type=int, default=512, help="Shots per block simulation"
    )
    parser.add_argument(
        "--max-blocks",
        type=int,
        default=2048,
        help="Number of 2x2 blocks to sample (0 = process all)",
    )
    parser.add_argument("--seed", type=int, default=13, help="Sampling seed")
    parser.add_argument(
        "--upsample",
        action="store_true",
        help="Upsample block maps to the original resolution when exporting PGM",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Print progress every 10%%"
    )
    return parser


if __name__ == "__main__":
    run_experiment(build_parser().parse_args())

