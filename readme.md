## 项目说明（最新版本）

本项目实现三个量子算术模块，并在此基础上构建了“二维量子小波原型电路”。电路包含量子舍入算子 UR（向下取整），并可对所有 4 位输入进行穷举验证。

### 目录结构
- `qquantum_module.py`：提供 `QFT / IQFT / MADD` 指令。
- `qmadd_gate.py` / `qmsub_gate.py` / `c_qmsub_gate.py`：模加、模减、比较-减法器。
- `main_round.py`：最新版主电路（含 UR 算子与 guard bit）。
- `test_rounding.py`：单元测试，验证基准参数的输出。
- `verify_all_inputs.py`：遍历 65,536 组 4 位输入，逐一对比量子输出与经典结果。

### 主电路工作流程（`main_round.py`）
1. **比较/求差**：使用 `C_QMSUB` 得到 `(a-b)`、`(c-d)` 及比较位。
2. **UR₁ / UR₂**：先计算 `(a-b)+(c-d)` 与 `(a-b)-(c-d)`，再通过 UR 算子向下取整（模 2⁴）。
3. **恢复原值并排序**：对 `a,c` 执行 QMADD 恢复输入，再用 `cswap` 获得 `max/min` 配对。
4. **全局运算**：比较 `min(a,b)` 与 `min(c,d)` 得到 `min(a,b,c,d)`，同时计算 `(a+b)-(c+d)` 并再执行 UR₃。
5. **测量**：读取 `reg_a`（UR₃ 结果）、`reg_d`（四数最小值）、`result1`、`result2`（分别对应 UR₁、UR₂）。

所有寄存器采用 `data_bits + 1` 位（默认 5 位），最高位为 guard-bit，用于记录模运算中的溢出/借位。输出只取回低 `data_bits` 位。

### 使用方法
```bash
python main_round.py          # 运行单组参数，打印量子/理论结果
python test_rounding.py       # 运行单元测试
python verify_all_inputs.py   # 穷举所有 4 位输入（需数分钟）
python image_quantum_experiment.py --image cameraman.bmp --max-blocks 2048
```
所有脚本默认都使用 `AerSimulator(method="matrix_product_state")`，可在普通 CPU 上完成仿真。

### 复杂度分析
记数据宽度为 `n`。

| 模块 | 量子比特 | 受控相位门数量 | 深度估计 |
|------|----------|----------------|----------|
| QFT / IQFT | `n` | `n(n-1)/2` | `O(n)` |
| MADD / MSUB | `2n` | `n(n+1)/2`（每个 `cp` 与参数相关）| `O(n)` |
| QMADD / QMSUB | `2n` | `≈ 3·n(n-1)/2`（QFT+MADD+IQFT）| `O(n)` |
| C_QMSUB | `2n+1` | 与 QMSUB 相同，外加 1 个 CX | `O(n)` |

整条“舍入电路”各阶段调用上述模块的次数如下：
1. `C_QMSUB` ×2（求 `(a-b)`,`(c-d)`）；
2. `QMADD` ×3（`result1` 两次，Stage6 中一次）；
3. `QMSUB` ×2（`result2`、Stage6）；
4. `QMADD` ×4 + `QMSUB` ×1（恢复/全局运算）；
5. 多轮 `cswap` 与 UR 操作（UR 仅使用 SWAP + 若干 CX，深度 `O(n)`）。

因此总门数约为 `O(k·n²)`（其中 `k≈12` 为上述自定义门的调用次数），总深度为 `O(k·n)`。在 `n=4`（guard-bit 后为 5）时，电路使用 36 量子比特，可通过 `matrix_product_state` 仿真，并已由 `verify_all_inputs.py` 穷举验证全部 65,536 组输入。

### 图像实验（Cameraman 案例）

`image_quantum_experiment.py` 将 `main_round.py` 封装为整图实验流程：枚举或抽样图像的 `2×2` 块，逐块运行量子电路，统计量化指标并生成能量图，可与经典 Max-Plus 或 2D_QMP1 边缘检测结果对比。

```bash
python3 image_quantum_experiment.py \
  --image cameraman.bmp \
  --bit-depth 4 \
  --shots 512 \
  --max-blocks 0 \
  --upsample
```

- `--max-blocks` 控制抽样块数（0 表示处理全部 16,384 个块）；默认 2,048，可在约 1 分钟内得到稳定统计。处理全部块时建议 10 核桌面 CPU，耗时约 3–6 分钟。
- 输出 `*_quantum_summary.json`，包含平均能量、P90 能量、`reg_d` 均值、单块耗时等指标；在完整遍历模式下还会额外生成 `*_quantum_energy.pgm` 与 `*_classical_energy.pgm`，可直接用 `sips`/ImageMagick 预览。
- 典型指标（256×256 Cameraman，4 bit，shots=512）：量子能量均值 ≈1.4、P90=4，与经典 Max-Plus 结果高度一致；`reg_d` 均值约 2.1，可用于分析背景/噪声。PGM 热力图在帽檐、三脚架等边缘位置亮度明显，验证电路对形态学边缘的响应能力。

可将上述指标与 Sobel、2D_QMP1 Max-Plus 等经典方法拼表，评估边缘响应强度、噪声鲁棒性与运行时间，进一步展示量子形态学电路的应用价值。