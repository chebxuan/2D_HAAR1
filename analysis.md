# 逻辑文档与代码实现对比分析

## 一、逻辑文档分析

### 步骤一：计算 a-b 和 c-d
**逻辑描述：**
- 使用 C_QMSUB 计算 a-b：QMSUB(目标=|reg_a⟩, 控制=|reg_b⟩)
- 结果：reg_a = |a-b⟩, comp_ab = |a<b⟩
- 同样：reg_c = |c-d⟩, comp_cd = |c<d⟩

**状态 |Ψ₁⟩：**
```
|a<b⟩_₁ |a-b⟩_₈ |b⟩_₈ |0⟩_₈ |c<d⟩_₁ |c-d⟩_₈ |d⟩_₈ |0⟩_₈
```

**✅ 逻辑正确性：正确**

### 步骤二：累加 a-b 和 c-d 到 result₁
**逻辑描述：**
- QMADD(目标=|result₁⟩, 控制=|reg_a⟩)：result₁ = 0 + (a-b) = (a-b)
- QMADD(目标=|result₁⟩, 控制=|reg_c⟩)：result₁ = (a-b) + (c-d)

**状态 |Ψ₂⟩：**
```
|a<b⟩_₁ |a-b⟩_₈ |b⟩_₈ |(a-b)+(c-d)⟩_₈ |c<d⟩_₁ |c-d⟩_₈ |d⟩_₈ |0⟩_₈
```

**✅ 逻辑正确性：正确**

### 步骤三：计算 (a-b)-(c-d) 并存储到 result₂
**逻辑描述：**
- 复制 a-b 到 result₂（使用 n 个 CNOT）
- QMSUB(目标=|result₂⟩, 控制=|reg_c⟩)：result₂ = (a-b) - (c-d)

**状态 |Ψ₃⟩：**
```
|a<b⟩_₁ |a-b⟩_₈ |b⟩_₈ |(a-b)+(c-d)⟩_₈ |c<d⟩_₁ |c-d⟩_₈ |d⟩_₈ |(a-b)-(c-d)⟩_₈
```

**✅ 逻辑正确性：正确**

### 步骤四：原始值恢复和排序
**逻辑描述：**
- 恢复 a：QMADD(目标=|reg_a⟩, 控制=|reg_b⟩)：reg_a = (a-b) + b = a
- 恢复 c：QMADD(目标=|reg_c⟩, 控制=|reg_d⟩)：reg_c = (c-d) + d = c
- 使用 CSWAP 重新排序为 (max, min)：
  - 如果 comp_ab=1（即 a<b），交换 reg_a 和 reg_b
  - 如果 comp_cd=1（即 c<d），交换 reg_c 和 reg_d

**最终状态：**
```
reg_a: |max(a,b) mod 2⁸⟩_₈
reg_b: |min(a,b) mod 2⁸⟩_₈
comp_cd: |1⟩ 如果 c<d, 否则 |0⟩
reg_c: |max(c,d) mod 2⁸⟩_₈
reg_d: |min(c,d) mod 2⁸⟩_₈
```

**⚠️ 逻辑问题：**
- CSWAP 的条件需要明确：当 comp=1 时（即第一个 < 第二个），应该交换以得到 (max, min)
- 但是 CSWAP(comp, a, b) 的逻辑是：如果 comp=1，交换 a 和 b
- 如果 comp_ab=1（即 a<b），交换后：reg_a 变成 b（min），reg_b 变成 a（max）
- **这是错误的！** 应该反过来：当 comp_ab=0（即 a>=b）时交换，或者使用相反的交换逻辑

**❌ 逻辑错误：CSWAP 的使用逻辑反了**

### 步骤五：全局最小值计算
**逻辑描述：**
1. 使用 C_QMSUB 比较 min(a,b) 和 min(c,d)
   - reg_b 被修改为 min(a,b) - min(c,d)
   - comp_new = 1 如果 min(a,b) < min(c,d)
2. 如果 comp_new=1（即 min(a,b) 更小），交换 reg_b 和 reg_d
   - reg_d 得到全局最小值

**中间状态：**
```
reg_a: |max(a,b) mod 2⁸⟩_₈
reg_b: min(a,b) - min(c,d)  （临时值）
comp_cd: |1⟩ 如果 c<d, 否则 |0⟩
reg_c: |max(c,d) mod 2⁸⟩_₈
reg_d: min(a,b,c,d)
```

**⚠️ 逻辑问题：**
- 同样的 CSWAP 逻辑问题：如果 comp_new=1 表示 min(a,b) < min(c,d)，那么交换 reg_b 和 reg_d 后，reg_d 会得到 min(a,b) - min(c,d)，而不是 min(a,b)
- **需要先恢复 reg_b 的值，或者使用正确的交换逻辑**

