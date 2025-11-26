"""
可逆整数逆变换实现

本模块实现形态学哈尔小波的逆变换，用于从分解结果重构原始输入。
关键点：
1. UR 算子的逆操作需要 LSB 信息
2. 所有操作按相反顺序执行
3. 使用保留的比较位和 LSB 信息
"""

from __future__ import annotations

from dataclasses import dataclass
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister, transpile
from qiskit_aer import AerSimulator

from c_qmsub_gate import build_c_qmsub_gate
from qmadd_gate import build_qmadd_gate
from qmsub_gate import build_qmsub_gate


@dataclass(frozen=True)
class InverseParams:
    """逆变换参数"""
    data_bits: int = 4
    # 输入：分解后的系数
    result1: int  # ⌊((a-b)+(c-d))/2⌋
    result2: int  # ⌊((a-b)-(c-d))/2⌋
    reg_a: int    # ⌊((a+b)-(c+d))/2⌋
    reg_d: int    # min(a,b,c,d)
    # 辅助信息（用于重构）
    comp_ab: int  # 比较位：1 if a < b else 0
    comp_cd: int  # 比较位：1 if c < d else 0
    comp_min: int # 比较位：1 if min(a,b) < min(c,d) else 0
    # LSB 信息（如果保留）
    lsb_res1: int = 0  # result1 的 LSB
    lsb_res2: int = 0  # result2 的 LSB
    lsb_reg_a: int = 0  # reg_a 的 LSB

    @property
    def arith_bits(self) -> int:
        return self.data_bits + 1

    @property
    def modulus(self) -> int:
        return 1 << self.data_bits


def apply_doubling(
    qc: QuantumCircuit,
    register: QuantumRegister,
    shift_anc,
    lsb_value: int,
    data_bits: int,
):
    """UR 的逆操作：将 ⌊a/2⌋ 恢复为原始值
    
    参数:
        register: 要恢复的寄存器（当前值为 ⌊a/2⌋）
        shift_anc: 辅助量子比特（用于存储恢复后的 LSB）
        lsb_value: 原始 LSB 值（0 或 1）
        data_bits: 数据位数
    """
    # 左移：将 register 左移一位
    for idx in range(len(register) - 1):
        qc.swap(register[idx], register[idx + 1])
    
    # 恢复 LSB：根据 lsb_value 设置最低位
    if lsb_value == 1:
        qc.x(register[0])
    
    # 如果 lsb_value 存储在 shift_anc 中，可以使用：
    # qc.cx(shift_anc, register[0])


