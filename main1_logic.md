# main1.py 执行逻辑说明文档

## 初始状态
初始值：a=7, b=2, c=5, d=1 (n=4位)
寄存器状态：
- reg_a: |a⟩_₄ = |7⟩
- reg_b: |b⟩_₄ = |2⟩
- reg_c: |c⟩_₄ = |5⟩
- reg_d: |d⟩_₄ = |1⟩
- result1: |0⟩_₄
- result2: |0⟩_₄
- comp_ab: |0⟩_₁
- comp_cd: |0⟩_₁
- comp_new: |0⟩_₁

## 步骤一：计算 a-b 和 c-d (使用 C_QMSUB)
我们使用 C_QMSUB 门（内部包含 QMSUB + MSB复制到比较位）来计算 a-b 和 c-d，同时得到比较结果。

**操作 1：** C_QMSUB(comp_ab, reg_a, reg_b)
- 执行 QMSUB：reg_a = reg_a - reg_b = a - b
- 复制 reg_a 的 MSB 到 comp_ab：comp_ab = 1 如果 a < b，否则 comp_ab = 0
- reg_b 保持不变：|b⟩

**操作 2：** C_QMSUB(comp_cd, reg_c, reg_d)
- 执行 QMSUB：reg_c = reg_c - reg_d = c - d
- 复制 reg_c 的 MSB 到 comp_cd：comp_cd = 1 如果 c < d，否则 comp_cd = 0
- reg_d 保持不变：|d⟩

**|Ψ₁⟩：步骤一完成时 (所有寄存器均处于计算基态)**
```
|comp_ab⟩_₁ |reg_a⟩_₄ |reg_b⟩_₄ |result1⟩_₄ |comp_cd⟩_₁ |reg_c⟩_₄ |reg_d⟩_₄ |result2⟩_₄
|a<b⟩_₁ |a-b⟩_₄ |b⟩_₄ |0⟩_₄ |c<d⟩_₁ |c-d⟩_₄ |d⟩_₄ |0⟩_₄
```

**实际值示例（a=7, b=2, c=5, d=1）：**
- comp_ab = |0⟩ (因为 7 >= 2)
- reg_a = |7-2⟩ = |5⟩
- reg_b = |2⟩
- comp_cd = |0⟩ (因为 5 >= 1)
- reg_c = |5-1⟩ = |4⟩
- reg_d = |1⟩

## 步骤二：累加 a-b 和 c-d 到 result₁ (使用 QMADD)
**操作 1：** QMADD(目标=|result₁⟩, 控制=|reg_a⟩)
- result₁ 从 |0⟩ 变为 |0 + (a-b)⟩ = |a-b⟩

**操作 2：** QMADD(目标=|result₁⟩, 控制=|reg_c⟩)
- result₁ 从 |a-b⟩ 变为 |(a-b) + (c-d)⟩

**|Ψ₂⟩：步骤二完成时 (所有寄存器均处于计算基态)**
```
|comp_ab⟩_₁ |reg_a⟩_₄ |reg_b⟩_₄ |result1⟩_₄ |comp_cd⟩_₁ |reg_c⟩_₄ |reg_d⟩_₄ |result2⟩_₄
|a<b⟩_₁ |a-b⟩_₄ |b⟩_₄ |(a-b)+(c-d)⟩_₄ |c<d⟩_₁ |c-d⟩_₄ |d⟩_₄ |0⟩_₄
```

**实际值示例（a=7, b=2, c=5, d=1）：**
- result1 = |5+4⟩ = |9⟩

## 步骤三：计算 (a-b)-(c-d) 并存储到 result₂
**操作 1：** 复制 a-b 到 result₂ (使用 n 个 CNOT 门)
- 对每个 i：CNOT(reg_a[i], result2[i])
- result₂ 从 |0⟩ 变为 |a-b⟩

**操作 2：** QMSUB(目标=|result₂⟩, 控制=|reg_c⟩)
- result₂ 从 |a-b⟩ 变为 |(a-b) - (c-d)⟩

**|Ψ₃⟩：步骤三完成时 (所有寄存器均处于计算基态)**
```
|comp_ab⟩_₁ |reg_a⟩_₄ |reg_b⟩_₄ |result1⟩_₄ |comp_cd⟩_₁ |reg_c⟩_₄ |reg_d⟩_₄ |result2⟩_₄
|a<b⟩_₁ |a-b⟩_₄ |b⟩_₄ |(a-b)+(c-d)⟩_₄ |c<d⟩_₁ |c-d⟩_₄ |d⟩_₄ |(a-b)-(c-d)⟩_₄
```

**实际值示例（a=7, b=2, c=5, d=1）：**
- result2 = |5-4⟩ = |1⟩

## 步骤四：原始值恢复，利用 QMADD 将处于差值状态的寄存器精确恢复为原始值 |a⟩ 和 |c⟩
**操作 1：** QMADD(目标=|reg_a⟩, 控制=|reg_b⟩)
- reg_a 从 |a-b⟩ 变为 |(a-b) + b⟩ = |a⟩