**接着：计算 (max(a,b) - max(c,d)) + (min(a,b) - min(c,d))**
**逻辑描述：**
1. QMSUB(目标=|reg_a⟩, 控制=|reg_c⟩)：reg_a = max(a,b) - max(c,d)
2. QMADD(目标=|reg_a⟩, 控制=|reg_b⟩)：reg_a += min(a,b) - min(c,d)

**⚠️ 问题：**
- 在步骤五开始，reg_b 已经被修改为 min(a,b) - min(c,d)
- 但如果执行了交换，reg_b 的值会改变

**❌ 逻辑错误：步骤五中 reg_b 的值管理有问题**

## 二、代码实现分析 (main1.py)

### 步骤一：Stage 1
```python
qc.append(c_qmsub_gate, comp_ab[:] + reg_a[:] + reg_b[:])
qc.append(c_qmsub_gate, comp_cd[:] + reg_c[:] + reg_d[:])
```

**✅ 符合逻辑文档**

### 步骤二：Stage 2
```python
qc.append(qmadd_gate, result1[:] + reg_a[:])
qc.append(qmadd_gate, result1[:] + reg_c[:])
```

**✅ 符合逻辑文档**

### 步骤三：Stage 3
```python
for i in range(n):
    qc.cnot(reg_a[i], result2[i])
qc.append(qmsub_gate, result2[:] + reg_c[:])
```

**✅ 符合逻辑文档**

### 步骤四：Stage 4 和 Stage 5
```python
# Stage 4: 恢复原始值
qc.append(qmadd_gate, reg_a[:] + reg_b[:])
qc.append(qmadd_gate, reg_c[:] + reg_d[:])

# Stage 5: 排序
for i in range(n):
    qc.cswap(comp_ab[0], reg_a[i], reg_b[i])
    qc.cswap(comp_cd[0], reg_c[i], reg_d[i])
```

**❌ 问题：CSWAP 逻辑错误**
- 如果 comp_ab=1（即 a<b），CSWAP 会交换 reg_a 和 reg_b
- 交换后：reg_a = b（min），reg_b = a（max）
- **这与逻辑文档要求的 (max, min) 相反**

### 步骤五：Stage 6
```python
# 比较 min(a,b) 和 min(c,d)
qc.append(c_qmsub_gate, comp_new[:] + reg_b[:] + reg_d[:])
# 计算 (a+b)-(c+d) 在 reg_a
qc.append(qmsub_gate, reg_a[:] + reg_c[:])  # reg_a = max(a,b)-max(c,d)
qc.append(qmadd_gate, reg_a[:] + reg_b[:])  # reg_a += min(a,b)-min(c,d)
```

**⚠️ 问题：**
- reg_b 此时是 min(a,b) - min(c,d)（因为 C_QMSUB 修改了它）
- 但 reg_d 还是 min(c,d)，而不是全局最小值
- 逻辑文档说应该先交换 reg_b 和 reg_d 得到全局最小值，但代码中交换是在 Stage 7

### 步骤六：Stage 7
```python
# 恢复 reg_b
qc.append(qmadd_gate, reg_b[:] + reg_d[:])
# CSWAP 得到全局最小值
for i in range(n):
    qc.cswap(comp_new[0], reg_b[i], reg_d[i])
```

**❌ 问题：**
- 恢复 reg_b 的操作 `qc.append(qmadd_gate, reg_b[:] + reg_d[:])` 会使得 reg_b = (min(a,b) - min(c,d)) + min(c,d) = min(a,b)
- 然后如果 comp_new=1（即 min(a,b) < min(c,d)），交换 reg_b 和 reg_d
- 交换后 reg_d = min(a,b)，reg_b = min(c,d)
- **这与逻辑文档描述的顺序不一致**

## 三、主要问题总结

### 问题 1：CSWAP 逻辑反向
**描述：** CSWAP 在 comp=1 时交换，但这与逻辑文档要求的 (max, min) 排序相反

**解决方案：**
- 方案 A：当 comp=0 时交换（即使用 CNOT 翻转 comp 位）
- 方案 B：交换 CSWAP 的参数顺序
- 方案 C：理解 CSWAP 后 reg_a 和 reg_b 的位置已经正确，只是命名需要调整

### 问题 2：步骤五的执行顺序
**逻辑文档要求：**
1. 先比较 min(a,b) 和 min(c,d)，得到 comp_new
2. 根据 comp_new 交换 reg_b 和 reg_d，得到全局最小值
3. 然后计算 (max(a,b) - max(c,d)) + (min(a,b) - min(c,d))

**代码实现：**
1. 比较 min(a,b) 和 min(c,d)，reg_b 被修改
2. 立即计算 (max(a,b) - max(c,d)) + (min(a,b) - min(c,d))
3. 然后才交换得到全局最小值

