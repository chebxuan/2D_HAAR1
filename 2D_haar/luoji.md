步骤一：计算 a-b 和 c-d (使用 QMADD/QMSUB)
我们使用 QMADD/QMSUB（如 Engin Şahin 图6 QMADD，它内部包含 QFT + MADD/MSUB + IQFT）来计算 a-b 和 c-d。
计算 a-b 并存储在 reg_a: QMSUB(目标=|reg_a⟩, 控制=|reg_b⟩) (注意：QMADD/QMSUB通常是 目标 = 目标 - 控制)
操作: reg_c 状态由 |c⟩ 变为 |c-d⟩。reg_d 保持 |d⟩。
|Ψ₁⟩：步骤一完成时 (所有寄存器均处于计算基态)
|a<b⟩_₁ |a-b⟩_₈ |b⟩_₈ |0⟩_₈ |c<d⟩_₁ |c-d⟩_₈ |d⟩_₈ |0⟩_₈

步骤二：累加 c-d 到 result₁ (使用 QMADD)
操作: QMADD(目标=|result₁⟩, 控制=|reg_a⟩) (即 result₁ = result₁ + (a-b))
操作: QMADD(目标=|result₁⟩, 控制=|reg_c⟩) (即 result₁ = result₁ + (c-d))
|Ψ₂⟩：步骤二完成时 (所有寄存器均处于计算基态)
|a<b⟩_₁ |a-b⟩_₈ |b⟩_₈ |(a-b)+(c-d)⟩_₈ |c<d⟩_₁ |c-d⟩_₈ |d⟩_₈ |0⟩_₈

步骤三：计算 (a-b)-(c-d) 并存储到 result₂
复制 a-b 到 result₂: (使用 n 个 CNOT 门)
result₂ 从 |0⟩ 变为 |a-b⟩。
在 result₂ 上执行减法 result₂ = result₂ - (c-d): QMSUB(目标=|result₂⟩, 控制=|reg_c⟩)
result₂ 从 |a-b⟩ 变为 |(a-b)-(c-d)⟩。
|Ψ₃⟩：步骤三完成时 (所有寄存器均处于计算基态)
|a<b⟩_₁ |a-b⟩_₈ |b⟩_₈ |(a-b)+(c-d)⟩_₈ |c<d⟩_₁ |c-d⟩_₈ |d⟩_₈ |(a-b)-(c-d)⟩_₈

步骤四：原始值恢复，利用 QMADD将处于差值状态的寄存器精确恢复为原始值 $|a\rangle$ 和 $|c\rangle$，并且利用比较结果控制 `CSWAP`，将 $(a,b)$ 和 $(c,d)$ 重新排序为 $(\max, \min)$ 。