**操作 2：** QMADD(目标=|reg_c⟩, 控制=|reg_d⟩)
- reg_c 从 |c-d⟩ 变为 |(c-d) + d⟩ = |c⟩

**恢复后状态：**
```
|comp_ab⟩_₁ |reg_a⟩_₄ |reg_b⟩_₄ |result1⟩_₄ |comp_cd⟩_₁ |reg_c⟩_₄ |reg_d⟩_₄ |result2⟩_₄
|a<b⟩_₁ |a⟩_₄ |b⟩_₄ |(a-b)+(c-d)⟩_₄ |c<d⟩_₁ |c⟩_₄ |d⟩_₄ |(a-b)-(c-d)⟩_₄
```

**实际值示例（a=7, b=2, c=5, d=1）：**
- reg_a = |7⟩
- reg_c = |5⟩

## 步骤五：利用比较结果控制 CSWAP，将 (a,b) 和 (c,d) 重新排序为 (max, min)
**操作 1：** CSWAP(comp_ab[0], reg_a[i], reg_b[i]) 对每个 i
- 如果 comp_ab = 1 (即 a < b)：交换 reg_a 和 reg_b
  - 交换后：reg_a = |b⟩, reg_b = |a⟩
- 如果 comp_ab = 0 (即 a >= b)：不交换
  - 保持不变：reg_a = |a⟩, reg_b = |b⟩
- **结果：** reg_a = |max(a,b)⟩, reg_b = |min(a,b)⟩

**操作 2：** CSWAP(comp_cd[0], reg_c[i], reg_d[i]) 对每个 i
- 如果 comp_cd = 1 (即 c < d)：交换 reg_c 和 reg_d
  - 交换后：reg_c = |d⟩, reg_d = |c⟩
- 如果 comp_cd = 0 (即 c >= d)：不交换
  - 保持不变：reg_c = |c⟩, reg_d = |d⟩
- **结果：** reg_c = |max(c,d)⟩, reg_d = |min(c,d)⟩

**|Ψ₄⟩：步骤五完成时 (所有寄存器均处于计算基态)**
```
|comp_ab⟩_₁ |reg_a⟩_₄ |reg_b⟩_₄ |result1⟩_₄ |comp_cd⟩_₁ |reg_c⟩_₄ |reg_d⟩_₄ |result2⟩_₄
|a<b⟩_₁ |max(a,b)⟩_₄ |min(a,b)⟩_₄ |(a-b)+(c-d)⟩_₄ |c<d⟩_₁ |max(c,d)⟩_₄ |min(c,d)⟩_₄ |(a-b)-(c-d)⟩_₄
```

**实际值示例（a=7, b=2, c=5, d=1）：**
- comp_ab = |0⟩ (7 >= 2，不交换)
- reg_a = |7⟩ = max(7,2)
- reg_b = |2⟩ = min(7,2)
- comp_cd = |0⟩ (5 >= 1，不交换)
- reg_c = |5⟩ = max(5,1)
- reg_d = |1⟩ = min(5,1)

## 步骤六：全局算术和比较
**操作 1：** C_QMSUB(comp_new, reg_b, reg_d)
- 执行 QMSUB：reg_b = reg_b - reg_d = min(a,b) - min(c,d)
- 复制 reg_b 的 MSB 到 comp_new：comp_new = 1 如果 min(a,b) < min(c,d)，否则 comp_new = 0
- reg_d 保持不变：|min(c,d)⟩

**操作 2：** QMSUB(目标=|reg_a⟩, 控制=|reg_c⟩)
- reg_a 从 |max(a,b)⟩ 变为 |max(a,b) - max(c,d)⟩

**操作 3：** QMADD(目标=|reg_a⟩, 控制=|reg_b⟩)
- reg_a 从 |max(a,b) - max(c,d)⟩ 变为 |max(a,b) - max(c,d) + (min(a,b) - min(c,d))⟩
- **数学等价性：** (max(a,b) - max(c,d)) + (min(a,b) - min(c,d)) = (a+b) - (c+d)

**|Ψ₅⟩：步骤六完成时 (所有寄存器均处于计算基态)**
```
|comp_ab⟩_₁ |reg_a⟩_₄ |reg_b⟩_₄ |result1⟩_₄ |comp_cd⟩_₁ |reg_c⟩_₄ |reg_d⟩_₄ |result2⟩_₄ |comp_new⟩_₁
|a<b⟩_₁ |(a+b)-(c+d)⟩_₄ |min(a,b)-min(c,d)⟩_₄ |(a-b)+(c-d)⟩_₄ |c<d⟩_₁ |max(c,d)⟩_₄ |min(c,d)⟩_₄ |(a-b)-(c-d)⟩_₄ |min(a,b)<min(c,d)⟩_₁
```