**❌ 执行顺序不一致**

### 问题 3：数学等式验证
**逻辑文档说：** `(max(a,b) - max(c,d)) + (min(a,b) - min(c,d)) = (a+b) - (c+d)`

**验证：**
- 如果 a >= b：max(a,b) = a, min(a,b) = b
- 如果 c >= d：max(c,d) = c, min(c,d) = d
- 那么：(a - c) + (b - d) = (a+b) - (c+d) ✓

**但是：**
- 如果 a < b：max(a,b) = b, min(a,b) = a
- 如果 c < d：max(c,d) = d, min(c,d) = c
- 那么：(b - d) + (a - c) = (a+b) - (c+d) ✓

**✅ 数学等式正确**

## 四、修复建议

### 修复 1：调整 CSWAP 逻辑
在步骤四中，如果希望 reg_a = max(a,b), reg_b = min(a,b)：
- 当 comp_ab=1（即 a<b）时，当前 reg_a = a-b（负数模），reg_b = b
- 恢复后：reg_a = a, reg_b = b
- 如果 a < b，我们想要 reg_a = max = b, reg_b = min = a
- **所以应该在 comp_ab=1 时交换** ✓
- 但问题是：交换后 reg_a = b, reg_b = a，这是正确的！

**等等，让我重新理解：**
- CSWAP(comp, a, b)：如果 comp=1，交换 a 和 b
- 如果 a < b，comp_ab = 1，交换后：reg_a = b, reg_b = a
- 所以 reg_a = max(a,b), reg_b = min(a,b) ✓

**看起来代码逻辑是正确的！**

### 修复 2：调整步骤五的执行顺序
应该先完成交换得到全局最小值，再计算 reg_a 的值。

## 五、详细对比：逻辑文档 vs main1.py

### 步骤一 ✅ 一致
**逻辑文档：** 使用 C_QMSUB 计算 a-b 和 c-d
**main1.py：**
```python
qc.append(c_qmsub_gate, comp_ab[:] + reg_a[:] + reg_b[:])
qc.append(c_qmsub_gate, comp_cd[:] + reg_c[:] + reg_d[:])
```
**✅ 完全一致**

### 步骤二 ✅ 一致
**逻辑文档：** 累加 a-b 和 c-d 到 result₁
**main1.py：**
```python
qc.append(qmadd_gate, result1[:] + reg_a[:])
qc.append(qmadd_gate, result1[:] + reg_c[:])
```
**✅ 完全一致**

### 步骤三 ✅ 一致
**逻辑文档：** 复制 a-b 到 result₂，然后 result₂ = result₂ - (c-d)
**main1.py：**
```python
for i in range(n):
    qc.cnot(reg_a[i], result2[i])
qc.append(qmsub_gate, result2[:] + reg_c[:])
```
**✅ 完全一致**

### 步骤四 ⚠️ 需要验证 CSWAP 逻辑
**逻辑文档：** 恢复 a 和 c，然后用 CSWAP 排序为 (max, min)

**CSWAP 逻辑验证：**
- 假设 a=7, b=2（所以 a > b, comp_ab = 0）
- 恢复后：reg_a = 7, reg_b = 2
- CSWAP(comp_ab=0, reg_a=7, reg_b=2)：不交换
- 结果：reg_a = 7, reg_b = 2 ✓

- 假设 a=2, b=7（所以 a < b, comp_ab = 1）
- 恢复后：reg_a = 2, reg_b = 7
- CSWAP(comp_ab=1, reg_a=2, reg_b=7)：交换
- 结果：reg_a = 7, reg_b = 2 ✓

**✅ CSWAP 逻辑正确**

**main1.py：**
```python
# Stage 4: 恢复
qc.append(qmadd_gate, reg_a[:] + reg_b[:])
qc.append(qmadd_gate, reg_c[:] + reg_d[:])
# Stage 5: 排序
for i in range(n):
    qc.cswap(comp_ab[0], reg_a[i], reg_b[i])
    qc.cswap(comp_cd[0], reg_c[i], reg_d[i])
```
**✅ 逻辑正确**

### 步骤五 ❌ 执行顺序不一致
**逻辑文档要求：**
1. 使用 C_QMSUB 比较 min(a,b) 和 min(c,d)
   - reg_b 被修改为 min(a,b) - min(c,d)
   - comp_new = 1 如果 min(a,b) < min(c,d)
2. **根据 comp_new 交换 reg_b 和 reg_d**，得到全局最小值
3. 然后计算 (max(a,b) - max(c,d)) + (min(a,b) - min(c,d))

