from __future__ import annotations
from dataclasses import dataclass
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister, transpile
from qiskit_aer import AerSimulator
from c_qmsub_gate import build_c_qmsub_gate
from qmadd_gate import build_qmadd_gate
from qmsub_gate import build_qmsub_gate


@dataclass(frozen=True)
class ArithmeticParams:
    n: int = 4
    a: int = 7
    b: int = 2
    c: int = 5
    d: int = 1


def _load_value(qc: QuantumCircuit, register: QuantumRegister, value: int):
    bits = format(value, f"0{len(register)}b")[::-1]
    for idx, bit in enumerate(bits):
        if bit == "1":
            qc.x(register[idx])


def _reg_args(*registers: QuantumRegister):
    qubits = []
    for reg in registers:
        qubits.extend(list(reg))
    return qubits


def build_full_circuit(params: ArithmeticParams) -> QuantumCircuit:
    n = params.n
    reg_a = QuantumRegister(n, "a")
    reg_b = QuantumRegister(n, "b")
    reg_c = QuantumRegister(n, "c")
    reg_d = QuantumRegister(n, "d")
    result1 = QuantumRegister(n, "result1")
    result2 = QuantumRegister(n, "result2")
    comp_ab = QuantumRegister(1, "comp_ab")
    comp_cd = QuantumRegister(1, "comp_cd")
    comp_min = QuantumRegister(1, "comp_min")

    qc = QuantumCircuit(
        reg_a,
        reg_b,
        reg_c,
        reg_d,
        result1,
        result2,
        comp_ab,
        comp_cd,
        comp_min,
        name="ArithmeticPipeline",
    )

    _load_value(qc, reg_a, params.a)
    _load_value(qc, reg_b, params.b)
    _load_value(qc, reg_c, params.c)
    _load_value(qc, reg_d, params.d)

    qmadd = build_qmadd_gate(n)
    qmsub = build_qmsub_gate(n)
    c_qmsub = build_c_qmsub_gate(n)

    # Step 1: Compute (a-b) into a with comp_ab; (c-d) into c with comp_cd.
    qc.append(c_qmsub, [comp_ab[0], *list(reg_a), *list(reg_b)])
    qc.append(c_qmsub, [comp_cd[0], *list(reg_c), *list(reg_d)])

    # Step 2: result1 = (a-b) + (c-d)
    qc.append(qmadd, _reg_args(result1, reg_a))
    qc.append(qmadd, _reg_args(result1, reg_c))

    # Step 3: result2 = (a-b) - (c-d)
    qc.append(qmadd, _reg_args(result2, reg_a))
    qc.append(qmsub, _reg_args(result2, reg_c))

    # Step 4: Restore a and c (undo subtractions)
    qc.append(qmadd, _reg_args(reg_a, reg_b))
    qc.append(qmadd, _reg_args(reg_c, reg_d))

    # Step 5: Compute reg_a = (a+b) - (c+d)  （在最小值交换之前）
    qc.append(qmadd, _reg_args(reg_a, reg_b))
    qc.append(qmsub, _reg_args(reg_a, reg_c))
    qc.append(qmsub, _reg_args(reg_a, reg_d))

    # Step 6: Pairwise mins using cswap so that b←min(a,b), d←min(c,d)
    for i in range(n):
        qc.cswap(comp_ab[0], reg_a[i], reg_b[i])
    for i in range(n):
        qc.cswap(comp_cd[0], reg_c[i], reg_d[i])

    # --- Stage 7: Get global min(a,b,c,d) ---
    print("Stage 7: Getting global min and cleaning up...")
    # Restore reg_b to |min(a,b)>
    qc.append(qmadd, _reg_args(reg_b, reg_d))
    # CSWAP to get min(a,b,c,d) into reg_d
    for i in range(n):
        qc.cswap(comp_min[0], reg_b[i], reg_d[i])

    qc.barrier()
    print("Circuit construction complete.")
    
    return qc


# ----------------------------------------------------------------
# CORRECTED MEASUREMENT AND PARSING SECTION
# ----------------------------------------------------------------

