步骤一：计算 a-b 和 c-d (使用 QMADD/QMSUB)
我们使用 QMADD/QMSUB（如 Engin Şahin 图6 QMADD，它内部包含 QFT + MADD/MSUB + IQFT）来计算 a-b 和 c-d。
计算 a-b 并存储在 reg_a: QMSUB(目标=|reg_a⟩, 控制=|reg_b⟩) (注意：QMADD/QMSUB通常是 目标 = 目标 - 控制)
操作: reg_c 状态由 |c⟩ 变为 |c-d⟩。reg_d 保持 |d⟩。
|Ψ₁⟩：步骤一完成时 (所有寄存器均处于计算基态)
|a<b⟩_₁ |a-b⟩_₈ |b⟩_₈ |0⟩_₈ |c<d⟩_₁ |c-d⟩_₈ |d⟩_₈ |0⟩_₈

步骤二：累加 a-b 和 c-d 到 result₁ (使用 QMADD)
操作: QMADD(目标=|result₁⟩, 控制=|reg_a⟩) (即 result₁ = result₁ + (a-b))
操作: QMADD(目标=|result₁⟩, 控制=|reg_c⟩) (即 result₁ = result₁ + (c-d))
|Ψ₂⟩：步骤二完成时 (所有寄存器均处于计算基态)
|a<b⟩_₁ |a-b⟩_₈ |b⟩_₈ |(a-b)+(c-d)⟩_₈ |c<d⟩_₁ |c-d⟩_₈ |d⟩_₈ |0⟩_₈

（新增）为了保证模减比较正确，所有算术寄存器都扩展为 data_bits+1 位（最末一位为 guard bit，初始为 |0⟩）

#UR₁：对 |(a-b)+(c-d)⟩ 施加量子舍入算子 UR，得到 floor((a-b)+(c-d))/2#

步骤三：计算 (a-b)-(c-d) 并存储到 result₂
复制 a-b 到 result₂: (使用 n 个 CNOT 门)
result₂ 从 |0⟩ 变为 |a-b⟩。
在 result₂ 上执行减法 result₂ = result₂ - (c-d): QMSUB(目标=|result₂⟩, 控制=|reg_c⟩)
result₂ 从 |a-b⟩ 变为 |(a-b)-(c-d)⟩。
|Ψ₃⟩：步骤三完成时 (所有寄存器均处于计算基态)
|a<b⟩_₁ |a-b⟩_₈ |b⟩_₈ |(a-b)+(c-d)⟩_₈ |c<d⟩_₁ |c-d⟩_₈ |d⟩_₈ |(a-b)-(c-d)⟩_₈
#UR₂：对 |(a-b)-(c-d)⟩ 施加 UR，得到 floor((a-b)-(c-d))/2#


步骤四：原始值恢复，利用 QMADD将处于差值状态的寄存器精确恢复为原始值 $|a\rangle$ 和 $|c\rangle$，并且利用比较结果控制 `CSWAP`，将 $(a,b)$ 和 $(c,d)$ 重新排序为 $(\max, \min)$ 。此时：
reg_a: |max(a,b)mod 2⁸⟩_₈
reg_b: |min(a,b)mod 2⁸⟩_₈
comp_cd: |1⟩ 如果 c<d, 否则 |0⟩
reg_c: |max(c,d)mod 2⁸⟩_₈
reg_d: |min(c,d)mod 2⁸⟩_₈
result₁: 整数「1/2|(a-b)+(c-d)mod 2⁸⟩_₈」
result₂: 整数「1/2|(a-b)-(c-d)mod 2⁸⟩_₈」


步骤五：得到$\min(a,b,c,d)$ 和  (max(a,b) - max(c,d)) + (min(a,b) - min(c,d)) 也就是|(a+b) - (c+d) mod 2⁸⟩_₈。先用C_QMSUB_Gate比较 min(a,b) 和 min(c,d)，reg_b 被临时修改为 min(a,b) - min(c,d)，comp_new 寄存器被设置为 1 (如果 min(a,b) < min(c,d)) 或 0 (如果 min(a,b) >= min(c,d))。这个比特现在是找到全局最小值的关键。comp_new 是 1 (即min(a,b)更小)，门会交换 reg_b 和 reg_d 的内容。reg_d 已经成功获得了全局最小值 min(a,b,c,d)，此时：
reg_a: |max(a,b)mod 2⁸⟩_₈
reg_b: min(a,b) - min(c,d)
comp_cd: |1⟩ 如果 c<d, 否则 |0⟩
reg_c: |max(c,d)mod 2⁸⟩_₈
reg_d: min(a,b,c,d)
result₁: 整数「1/2|(a-b)+(c-d)mod 2⁸⟩_₈」
result₂: 整数「1/2|(a-b)-(c-d)mod 2⁸⟩_₈」


接着：计算 (max(a,b) - max(c,d)) + (min(a,b) - min(c,d))，#并且1/2舍入，向下取整。 
对 reg_a 和 reg_c 利用QMSUB执行一次标准的模减法，reg_a 的值现在变为 max(a,b) - max(c,d)。利用QMADD将 reg_b 中刚刚计算出的 min(a,b) - min(c,d) 加到 reg_a 上，reg_a 的最终值变为 (max(a,b) - max(c,d)) + (min(a,b) - min(c,d)).
最终：
reg_a: {1/2「(max(a,b) - max(c,d)) + (min(a,b) - min(c,d))」}. #UR₃，向下取整#
reg_b: min(a,b) - min(c,d)
comp_cd: |1⟩ 如果 c<d, 否则 |0⟩
reg_c: |max(c,d)mod 2⁸⟩_₈
reg_d: min(a,b,c,d)
result₁: 整数「1/2|(a-b)+(c-d)mod 2⁸⟩_₈」
result₂: 整数「1/2|(a-b)-(c-d)mod 2⁸⟩_₈」


#关于舍入算子 UR#
UR |a⟩ = |⌊a/2⌋⟩, a ∈ ℤ
实现要点：
1. 所有算术寄存器增加 guard bit（data_bits+1 位），初始置 0；
2. 将 guard bit 拷贝到辅助量子比特并从寄存器中清除（对应借位/溢出信息）；
3. 使用额外的 shift anc 逐位 swap，实现量子右移并保留 LSB；
4. 结果只读取低 data_bits 位（即对 2^{data_bits} 取模）。
这种方式保持了量子操作的线性和可逆性，也保证了比较器不会再因为模减回绕而失效。