def build_inverse_circuit(params: InverseParams) -> QuantumCircuit:
    """构造逆变换电路，从分解结果重构原始输入"""
    n = params.arith_bits

    # --- 量子寄存器 ---
    # 输入寄存器（存储分解结果）
    reg_a = QuantumRegister(n, "a")
    reg_b = QuantumRegister(n, "b")
    reg_c = QuantumRegister(n, "c")
    reg_d = QuantumRegister(n, "d")
    
    res1 = QuantumRegister(n, "res1")
    res2 = QuantumRegister(n, "res2")
    
    # 辅助寄存器
    anc_res1_shift = QuantumRegister(1, "anc_res1_shift")
    anc_res2_shift = QuantumRegister(1, "anc_res2_shift")
    anc_reg_a_shift = QuantumRegister(1, "anc_a_shift")
    
    anc_res1_guard = QuantumRegister(1, "anc_res1_guard")
    anc_res2_guard = QuantumRegister(1, "anc_res2_guard")
    anc_reg_a_guard = QuantumRegister(1, "anc_a_guard")
    
    # 比较位（从正向变换保留）
    comp_ab = QuantumRegister(1, "comp_ab")
    comp_cd = QuantumRegister(1, "comp_cd")
    comp_min = QuantumRegister(1, "comp_min")
    
    qc = QuantumCircuit(
        reg_a, reg_b, reg_c, reg_d,
        res1, res2,
        anc_res1_shift, anc_res2_shift, anc_reg_a_shift,
        anc_res1_guard, anc_res2_guard, anc_reg_a_guard,
        comp_ab, comp_cd, comp_min,
        name="InverseMorphologicalHaar",
    )
    
    # 初始化：加载分解结果
    from main_round import _set_initial_state
    _set_initial_state(qc, res1, params.result1, params.data_bits)
    _set_initial_state(qc, res2, params.result2, params.data_bits)
    _set_initial_state(qc, reg_a, params.reg_a, params.data_bits)
    _set_initial_state(qc, reg_d, params.reg_d, params.data_bits)
    
    # 加载比较位
    if params.comp_ab:
        qc.x(comp_ab[0])
    if params.comp_cd:
        qc.x(comp_cd[0])
    if params.comp_min:
        qc.x(comp_min[0])
    
    qmadd = build_qmadd_gate(n)
    qmsub = build_qmsub_gate(n)
    c_qmsub = build_c_qmsub_gate(n)
    
    # ============================================
    # 逆变换：按相反顺序执行正向变换的逆操作
    # ============================================
    
    # --- 逆 Stage 7: 恢复 min(a,b) 和 min(c,d) ---
    # 正向：CSWAP + QMADD
    # 逆向：CSWAP + QMSUB
    for idx in range(n):
        qc.cswap(comp_min[0], reg_b[idx], reg_d[idx])
    qc.append(qmsub, list(reg_b) + list(reg_d))
    qc.barrier()
    
    # --- 逆 Stage 6: 恢复 max(a,b) 和 max(c,d) ---
    # 正向：UR₃ + QMADD + QMSUB + C_QMSUB
    # 逆向：C_QMSUB⁻¹ + QMSUB⁻¹ + QMADD⁻¹ + UR₃⁻¹
    
    # 恢复 reg_a（需要 LSB）
    apply_doubling(
        qc, reg_a, anc_reg_a_shift[0], params.lsb_reg_a, params.data_bits
    )
    
    # 恢复 reg_b = min(a,b) - min(c,d)
    qc.append(qmsub, list(reg_a) + list(reg_b))  # reg_a -= reg_b
    qc.append(qmadd, list(reg_a) + list(reg_c))   # reg_a += reg_c
    # 注意：C_QMSUB 的逆操作比较复杂，需要根据 comp_min 恢复
    qc.barrier()
    
    # --- 逆 Stage 5: 恢复 a, b, c, d 的原始顺序 ---
    # 正向：CSWAP
    # 逆向：CSWAP（自逆）
    for idx in range(n):
        qc.cswap(comp_cd[0], reg_c[idx], reg_d[idx])
    for idx in range(n):
        qc.cswap(comp_ab[0], reg_a[idx], reg_b[idx])
    qc.barrier()
    
    # --- 逆 Stage 4: 恢复差值状态 ---
    # 正向：QMADD（恢复 a, c）
    # 逆向：QMSUB（恢复差值）
    qc.append(qmsub, list(reg_c) + list(reg_d))  # reg_c = reg_c - reg_d
    qc.append(qmsub, list(reg_a) + list(reg_b))  # reg_a = reg_a - reg_b
    qc.barrier()
    
    # --- 逆 Stage 3: 恢复 (a-b) 和 (c-d) ---
    # 正向：UR₂ + QMSUB + CNOT
    # 逆向：CNOT⁻¹ + QMADD + UR₂⁻¹
    
    # 恢复 result2 = (a-b) - (c-d)
    apply_doubling(
        qc, res2, anc_res2_shift[0], params.lsb_res2, params.data_bits
    )
    qc.append(qmadd, list(res2) + list(reg_c))  # res2 += reg_c
    # 复制 res2 到 reg_a（逆 CNOT）
    for idx in range(n):
        qc.cx(res2[idx], reg_a[idx])
    qc.barrier()
    
    # --- 逆 Stage 2: 恢复 (a-b) 和 (c-d) ---
    # 正向：UR₁ + QMADD ×2
    # 逆向：QMSUB ×2 + UR₁⁻¹
    
    # 恢复 result1 = (a-b) + (c-d)
    apply_doubling(
        qc, res1, anc_res1_shift[0], params.lsb_res1, params.data_bits
    )
    qc.append(qmsub, list(res1) + list(reg_c))  # res1 -= reg_c
    qc.append(qmsub, list(res1) + list(reg_a))  # res1 -= reg_a
    # 现在 res1 应该等于 0（或接近 0，由于取整误差）
    qc.barrier()
    
    # --- 逆 Stage 1: 恢复原始值 a, b, c, d ---
    # 正向：C_QMSUB
    # 逆向：C_QMSUB⁻¹（需要恢复 a, c）
    
    # 恢复 a = (a-b) + b
    qc.append(qmadd, list(reg_a) + list(reg_b))  # reg_a += reg_b
    # 恢复 c = (c-d) + d
    qc.append(qmadd, list(reg_c) + list(reg_d))  # reg_c += reg_d
    
    return qc


