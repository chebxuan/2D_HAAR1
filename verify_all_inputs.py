"""Brute-force verification of the rounded Haar circuit for all 4-bit inputs."""

from itertools import product

from qiskit import ClassicalRegister, transpile
from qiskit_aer import AerSimulator

from main_round import ArithmeticParams, build_rounding_circuit


DATA_BITS = 4
ARITH_BITS = DATA_BITS + 1
MOD = 1 << DATA_BITS


def _add_measurements(qc):
    """Attach measurement registers for reg_a, reg_d, res1, res2."""
    cr_a = ClassicalRegister(ARITH_BITS, "c_a")
    cr_d = ClassicalRegister(ARITH_BITS, "c_d")
    cr_res1 = ClassicalRegister(ARITH_BITS, "c_res1")
    cr_res2 = ClassicalRegister(ARITH_BITS, "c_res2")

    reg_a = next(reg for reg in qc.qregs if reg.name == "a")
    reg_d = next(reg for reg in qc.qregs if reg.name == "d")
    res1 = next(reg for reg in qc.qregs if reg.name == "res1")
    res2 = next(reg for reg in qc.qregs if reg.name == "res2")

    qc.add_register(cr_a, cr_d, cr_res1, cr_res2)
    qc.measure(reg_a, cr_a)
    qc.measure(reg_d, cr_d)
    qc.measure(res1, cr_res1)
    qc.measure(res2, cr_res2)

    return cr_a, cr_d, cr_res1, cr_res2


def _parse_measurement(counts, cr_names):
    bitstring = next(iter(counts))  # deterministic circuit: single outcome
    parts = bitstring.split(" ")[::-1]  # reverse to align with add order
    if len(parts) != len(cr_names):
        raise AssertionError(f"Unexpected measurement format: {bitstring}")
    mask = MOD - 1
    return tuple(int(bits, 2) & mask for bits in parts)


def simulate_quantum(a, b, c, d, simulator):
    params = ArithmeticParams(data_bits=DATA_BITS, a=a, b=b, c=c, d=d)
    qc = build_rounding_circuit(params)
    crs = _add_measurements(qc)
    transpiled = transpile(qc, simulator, optimization_level=0)
    result = simulator.run(transpiled, shots=1).result()
    counts = result.get_counts(transpiled)
    return _parse_measurement(counts, [cr.name for cr in crs])


def classical_reference(a, b, c, d):
    ab = (a - b) % MOD
    cd = (c - d) % MOD
    res1 = ((ab + cd) % MOD) // 2
    res2 = ((ab - cd) % MOD) // 2

    max_ab, min_ab = max(a, b), min(a, b)
    max_cd, min_cd = max(c, d), min(c, d)
    reg_a = ((max_ab - max_cd) + (min_ab - min_cd)) % MOD
    reg_a //= 2
    reg_d = min(min_ab, min_cd)

    return reg_a, reg_d, res1, res2


def main():
    simulator = AerSimulator(method="matrix_product_state")
    total = MOD ** 4
    for idx, (a, b, c, d) in enumerate(product(range(MOD), repeat=4), start=1):
        q_outputs = simulate_quantum(a, b, c, d, simulator)
        ref_outputs = classical_reference(a, b, c, d)
        if q_outputs != ref_outputs:
            raise AssertionError(
                f"Mismatch for inputs (a={a}, b={b}, c={c}, d={d}): "
                f"quantum={q_outputs}, classical={ref_outputs}"
            )
        if idx % 1000 == 0:
            print(f"Validated {idx}/{total} combinations...", end="\r")

    print(f"\nAll {total} combinations validated successfully.")


if __name__ == "__main__":
    main()

