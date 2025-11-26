from __future__ import annotations

from dataclasses import dataclass
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister, transpile
from qiskit_aer import AerSimulator

from c_qmsub_gate import build_c_qmsub_gate
from qmadd_gate import build_qmadd_gate
from qmsub_gate import build_qmsub_gate


@dataclass(frozen=True)
class ArithmeticParams:
    data_bits: int = 4  # logical bits for inputs/results
    a: int = 7
    b: int = 2
    c: int = 5
    d: int = 1

    @property
    def arith_bits(self) -> int:
        return self.data_bits + 1  # extra guard bit for signed detection

    @property
    def modulus(self) -> int:
        return 1 << self.data_bits


def _set_initial_state(qc: QuantumCircuit, register: QuantumRegister, value: int, data_bits: int):
    bits = format(value % (1 << data_bits), f"0{data_bits}b")[::-1]
    for idx, bit in enumerate(bits):
        if bit == "1":
            qc.x(register[idx])


def apply_halving(
    qc: QuantumCircuit,
    register: QuantumRegister,
    shift_anc,
    guard_anc,
    data_bits: int,
):
    """In-place UR operator (floor division by 2) with guard handling.

    shift_anc ends with the discarded LSB.
    guard_anc records whether the MSB (overflow/underflow) was set, so that
    we can subtract 2^{data_bits-1} when necessary.
    """
    guard_idx = data_bits  # extra guard bit position

    # Copy guard bit to anc and clear it in the register (subtract 2^{data_bits} if needed)
    qc.cx(register[guard_idx], guard_anc)
    qc.cx(guard_anc, register[guard_idx])

    # Perform right-shift with zero fill using shift_anc
    for idx in range(len(register) - 1, -1, -1):
        qc.swap(register[idx], shift_anc)

    # guard_anc keeps track of the overflow bit (no further action needed here)


def build_rounding_circuit(params: ArithmeticParams) -> QuantumCircuit:
    n = params.arith_bits

    # --- Quantum registers ---
    reg_a = QuantumRegister(n, "a")
    reg_b = QuantumRegister(n, "b")
    reg_c = QuantumRegister(n, "c")
    reg_d = QuantumRegister(n, "d")

    res1 = QuantumRegister(n, "res1")
    res2 = QuantumRegister(n, "res2")

    anc_res1_shift = QuantumRegister(1, "anc_res1_shift")
    anc_res2_shift = QuantumRegister(1, "anc_res2_shift")
    anc_reg_a_shift = QuantumRegister(1, "anc_a_shift")

    anc_res1_guard = QuantumRegister(1, "anc_res1_guard")
    anc_res2_guard = QuantumRegister(1, "anc_res2_guard")
    anc_reg_a_guard = QuantumRegister(1, "anc_a_guard")

    comp_ab = QuantumRegister(1, "comp_ab")
    comp_cd = QuantumRegister(1, "comp_cd")
    comp_min = QuantumRegister(1, "comp_min")

    qc = QuantumCircuit(
        reg_a,
        reg_b,
        reg_c,
        reg_d,
        res1,
        res2,
        anc_res1_shift,
        anc_res2_shift,
        anc_reg_a_shift,
        anc_res1_guard,
        anc_res2_guard,
        anc_reg_a_guard,
        comp_ab,
        comp_cd,
        comp_min,
        name="RoundedArithmeticPipeline",
    )

    # Load initial values
    _set_initial_state(qc, reg_a, params.a, params.data_bits)
    _set_initial_state(qc, reg_b, params.b, params.data_bits)
    _set_initial_state(qc, reg_c, params.c, params.data_bits)
    _set_initial_state(qc, reg_d, params.d, params.data_bits)

    qmadd = build_qmadd_gate(n)
    qmsub = build_qmsub_gate(n)
    c_qmsub = build_c_qmsub_gate(n)

    # --- Stage 1: Compare/Subtract pairs ---
    qc.append(c_qmsub, [comp_ab[0], *reg_a, *reg_b])
    qc.append(c_qmsub, [comp_cd[0], *reg_c, *reg_d])
    qc.barrier()

    # --- Stage 2: (a-b)+(c-d) ---
    qc.append(qmadd, list(res1) + list(reg_a))
    qc.append(qmadd, list(res1) + list(reg_c))
    apply_halving(
        qc,
        res1,
        anc_res1_shift[0],
        anc_res1_guard[0],
        params.data_bits,
    )

    # --- Stage 3: (a-b)-(c-d) ---
    for idx in range(n):
        qc.cx(reg_a[idx], res2[idx])
    qc.append(qmsub, list(res2) + list(reg_c))
    apply_halving(
        qc,
        res2,
        anc_res2_shift[0],
        anc_res2_guard[0],
        params.data_bits,
    )
    qc.barrier()

    # --- Stage 4: Restore a, c ---
    qc.append(qmadd, list(reg_a) + list(reg_b))
    qc.append(qmadd, list(reg_c) + list(reg_d))
    qc.barrier()

    # --- Stage 5: Pairwise max/min ---
    for idx in range(n):
        qc.cswap(comp_ab[0], reg_a[idx], reg_b[idx])
    for idx in range(n):
        qc.cswap(comp_cd[0], reg_c[idx], reg_d[idx])
    qc.barrier()

    # --- Stage 6: Global arithmetic ---
    qc.append(c_qmsub, [comp_min[0], *reg_b, *reg_d])
    qc.append(qmsub, list(reg_a) + list(reg_c))
    qc.append(qmadd, list(reg_a) + list(reg_b))
    apply_halving(
        qc,
        reg_a,
        anc_reg_a_shift[0],
        anc_reg_a_guard[0],
        params.data_bits,
    )
    qc.barrier()

    # --- Stage 7: Global minimum ---
    qc.append(qmadd, list(reg_b) + list(reg_d))
    for idx in range(n):
        qc.cswap(comp_min[0], reg_b[idx], reg_d[idx])
    qc.barrier()

    return qc


