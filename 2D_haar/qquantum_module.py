from qiskit import QuantumCircuit
import numpy as np


def qft(n):
    """Creates an n-qubit QFT instruction."""
    qc = QuantumCircuit(n, name="QFT")
    for i in range(n - 1, -1, -1):
        qc.h(i)
        for j in range(i - 1, -1, -1):
            qc.cp(np.pi / 2 ** (i - j), j, i)
    for i in range(n // 2):
        qc.swap(i, n - 1 - i)
    return qc.to_instruction(label="QFT")


def iqft(n):
    """Creates an n-qubit Inverse QFT instruction as the exact inverse of QFT."""
    return qft(n).inverse()


def madd(n, is_inverse=False):
    """Creates a controlled-phase addition instruction (MADD/MSUB)."""
    name = "MSUB" if is_inverse else "MADD"
    qc = QuantumCircuit(2 * n, name=name)
    angle_sign = -1 if is_inverse else 1
    for i in range(n):
        for j in range(i, n):
            angle = angle_sign * np.pi / (2 ** (j - i))
            qc.cp(angle, n + i, j)
    return qc.to_instruction(label=name)