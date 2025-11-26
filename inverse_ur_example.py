"""
逆 UR 算子实现示例

UR 算子：UR |a⟩ = |⌊a/2⌋⟩，LSB 存储在 shift_anc 中
逆 UR 算子：UR⁻¹ |k⟩|lsb⟩ → |2k + lsb⟩

这个文件展示了如何实现逆 UR 算子，用于可逆重构。
"""

from qiskit import QuantumCircuit, QuantumRegister


def apply_doubling(
    qc: QuantumCircuit,
    register: QuantumRegister,
    shift_anc,  # 包含 LSB 的辅助寄存器
    guard_anc,
    data_bits: int,
):
    """
    逆 UR 算子：UR⁻¹ |k⟩|lsb⟩ → |2k + lsb⟩
    
    参数:
        qc: 量子电路
        register: 要恢复的寄存器（当前包含 ⌊a/2⌋）
        shift_anc: 包含 LSB 的辅助寄存器
        guard_anc: guard bit 辅助寄存器
        data_bits: 数据位数
    """
    guard_idx = data_bits  # guard bit 位置
    
    # 步骤 1: 左移 register（乘以 2）
    # 从低位到高位，将每一位向左移动一位
    for idx in range(data_bits - 1, -1, -1):
        qc.swap(register[idx], register[idx + 1])
    
    # 步骤 2: 将 shift_anc 中的 LSB 加回 register[0]
    # 使用 CNOT 将 LSB 复制到 register[0]
    qc.cx(shift_anc, register[0])
    
    # 步骤 3: 处理 guard bit（如果需要）
    # 如果原始值有溢出，需要恢复 guard bit
    # 这里简化处理，实际可能需要根据 guard_anc 的状态调整
    
    # 注意：register[guard_idx] 现在应该是 0（因为左移后最高位是 0）
    # 如果需要恢复 guard bit，可以根据 guard_anc 的状态设置


def build_inverse_ur_circuit_example():
    """
    构建一个简单的逆 UR 电路示例
    演示如何从 ⌊a/2⌋ 和 LSB 恢复原始值 a
    """
    data_bits = 4
    arith_bits = data_bits + 1  # 包含 guard bit
    
    # 寄存器
    reg = QuantumRegister(arith_bits, "reg")  # 包含 ⌊a/2⌋
    shift_anc = QuantumRegister(1, "shift_anc")  # 包含 LSB
    guard_anc = QuantumRegister(1, "guard_anc")  # guard bit
    
    qc = QuantumCircuit(reg, shift_anc, guard_anc, name="InverseUR")
    
    # 应用逆 UR 算子
    apply_doubling(qc, reg, shift_anc[0], guard_anc[0], data_bits)
    
    return qc


def verify_inverse_ur():
    """
    验证逆 UR 算子的正确性
    
    测试：对于 a = 2k 或 a = 2k+1，验证 UR⁻¹(UR(a)) = a
    """
    from qiskit_aer import AerSimulator
    from qiskit import transpile
    
    data_bits = 4
    arith_bits = data_bits + 1
    
    # 测试几个值
    test_values = [5, 6, 7, 8, 9, 10]
    
    simulator = AerSimulator(method="matrix_product_state")
    
    print("验证逆 UR 算子：")
    print("=" * 50)
    
    for a in test_values:
        # 正向：UR(a) = ⌊a/2⌋
        k = a // 2
        lsb = a % 2
        
        # 构建正向电路（简化版）
        reg = QuantumRegister(arith_bits, "reg")
        shift_anc = QuantumRegister(1, "shift_anc")
        guard_anc = QuantumRegister(1, "guard_anc")
        
        qc_forward = QuantumCircuit(reg, shift_anc, guard_anc)
        
        # 初始化：reg = a, shift_anc = 0
        bits = format(a % (1 << data_bits), f"0{data_bits}b")[::-1]
        for idx, bit in enumerate(bits):
            if bit == "1":
                qc_forward.x(reg[idx])
        
        # 应用 UR（简化版：右移）
        for idx in range(arith_bits - 1, -1, -1):
            qc_forward.swap(reg[idx], shift_anc[0])
        
        # 现在 reg 应该包含 ⌊a/2⌋，shift_anc 包含 LSB
        
        # 构建逆电路
        qc_inverse = QuantumCircuit(reg, shift_anc, guard_anc)
        apply_doubling(qc_inverse, reg, shift_anc[0], guard_anc[0], data_bits)
        
        # 组合正向和逆电路
        qc_combined = qc_forward.compose(qc_inverse)
        
        # 测量
        cr = qc_combined.add_register(qc_combined.cregs[0] if qc_combined.cregs else None)
        if not qc_combined.cregs:
            from qiskit import ClassicalRegister
            cr = ClassicalRegister(arith_bits, "c")
            qc_combined.add_register(cr)
        
        qc_combined.measure(reg, cr)
        
        # 运行
        transpiled = transpile(qc_combined, simulator, optimization_level=0)
        result = simulator.run(transpiled, shots=1024).result()
        counts = result.get_counts(transpiled)
        
        # 检查结果
        mask = (1 << data_bits) - 1
        recovered = int(list(counts.keys())[0], 2) & mask
        
        status = "✓" if recovered == a else "✗"
        print(f"{status} a={a:2d} → UR(a)={k:2d}, LSB={lsb} → UR⁻¹={recovered:2d}")
    
    print("=" * 50)
    print("注意：这是一个简化示例，实际实现需要考虑 guard bit 和模运算")


if __name__ == "__main__":
    # 构建示例电路
    qc = build_inverse_ur_circuit_example()
    print("逆 UR 电路示例：")
    print(qc.draw(output="text"))
    print("\n")
    
    # 验证（需要完整的正向 UR 实现）
    # verify_inverse_ur()

