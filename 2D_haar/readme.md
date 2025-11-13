## 项目说明（基于当前代码）

本项目实现并验证三个核心量子算术模块，并据此构建主电路完成四个关键结果的测量验证。代码已模块化，便于复用和测试。

### 目录结构（精简后）
- `qquantum_module.py`：基础构件（QFT、IQFT、MADD/MSUB），以 Instruction 形式返回。
- `qmadd_gate.py`：量子模加法器 `build_qmadd_gate(n)`。
- `qmsub_gate.py`：量子模减法器 `build_qmsub_gate(n)`。
- `c_qmsub_gate.py`：比较-减法器 `build_c_qmsub_gate(n)`（输出比较位）。
- `main.py`：主电路，组装并执行验证。
- `readme.md`：本文档。

### 三个核心模块
1) QMADD（`qmadd_gate.py`）
- 目标：`target = (target + control) mod 2^n`
- 实现：`QFT(target)` → `MADD(target, control)` → `IQFT(target)`

2) QMSUB（`qmsub_gate.py`）
- 目标：`target = (target - control) mod 2^n`
- 实现：`QFT(target)` → `MSUB(target, control)` → `IQFT(target)`（MADD 的逆）

3) C_QMSUB（`c_qmsub_gate.py`）
- 目标：比较并相减：`|0⟩|t⟩|c⟩ → |t<c⟩|(t-c) mod 2^n⟩|c⟩`
- 实现：先执行 QMSUB，再将 `target` 的 MSB 拷贝到比较位（包裹时为 1）

上述自定义单元均以 Instruction 返回，便于 Aer 分解与仿真。

### 主电路与验证（`main.py`）
- 参数：默认 `n=4, a=7, b=2, c=5, d=1`
- 寄存器：`a,b,c,d,result1,result2` 以及三个比较位 `comp_ab, comp_cd, comp_min`
- 步骤对齐设计（高层概述）：
  1. 用 `C_QMSUB` 计算 `(a-b)` 与 `(c-d)`，比较位写入 `comp_ab/comp_cd`。
  2. `result1 = (a-b) + (c-d)`（两次 QMADD）。
  3. `result2 = (a-b) - (c-d)`（一次 QMADD + 一次 QMSUB）。
  4. 恢复 `a,c`（各自对 `b,d` 执行 QMADD）。
  5. 以 `cswap` 和比较位将 `b←min(a,b)`，`d←min(c,d)`。
  6. 计算 `a = (a+b) - (c+d)`（用 QMADD/QMSUB）。
  7. 比较 `b` 与 `d`，用 `C_QMSUB` 得到 `comp_min`，再用 `cswap` 使 `d←min(b,d)`（最终 `reg_d` 存四数最小值）。
- 测量顺序：`reg_d`, `result1`, `result2`, `reg_a`
- 仿真：`AerSimulator(method="matrix_product_state")`，并对电路做深度分解 `decompose(reps=10)` 以去除未知指令

### 在已安装依赖的 conda 环境运行
假设你的环境名为 `teat`，在终端执行：
```bash
conda activate teat
python main.py
```

程序会打印 `Counts: {...}`，取频率最高的结果作为判定：
- 对于 `n=4, a=7, b=2, c=5, d=1`，理论结果：
  - `reg_d = 0001`（四数最小值 1）
  - `result1 = 1001`（(a-b)+(c-d)=9）
  - `result2 = 0001`（(a-b)-(c-d)=1）
  - `reg_a = 0011`（(a+b)-(c+d)=3）
- Qiskit 输出 key 的段顺序通常为：`reg_a result2 result1 reg_d`，因此期望最高频 key 为：
```
0011 0001 1001 0001
```
若你的输出中最高频 key 与上述一致（或仅段顺序不同但数值匹配），验证即通过。

### 自定义与扩展
- 修改 `main.py` 中的 `ArithmeticParams` 可更换 `n` 与 `a,b,c,d`。
- 模块均为可复用 Instruction，可直接在其它电路中 `append`。