def run_and_report(params: ArithmeticParams):
    qc = build_rounding_circuit(params)

    n = params.arith_bits
    cr_a = ClassicalRegister(n, "c_a")
    cr_d = ClassicalRegister(n, "c_d")
    cr_res1 = ClassicalRegister(n, "c_res1")
    cr_res2 = ClassicalRegister(n, "c_res2")

    reg_d = next(reg for reg in qc.qregs if reg.name == "d")
    reg_a = next(reg for reg in qc.qregs if reg.name == "a")
    res1 = next(reg for reg in qc.qregs if reg.name == "res1")
    res2 = next(reg for reg in qc.qregs if reg.name == "res2")

    qc.add_register(cr_a, cr_d, cr_res1, cr_res2)
    qc.measure(reg_a, cr_a)
    qc.measure(reg_d, cr_d)
    qc.measure(res1, cr_res1)
    qc.measure(res2, cr_res2)

    simulator = AerSimulator(method="matrix_product_state")
    transpiled = transpile(qc, simulator, optimization_level=0)
    result = simulator.run(transpiled, shots=4096).result()
    counts = result.get_counts(transpiled)

    print("\n--- Rounded Simulation Results ---")
    mask = params.modulus - 1

    sorted_counts = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    for idx, (meas_result, count) in enumerate(sorted_counts[:5]):
        bits = meas_result.split(" ")[::-1]
        a_val = int(bits[0], 2) & mask
        d_val = int(bits[1], 2) & mask
        res1_val = int(bits[2], 2) & mask
        res2_val = int(bits[3], 2) & mask
        print(
            f"#{idx+1}: Freq={count/4096:.2%} | Outcome: {meas_result}\n"
            f"    Parsed: reg_a={a_val}, reg_d={d_val}, "
            f"res1={res1_val}, res2={res2_val}"
        )

    # Theoretical expectations with rounding
    exp_res1 = ((params.a - params.b + params.c - params.d) % params.modulus) // 2
    exp_res2 = ((params.a - params.b - (params.c - params.d)) % params.modulus) // 2
    exp_reg_a = ((params.a + params.b - params.c - params.d) % params.modulus) // 2
    exp_min = min(params.a, params.b, params.c, params.d)

    print("\n--- Rounded Theoretical Expectations ---")
    print(f"Expected: reg_a = {exp_reg_a}")
    print(f"Expected: reg_d (min) = {exp_min}")
    print(f"Expected: res1_half = {exp_res1}")
    print(f"Expected: res2_half = {exp_res2}")


if __name__ == "__main__":
    run_and_report(ArithmeticParams())

