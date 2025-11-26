from qiskit import QuantumCircuit, QuantumRegister

from qquantum_module import iqft, madd, qft


def build_qmadd_gate(n: int):
    """n 位量子模加法器：target = (target + control) mod 2**n"""
    target = QuantumRegister(n, "target")
    control = QuantumRegister(n, "control")
    qc = QuantumCircuit(target, control, name="QMADD")

    qc.append(qft(n), list(target))
    qc.append(madd(n), list(target) + list(control))
    qc.append(iqft(n), list(target))

    return qc.to_instruction()


