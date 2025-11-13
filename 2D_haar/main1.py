import numpy as np
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, Aer, execute
from modules import build_qmadd_gate, build_qmsub_gate, build_c_qmsub_gate

# --- 1. SETUP ---
n = 4  # Number of qubits for each register

# Build the reusable arithmetic gates
print("Building arithmetic gates...")
qmadd_gate = build_qmadd_gate(n)
qmsub_gate = build_qmsub_gate(n)
c_qmsub_gate = build_c_qmsub_gate(n)

# Define all quantum registers
print("Defining quantum registers...")
reg_a = QuantumRegister(n, 'a')
reg_b = QuantumRegister(n, 'b')
reg_c = QuantumRegister(n, 'c')
reg_d = QuantumRegister(n, 'd')
result1 = QuantumRegister(n, 'res1')
result2 = QuantumRegister(n, 'res2')
comp_ab = QuantumRegister(1, 'comp_ab')
comp_cd = QuantumRegister(1, 'comp_cd')
comp_new = QuantumRegister(1, 'comp_new')

# Create the main Quantum Circuit
qc = QuantumCircuit(reg_a, reg_b, reg_c, reg_d, result1, result2, comp_ab, comp_cd, comp_new)

# --- 2. INITIAL STATE ---
a_val = 7
b_val = 2
c_val = 5
d_val = 1
print(f"Setting initial state: a={a_val}, b={b_val}, c={c_val}, d={d_val}")

def set_initial_state(qc, reg, value, n_bits):
    """Sets a register to a specific value, handling endianness."""
    binary_val = format(value, f'0{n_bits}b')[::-1] # Reverse for Qiskit's little-endian
    for i in range(n_bits):
        if binary_val[i] == '1':
            qc.x(reg[i])

set_initial_state(qc, reg_a, a_val, n)
set_initial_state(qc, reg_b, b_val, n)
set_initial_state(qc, reg_c, c_val, n)
set_initial_state(qc, reg_d, d_val, n)
qc.barrier()

# --- 3. CIRCUIT LOGIC (STAGES 1-7) ---

# --- Stage 1: Parallel compare and subtract ---
print("Stage 1: Performing parallel subtractions...")
qc.append(c_qmsub_gate, comp_ab[:] + reg_a[:] + reg_b[:])
qc.append(c_qmsub_gate, comp_cd[:] + reg_c[:] + reg_d[:])
qc.barrier()

# --- Stage 2: Calculate (a-b)+(c-d) ---
print("Stage 2: Calculating (a-b)+(c-d)...")
qc.append(qmadd_gate, result1[:] + reg_a[:])
qc.append(qmadd_gate, result1[:] + reg_c[:])
qc.barrier()

# --- Stage 3: Calculate (a-b)-(c-d) ---
print("Stage 3: Calculating (a-b)-(c-d)...")
for i in range(n):
    qc.cnot(reg_a[i], result2[i])
qc.append(qmsub_gate, result2[:] + reg_c[:])
qc.barrier()

# --- Stage 4: Restore original values a and c ---
print("Stage 4: Restoring original values a and c...")
qc.append(qmadd_gate, reg_a[:] + reg_b[:])
qc.append(qmadd_gate, reg_c[:] + reg_d[:])
qc.barrier()

# --- Stage 5: Get local max/min pairs ---
print("Stage 5: Sorting local max/min pairs...")
for i in range(n):
    qc.cswap(comp_ab[0], reg_a[i], reg_b[i])
    qc.cswap(comp_cd[0], reg_c[i], reg_d[i])
qc.barrier()

# --- Stage 6: Global arithmetic and comparison ---
print("Stage 6: Performing global arithmetic and comparison...")
# Compare min(a,b) and min(c,d)
qc.append(c_qmsub_gate, comp_new[:] + reg_b[:] + reg_d[:])
# Calculate (a+b)-(c+d) in reg_a
qc.append(qmsub_gate, reg_a[:] + reg_c[:]) # reg_a = max(a,b)-max(c,d)
qc.append(qmadd_gate, reg_a[:] + reg_b[:]) # reg_a += min(a,b)-min(c,d) => (a+b)-(c+d)
qc.barrier()

# --- Stage 7: Get global min(a,b,c,d) ---
print("Stage 7: Getting global min...")
# Restore reg_b to |min(a,b)>
qc.append(qmadd_gate, reg_b[:] + reg_d[:])
# CSWAP to get min(a,b,c,d) into reg_d
for i in range(n):
    qc.cswap(comp_new[0], reg_b[i], reg_d[i])
qc.barrier()

print("Circuit construction complete.")

# --- 4. MEASUREMENT AND EXECUTION ---

# Define ClassicalRegisters ONLY for the results we want to verify
cr_a = ClassicalRegister(n, 'ca')
cr_d = ClassicalRegister(n, 'cd')
cr_res1 = ClassicalRegister(n, 'cres1')
cr_res2 = ClassicalRegister(n, 'cres2')

# Add these new classical registers to the circuit
qc.add_register(cr_a, cr_d, cr_res1, cr_res2)

# Measure ONLY the target registers into their corresponding classical registers
print("Measuring target registers: reg_a, reg_d, result1, result2...")
qc.measure(reg_a, cr_a)
qc.measure(reg_d, cr_d)
qc.measure(result1, cr_res1)
qc.measure(result2, cr_res2)

# Run the simulation
print("Running simulation...")
backend = Aer.get_backend('qasm_simulator')
job = execute(qc, backend, shots=8192)
result = job.result()
counts = result.get_counts(qc)

print("\n--- Simulation Results ---")

# A simpler, correct way to parse and display the results
print(f"Top 5 measurement outcomes (format: res2 res1 d a):")
# Sort counts by value in descending order
sorted_counts = sorted(counts.items(), key=lambda item: item[1], reverse=True)

for i, (meas_result, count) in enumerate(sorted_counts[:5]):
    # The result string from Qiskit is spaced, with registers ordered from right to left
    # as they were added. Our add order was cr_a, cr_d, cr_res1, cr_res2.
    # Qiskit's format: 'cres2_val cres1_val cd_val ca_val'
    bits = meas_result.split(' ')
    
    a_meas_str = bits[3]
    d_meas_str = bits[2]
    res1_meas_str = bits[1]
    res2_meas_str = bits[0]
    
    a_val = int(a_meas_str, 2)
    d_val = int(d_meas_str, 2)
    res1_val = int(res1_meas_str, 2)
    res2_val = int(res2_meas_str, 2)
    
    print(f"#{i+1}: Freq={count/8192:.2%} | Outcome: {meas_result}")
    print(f"    Parsed: reg_a = {a_val}, reg_d = {d_val}, result1 = {res1_val}, result2 = {res2_val}\n")

# --- 5. THEORETICAL VERIFICATION ---

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