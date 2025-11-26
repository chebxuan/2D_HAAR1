"""Tests for the rounded arithmetic circuit."""

from main_round import ArithmeticParams, build_rounding_circuit
from qiskit import ClassicalRegister, transpile
from qiskit_aer import AerSimulator


def parse_counts(counts, cr_names, mask):
    """Return masked tuple (a_round, d, res1_round, res2_round)."""
    (bitstring, _) = max(counts.items(), key=lambda item: item[1])
    parts = bitstring.split(" ")[::-1]
    if len(parts) != len(cr_names):
        raise AssertionError("Unexpected measurement format")
    values = [int(bits, 2) & mask for bits in parts]
    return tuple(values)


def test_rounding_default():
    params = ArithmeticParams()
    qc = build_rounding_circuit(params)

    n = params.arith_bits

    cr_a = ClassicalRegister(n, "c_a")
    cr_d = ClassicalRegister(n, "c_d")
    cr_res1 = ClassicalRegister(n, "c_res1")
    cr_res2 = ClassicalRegister(n, "c_res2")

    reg_a = next(reg for reg in qc.qregs if reg.name == "a")
    reg_d = next(reg for reg in qc.qregs if reg.name == "d")
    res1 = next(reg for reg in qc.qregs if reg.name == "res1")
    res2 = next(reg for reg in qc.qregs if reg.name == "res2")

    qc.add_register(cr_a, cr_d, cr_res1, cr_res2)
    qc.measure(reg_a, cr_a)
    qc.measure(reg_d, cr_d)
    qc.measure(res1, cr_res1)
    qc.measure(res2, cr_res2)

    simulator = AerSimulator(method="matrix_product_state")
    transpiled = transpile(qc, simulator, optimization_level=0)
    result = simulator.run(transpiled, shots=2048).result()
    mask = params.modulus - 1
    values = parse_counts(
        result.get_counts(transpiled),
        [cr_a.name, cr_d.name, cr_res1.name, cr_res2.name],
        mask,
    )

    exp_res1 = ((params.a - params.b + params.c - params.d) % params.modulus) // 2
    exp_res2 = ((params.a - params.b - (params.c - params.d)) % params.modulus) // 2
    exp_reg_a = ((params.a + params.b - params.c - params.d) % params.modulus) // 2
    exp_min = min(params.a, params.b, params.c, params.d)

    assert values == (exp_reg_a, exp_min, exp_res1, exp_res2)


if __name__ == "__main__":
    test_rounding_default()
    print("Rounded circuit test passed.")

