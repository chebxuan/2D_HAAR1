"""Simple regression tests for QMADD/QMSUB/C_QMSUB gates."""
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile
from qiskit_aer import AerSimulator

from qmadd_gate import build_qmadd_gate
from qmsub_gate import build_qmsub_gate
from c_qmsub_gate import build_c_qmsub_gate


n = 4
sim = AerSimulator()


def set_val(qc: QuantumCircuit, reg: QuantumRegister, value: int):
    bits = format(value % (1 << len(reg)), f"0{len(reg)}b")[::-1]
    for idx, bit in enumerate(bits):
        if bit == "1":
            qc.x(reg[idx])


def run_and_parse(qc: QuantumCircuit, creg_names):
    transpiled = transpile(qc, sim)
    result = sim.run(transpiled, shots=1024).result()
    counts = result.get_counts(transpiled)
    top = max(counts.items(), key=lambda item: item[1])[0]
    parts = top.split(" ")
    if len(parts) != len(creg_names):
        raise RuntimeError(f"Unexpected measurement format: {top}")
    return {
        creg: int(bits, 2)
        for creg, bits in zip(creg_names, reversed(parts))
    }


# Test QMSUB: target = target - control
reg_t = QuantumRegister(n, "t")
reg_c = QuantumRegister(n, "c")
cr_t = ClassicalRegister(n, "ct")
cr_c = ClassicalRegister(n, "cc")
qc = QuantumCircuit(reg_t, reg_c, cr_t, cr_c)
set_val(qc, reg_t, 7)
set_val(qc, reg_c, 2)
qc.append(build_qmsub_gate(n), list(reg_t) + list(reg_c))
qc.measure(reg_t, cr_t)
qc.measure(reg_c, cr_c)
res = run_and_parse(qc, [cr_t.name, cr_c.name])
print("QMSUB result:", res)

# Test QMADD: target = target + control
reg_t = QuantumRegister(n, "t")
reg_c = QuantumRegister(n, "c")
cr_t = ClassicalRegister(n, "ct")
cr_c = ClassicalRegister(n, "cc")
qc = QuantumCircuit(reg_t, reg_c, cr_t, cr_c)
set_val(qc, reg_t, 5)
set_val(qc, reg_c, 3)
qc.append(build_qmadd_gate(n), list(reg_t) + list(reg_c))
qc.measure(reg_t, cr_t)
qc.measure(reg_c, cr_c)
res = run_and_parse(qc, [cr_t.name, cr_c.name])
print("QMADD result:", res)

# Test C_QMSUB: comparator + subtraction
comp = QuantumRegister(1, "comp")
reg_a = QuantumRegister(n, "a")
reg_b = QuantumRegister(n, "b")
cr_comp = ClassicalRegister(1, "ccomp")
cr_a = ClassicalRegister(n, "ca")
cr_b = ClassicalRegister(n, "cb")
qc = QuantumCircuit(comp, reg_a, reg_b, cr_comp, cr_a, cr_b)
set_val(qc, reg_a, 7)
set_val(qc, reg_b, 2)
qc.append(build_c_qmsub_gate(n), [*comp, *reg_a, *reg_b])
qc.measure(comp, cr_comp)
qc.measure(reg_a, cr_a)
qc.measure(reg_b, cr_b)
res = run_and_parse(qc, [cr_comp.name, cr_a.name, cr_b.name])
print("C_QMSUB result:", res)
{
  "cells": [],
  "metadata": {
    "language_info": {
      "name": "python"
    }
  },
  "nbformat": 4,
  "nbformat_minor": 2
}