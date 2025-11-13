from qiskit import QuantumCircuit, QuantumRegister

from qmsub_gate import build_qmsub_gate


def build_c_qmsub_gate(n: int):
    """比较-减法器：|0⟩|t⟩|c⟩ → |t<c⟩|(t-c) mod 2**n⟩|c⟩"""
    comp = QuantumRegister(1, "comp")
    target = QuantumRegister(n, "target")
    control = QuantumRegister(n, "control")
    qc = QuantumCircuit(comp, target, control, name="C_QMSUB")

    qmsub = build_qmsub_gate(n)
    qc.append(qmsub, list(target) + list(control))
    qc.cx(target[n - 1], comp[0])

    return qc.to_instruction()