**实际值示例（a=7, b=2, c=5, d=1）：**
- reg_b = |2-1⟩ = |1⟩ (min(7,2) - min(5,1) = 2 - 1)
- comp_new = |0⟩ (因为 2 >= 1，即 min(7,2) >= min(5,1))
- reg_a = |(7-5) + (2-1)⟩ = |2+1⟩ = |3⟩ = (7+2) - (5+1) = 9 - 6
- reg_c = |5⟩
- reg_d = |1⟩

## 步骤七：获取全局最小值 min(a,b,c,d)
**操作 1：** QMADD(目标=|reg_b⟩, 控制=|reg_d⟩)
- reg_b 从 |min(a,b) - min(c,d)⟩ 恢复为 |min(a,b) - min(c,d) + min(c,d)⟩ = |min(a,b)⟩

**操作 2：** CSWAP(comp_new[0], reg_b[i], reg_d[i]) 对每个 i
- 如果 comp_new = 1 (即 min(a,b) < min(c,d))：交换 reg_b 和 reg_d
  - 交换后：reg_b = |min(c,d)⟩, reg_d = |min(a,b)⟩
  - **此时 reg_d = min(a,b)，而 min(a,b) < min(c,d)，所以 reg_d = min(a,b,c,d)**
- 如果 comp_new = 0 (即 min(a,b) >= min(c,d))：不交换
  - 保持不变：reg_b = |min(a,b)⟩, reg_d = |min(c,d)⟩
  - **此时 min(a,b) >= min(c,d)，所以 min(a,b,c,d) = min(c,d)，reg_d 已经保存了全局最小值**

**|Ψ₆⟩：步骤七完成时 (最终状态，所有寄存器均处于计算基态)**
```
|comp_ab⟩_₁ |reg_a⟩_₄ |reg_b⟩_₄ |result1⟩_₄ |comp_cd⟩_₁ |reg_c⟩_₄ |reg_d⟩_₄ |result2⟩_₄ |comp_new⟩_₁
|a<b⟩_₁ |(a+b)-(c+d)⟩_₄ |min(a,b)或min(c,d)⟩_₄ |(a-b)+(c-d)⟩_₄ |c<d⟩_₁ |max(c,d)⟩_₄ |min(a,b,c,d)⟩_₄ |(a-b)-(c-d)⟩_₄ |min(a,b)<min(c,d)⟩_₁
```

**实际值示例（a=7, b=2, c=5, d=1）：**
- reg_b 恢复为 |2⟩ = min(7,2)
- comp_new = |0⟩ (因为 min(7,2) = 2 >= min(5,1) = 1)
- 不交换：reg_b = |2⟩, reg_d = |1⟩
- **reg_d = |1⟩ = min(7,2,5,1) ✓**

## 最终状态总结
**测量结果：**
- reg_a: |(a+b)-(c+d) mod 2^n⟩_₄
- reg_d: |min(a,b,c,d) mod 2^n⟩_₄
- result1: |(a-b)+(c-d) mod 2^n⟩_₄
- result2: |(a-b)-(c-d) mod 2^n⟩_₄

**实际值示例（a=7, b=2, c=5, d=1, n=4）：**
- reg_a = |(7+2)-(5+1)⟩ = |9-6⟩ = |3⟩
- reg_d = |min(7,2,5,1)⟩ = |1⟩
- result1 = |(7-2)+(5-1)⟩ = |5+4⟩ = |9⟩
- result2 = |(7-2)-(5-1)⟩ = |5-4⟩ = |1⟩

## 关键点说明

### 1. CSWAP 逻辑
- CSWAP(comp, a, b)：当 comp=1 时交换 a 和 b
- 如果 a < b，comp=1，交换后：a = b (max), b = a (min) ✓
- 如果 a >= b，comp=0，不交换：a = a (max), b = b (min) ✓

### 2. 步骤六的执行顺序
- **先比较** min(a,b) 和 min(c,d)，得到 reg_b = min(a,b) - min(c,d) 和 comp_new
- **然后计算** reg_a = (max(a,b) - max(c,d)) + (min(a,b) - min(c,d))
- 这里使用 reg_b 的值（min(a,b) - min(c,d)）来计算 reg_a

### 3. 步骤七的恢复逻辑
- **先恢复** reg_b 从 |min(a,b) - min(c,d)⟩ 到 |min(a,b)⟩
- **然后根据 comp_new 交换** reg_b 和 reg_d，得到全局最小值到 reg_d
- 这个顺序确保了：
  1. reg_a 的计算使用了正确的 reg_b 值（min(a,b) - min(c,d)）
  2. 全局最小值的获取通过恢复和交换完成

### 4. 数学等式验证
- (max(a,b) - max(c,d)) + (min(a,b) - min(c,d)) = (a+b) - (c+d)
- **证明：**
  - 如果 a >= b：max(a,b) = a, min(a,b) = b
  - 如果 c >= d：max(c,d) = c, min(c,d) = d
  - 那么：(a - c) + (b - d) = (a+b) - (c+d) ✓
  - 如果 a < b：max(a,b) = b, min(a,b) = a
  - 如果 c < d：max(c,d) = d, min(c,d) = c
  - 那么：(b - d) + (a - c) = (a+b) - (c+d) ✓