**main1.py 实现：**
```python
# Stage 6:
# 1. 比较 min(a,b) 和 min(c,d)
qc.append(c_qmsub_gate, comp_new[:] + reg_b[:] + reg_d[:])
# 2. 立即计算 reg_a（此时 reg_b 已经被修改）
qc.append(qmsub_gate, reg_a[:] + reg_c[:])
qc.append(qmadd_gate, reg_a[:] + reg_b[:])
# Stage 7:
# 3. 然后才交换（已经太晚了）
qc.append(qmadd_gate, reg_b[:] + reg_d[:])
for i in range(n):
    qc.cswap(comp_new[0], reg_b[i], reg_d[i])
```

**❌ 问题：**
1. 在 Stage 6 中，计算 reg_a 时使用了 reg_b，但此时 reg_b = min(a,b) - min(c,d) ✓（这个是对的）
2. 但是交换应该在计算 reg_a 之前完成，这样 reg_b 中保存的是 min(a,b) - min(c,d)，而 reg_d 中保存的是全局最小值
3. **当前实现：交换在 Stage 7 才执行，此时 reg_b 已经被用于计算 reg_a**

**但实际上：** 
- 逻辑文档说 reg_b 被修改为 min(a,b) - min(c,d)，然后用它来计算 reg_a
- 交换的目的是得到全局最小值到 reg_d
- 如果交换在计算 reg_a 之前，那么 reg_b 的值会改变，计算 reg_a 时用的就不是 min(a,b) - min(c,d) 了

**让我重新理解逻辑文档：**
1. C_QMSUB：reg_b = min(a,b) - min(c,d), comp_new = (min(a,b) < min(c,d))
2. **如果 comp_new=1（即 min(a,b) < min(c,d)），交换 reg_b 和 reg_d**
   - 交换前：reg_b = min(a,b) - min(c,d), reg_d = min(c,d)
   - 交换后：reg_b = min(c,d), reg_d = min(a,b) - min(c,d)
   - **但这不对！** 逻辑文档说交换后 reg_d = min(a,b,c,d)
   
**等等，让我重新看逻辑文档：**
- "comp_new 是 1 (即min(a,b)更小)，门会交换 reg_b 和 reg_d 的内容。reg_d 已经成功获得了全局最小值 min(a,b,c,d)"
- 这意味着：如果 min(a,b) < min(c,d)，那么 min(a,b,c,d) = min(a,b)
- 交换前：reg_b = min(a,b) - min(c,d)，reg_d = min(c,d)
- 如果 min(a,b) < min(c,d)，我们应该让 reg_d = min(a,b)
- **但是 reg_b 中现在只有 min(a,b) - min(c,d)，不是 min(a,b)！**

**我发现逻辑文档的问题：**
- 在交换之前，reg_b = min(a,b) - min(c,d)，不是 min(a,b)
- 如果要得到 min(a,b) 到 reg_d，需要先恢复 reg_b

**所以 main1.py 的做法可能是对的：**
- Stage 6：比较得到 reg_b = min(a,b) - min(c,d)，并用于计算 reg_a
- Stage 7：恢复 reg_b = min(a,b)，然后根据 comp_new 交换得到全局最小值

但是逻辑文档的描述顺序不同。

## 六、关键发现

### 问题 1：逻辑文档中步骤五的描述有歧义
**逻辑文档说：**
- "先用C_QMSUB_Gate比较 min(a,b) 和 min(c,d)，reg_b 被临时修改为 min(a,b) - min(c,d)"
- "comp_new 是 1 (即min(a,b)更小)，门会交换 reg_b 和 reg_d 的内容。reg_d 已经成功获得了全局最小值"

**问题：** 如果 reg_b = min(a,b) - min(c,d)，交换后 reg_d 不会得到 min(a,b)，除非先恢复 reg_b。

**可能的解释：**
- 逻辑文档中说的"交换"可能是指：如果 comp_new=1，那么 min(a,b) 就是全局最小值，需要特殊处理
- 但具体如何"交换"来得到全局最小值，文档描述不清楚

### 问题 2：main1.py 的实现可能更合理
**main1.py 的做法：**
1. 比较得到 reg_b = min(a,b) - min(c,d)，comp_new
2. 用 reg_b 计算 reg_a = (max(a,b) - max(c,d)) + (min(a,b) - min(c,d))
3. 恢复 reg_b = min(a,b)
4. 根据 comp_new 交换 reg_b 和 reg_d

**这个顺序可能更合理。**

## 七、总结与建议

### 主要问题
1. **逻辑文档中步骤五的描述不够清晰**，特别是如何从 reg_b = min(a,b) - min(c,d) 得到全局最小值
2. **main1.py 的执行顺序与逻辑文档不同**，但可能更合理
3. **需要验证数学计算的正确性**

### 建议
1. 检查逻辑文档中步骤五的详细描述，明确交换的具体操作
2. 如果 main1.py 的逻辑更合理，更新逻辑文档
3. 运行测试验证最终结果是否正确