if __name__ == "__main__":
    params = ArithmeticParams()
    qc = build_full_circuit(params)
    
    # 1. Define ClassicalRegisters ONLY for the results we want to verify
    n = params.n
    cr_a = ClassicalRegister(n, 'ca')
    cr_d = ClassicalRegister(n, 'cd')
    cr_res1 = ClassicalRegister(n, 'cres1')
    cr_res2 = ClassicalRegister(n, 'cres2')

    # Add these new classical registers to the circuit
    qc.add_register(cr_a, cr_d, cr_res1, cr_res2)

    # 2. Measure ONLY the target registers into their corresponding classical registers
    print("Measuring target registers: reg_a, reg_d, result1, result2...")
    # Get registers from circuit by name
    reg_a = next(reg for reg in qc.qregs if reg.name == "a")
    reg_d = next(reg for reg in qc.qregs if reg.name == "d")
    result1 = next(reg for reg in qc.qregs if reg.name == "result1")
    result2 = next(reg for reg in qc.qregs if reg.name == "result2")
    
    qc.measure(reg_a, cr_a)
    qc.measure(reg_d, cr_d)
    qc.measure(result1, cr_res1)
    qc.measure(result2, cr_res2)

    # 3. Run the simulation
    print("Running simulation...")
    simulator = AerSimulator()
    # Transpile the circuit to decompose custom gates into basis gates
    print("Transpiling circuit to decompose custom gates...")
    qc_transpiled = transpile(qc, simulator)
    job = simulator.run(qc_transpiled, shots=8192)
    result = job.result()
    # Get counts only for our measurement registers
    counts = result.get_counts(qc_transpiled)

    print("\n--- Simulation Results ---")

    # 4. A simpler, correct way to parse and display the results
    print(f"Top 5 measurement outcomes (format: res2 res1 d a):")
    # Sort counts by value in descending order
    sorted_counts = sorted(counts.items(), key=lambda item: item[1], reverse=True)

    for i, (meas_result, count) in enumerate(sorted_counts[:5]):
        # Parse the measurement result string
        # Qiskit returns results as space-separated strings for each classical register
        # The order is reverse of how registers were added to the circuit
        # Since we added cr_a, cr_d, cr_res1, cr_res2 in that order,
        # the result order is: cr_res2 cr_res1 cr_d cr_a
        bits = meas_result.split(' ')
        
        # Debug: print the number of parts
        if i == 0:
            print(f"Debug: Measurement string has {len(bits)} parts")
            print(f"Debug: First measurement: {meas_result}")
        
        # Extract the 4 measurement registers (last 4 parts)
        # Format should be: ... cr_res2 cr_res1 cr_d cr_a
        if len(bits) >= 4:
            # Take the last 4 parts (our measurement registers)
            res2_meas_str = bits[-4]  # cr_res2 (result2)
            res1_meas_str = bits[-3]  # cr_res1 (result1)
            d_meas_str = bits[-2]     # cr_d (reg_d)
            a_meas_str = bits[-1]     # cr_a (reg_a)
        elif len(bits) == 1:
            # Single string format - need to split by register size
            full_str = bits[0]
            # Reverse order: cr_res2, cr_res1, cr_d, cr_a
            res2_meas_str = full_str[0:n]
            res1_meas_str = full_str[n:2*n]
            d_meas_str = full_str[2*n:3*n]
            a_meas_str = full_str[3*n:4*n]
        else:
            # Fallback
            print(f"Warning: Unexpected measurement format with {len(bits)} parts")
            res2_meas_str = bits[0] if len(bits) > 0 else '0' * n
            res1_meas_str = bits[1] if len(bits) > 1 else '0' * n
            d_meas_str = bits[2] if len(bits) > 2 else '0' * n
            a_meas_str = bits[3] if len(bits) > 3 else '0' * n
        
        a_val = int(a_meas_str, 2)
        d_val = int(d_meas_str, 2)
        res1_val = int(res1_meas_str, 2)
        res2_val = int(res2_meas_str, 2)
        
        print(f"#{i+1}: Freq={count/8192:.2%} | Outcome: {meas_result}")
        print(f"    Parsed: reg_a = {a_val}, reg_d = {d_val}, result1 = {res1_val}, result2 = {res2_val}\n")

    # Theoretical results for a=7, b=2, c=5, d=1
    print("\n--- Theoretical Expectations ---")
    min_abcd = 1        # min(7,2,5,1)
    ab_cd_sum = 9       # (7-2)+(5-1) = 5+4
    ab_cd_sub = 1       # (7-2)-(5-1) = 5-4
    apb_cmd_sub = 3     # (7+2)-(5+1) = 9-6

    print(f"Expected: reg_a ( (a+b)-(c+d) ) = {apb_cmd_sub}")
    print(f"Expected: reg_d ( min(a,b,c,d) ) = {min_abcd}")
    print(f"Expected: result1 ( (a-b)+(c-d) ) = {ab_cd_sum}")
    print(f"Expected: result2 ( (a-b)-(c-d) ) = {ab_cd_sub}")