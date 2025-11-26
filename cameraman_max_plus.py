import math
import struct
import time
from pathlib import Path


def read_bmp_grayscale(path: Path):
    """Load a grayscale BMP image without external dependencies."""
    data = path.read_bytes()
    if data[:2] != b"BM":
        raise ValueError("Not a BMP file")

    pixel_offset = struct.unpack_from("<I", data, 10)[0]
    dib_header_size = struct.unpack_from("<I", data, 14)[0]
    width = struct.unpack_from("<i", data, 18)[0]
    height = struct.unpack_from("<i", data, 22)[0]
    planes = struct.unpack_from("<H", data, 26)[0]
    bits_per_pixel = struct.unpack_from("<H", data, 28)[0]
    compression = struct.unpack_from("<I", data, 30)[0]

    if planes != 1 or bits_per_pixel not in (8, 24) or compression != 0:
        raise ValueError("Only uncompressed 8-bit or 24-bit BMP is supported")

    top_down = height < 0
    height = abs(height)
    row_stride = ((bits_per_pixel * width + 31) // 32) * 4

    palette = None
    if bits_per_pixel == 8:
        palette_entries = (pixel_offset - 14 - dib_header_size) // 4
        palette = [
            data[14 + dib_header_size + i * 4 + 2]
            for i in range(palette_entries)
        ]
        if len(palette) < 256:
            palette.extend([int(round(255 * i / 255)) for i in range(256 - len(palette))])

    pixels = [[0] * width for _ in range(height)]

    for row in range(height):
        src_row = row if top_down else height - 1 - row
        row_start = pixel_offset + src_row * row_stride
        row_bytes = data[row_start : row_start + row_stride]
        for col in range(width):
            if bits_per_pixel == 8:
                index = row_bytes[col]
                pixels[row][col] = palette[index] if palette else index
            else:  # 24-bit, use average of RGB
                base = col * 3
                b, g, r = row_bytes[base : base + 3]
                pixels[row][col] = (r + g + b) // 3

    return pixels


def quantize_pixels(pixels, bit_depth: int):
    shift = max(0, 8 - bit_depth)
    return [[value >> shift for value in row] for row in pixels]


def max_plus_block(a, b, c, d):
    result1 = ((a - b) + (c - d)) // 2
    result2 = ((a - b) - (c - d)) // 2
    reg_a = ((a + b) - (c + d)) // 2
    reg_d = min(a, b, c, d)
    return result1, result2, reg_a, reg_d


def build_edge_map(pixels, bit_depth: int):
    quant = quantize_pixels(pixels, bit_depth)
    height = len(quant)
    width = len(quant[0])
    block_h = height // 2
    block_w = width // 2

    energy_map = [[0] * block_w for _ in range(block_h)]

    for by in range(block_h):
        for bx in range(block_w):
            a = quant[2 * by][2 * bx]
            b = quant[2 * by][2 * bx + 1]
            c = quant[2 * by + 1][2 * bx]
            d = quant[2 * by + 1][2 * bx + 1]
            res1, res2, reg_a, _ = max_plus_block(a, b, c, d)
            energy = abs(res1) + abs(res2) + abs(reg_a)
            energy_map[by][bx] = energy

    flat = [val for row in energy_map for val in row]
    max_energy = max(flat) if flat else 1
    norm_map = [
        [int(round(255 * val / max_energy)) for val in row] for row in energy_map
    ]
    return norm_map, flat


def upsample_map(edge_map):
    small_h = len(edge_map)
    small_w = len(edge_map[0])
    upsampled = [[0] * (small_w * 2) for _ in range(small_h * 2)]
    for y in range(small_h):
        for x in range(small_w):
            value = edge_map[y][x]
            upsampled[2 * y][2 * x] = value
            upsampled[2 * y][2 * x + 1] = value
            upsampled[2 * y + 1][2 * x] = value
            upsampled[2 * y + 1][2 * x + 1] = value
    return upsampled


def save_pgm(path: Path, pixels):
    height = len(pixels)
    width = len(pixels[0])
    header = f"P2\n{width} {height}\n255\n"
    body_lines = [" ".join(str(value) for value in row) for row in pixels]
    path.write_text(header + "\n".join(body_lines))


def summarize_energy(flat_energy):
    avg = sum(flat_energy) / len(flat_energy)
    sorted_vals = sorted(flat_energy, reverse=True)
    p90 = sorted_vals[int(0.1 * len(sorted_vals))]
    return avg, p90


def run_experiment(image_path: Path, bit_depth: int = 4):
    t0 = time.time()
    pixels = read_bmp_grayscale(image_path)
    load_time = time.time() - t0

    edge_map, flat = build_edge_map(pixels, bit_depth)
    edged = upsample_map(edge_map)
    avg_energy, top10pct = summarize_energy(flat)

    output_path = image_path.with_name(f"{image_path.stem}_edge_map.pgm")
    save_pgm(output_path, edged)

    total_time = time.time() - t0
    return {
        "width": len(pixels[0]),
        "height": len(pixels),
        "bit_depth": bit_depth,
        "blocks": len(flat),
        "avg_energy": avg_energy,
        "p90_energy": top10pct,
        "edge_map_path": str(output_path),
        "load_time": load_time,
        "total_time": total_time,
    }


if __name__ == "__main__":
    info = run_experiment(Path("cameraman.bmp"), bit_depth=4)
    for key, value in info.items():
        print(f"{key}: {value}")