def test_inverse_transform():
    """测试逆变换"""
    # 原始输入
    original_a, original_b, original_c, original_d = 7, 2, 5, 1
    
    # 模拟正向变换的结果（需要从实际正向电路获取）
    # 这里使用理论值
    from main_round import ArithmeticParams
    params = ArithmeticParams(a=original_a, b=original_b, c=original_c, d=original_d)
    
    # 计算理论分解结果
    modulus = params.modulus
    result1 = ((original_a - original_b + original_c - original_d) % modulus) // 2
    result2 = ((original_a - original_b - (original_c - original_d)) % modulus) // 2
    reg_a = ((original_a + original_b - original_c - original_d) % modulus) // 2
    reg_d = min(original_a, original_b, original_c, original_d)
    
    # 比较位（需要从正向电路获取，这里假设）
    comp_ab = 1 if original_a < original_b else 0
    comp_cd = 1 if original_c < original_d else 0
    comp_min = 1 if min(original_a, original_b) < min(original_c, original_d) else 0
    
    # 构造逆变换参数
    inv_params = InverseParams(
        data_bits=4,
        result1=result1,
        result2=result2,
        reg_a=reg_a,
        reg_d=reg_d,
        comp_ab=comp_ab,
        comp_cd=comp_cd,
        comp_min=comp_min,
        lsb_res1=0,  # 需要从正向电路获取
        lsb_res2=0,  # 需要从正向电路获取
        lsb_reg_a=0,  # 需要从正向电路获取
    )
    
    # 构建逆电路
    inv_qc = build_inverse_circuit(inv_params)
    
    # 添加测量
    cr_a = ClassicalRegister(params.arith_bits, "c_a")
    cr_b = ClassicalRegister(params.arith_bits, "c_b")
    cr_c = ClassicalRegister(params.arith_bits, "c_c")
    cr_d = ClassicalRegister(params.arith_bits, "c_d")
    
    reg_a = next(reg for reg in inv_qc.qregs if reg.name == "a")
    reg_b = next(reg for reg in inv_qc.qregs if reg.name == "b")
    reg_c = next(reg for reg in inv_qc.qregs if reg.name == "c")
    reg_d = next(reg for reg in inv_qc.qregs if reg.name == "d")
    
    inv_qc.add_register(cr_a, cr_b, cr_c, cr_d)
    inv_qc.measure(reg_a, cr_a)
    inv_qc.measure(reg_b, cr_b)
    inv_qc.measure(reg_c, cr_c)
    inv_qc.measure(reg_d, cr_d)
    
    # 运行仿真
    simulator = AerSimulator(method="matrix_product_state")
    transpiled = transpile(inv_qc, simulator, optimization_level=0)
    result = simulator.run(transpiled, shots=1024).result()
    counts = result.get_counts(transpiled)
    
    print("\n--- Inverse Transform Results ---")
    print(f"Original: a={original_a}, b={original_b}, c={original_c}, d={original_d}")
    print(f"Decomposition: result1={result1}, result2={result2}, reg_a={reg_a}, reg_d={reg_d}")
    
    # 显示重构结果
    mask = modulus - 1
    sorted_counts = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    for idx, (meas_result, count) in enumerate(sorted_counts[:3]):
        print(f"#{idx+1}: Freq={count/1024:.2%} | {meas_result}")


if __name__ == "__main__":
    test_inverse_transform()

