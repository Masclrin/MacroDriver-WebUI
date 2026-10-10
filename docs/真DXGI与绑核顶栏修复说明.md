# 真 DXGI 截图 / 宏绑核 / 顶栏布局 修复说明

> 对应反馈：
> 1. 让项目支持真 DXGI 截图
> 2. 窗口发现问题已解决（本轮无需改动）
> 3. `[宏绑核] 绑定失败，改为系统调度：argument 1: OverflowError: int too long to convert`
> 4. `html.theme-light .topbar` 6 个状态块固定折两行、不随窗口变化、占高过多

---

## 一、真 DXGI 截图（新增原生实现）

### 原先为什么用不上真 DXGI

`automation/detection/dxgi_capture.py` 走 comtypes 路线，需要 `comtypes.gen.DXGI` /
`comtypes.gen.D3D11` 两个**自动生成**模块。而 DXGI / D3D11 都不属于标准 Windows 组件：
`dxgi.dll` / `d3d11.dll` 内不含 type library，`comtypes.client.GetModule()` 报
`TYPE_E_CANTLOADLIBRARY`。于是永远落到 `_initialize_ctypes()` → **所谓"DXGI 截图源"
其实是每帧一次全屏 BitBlt**：窗口化程序正常，**独占全屏(D3D)程序只能取到黑屏**。

### 本次做法：纯 ctypes 直接按虚表调用

新增 `automation/detection/dxgi_duplication.py`，不依赖任何 type library：

```
CreateDXGIFactory1 → EnumAdapters1 → EnumOutputs → QI(IDXGIOutput1) → DuplicateOutput
D3D11CreateDevice(绑定该输出所属适配器) → CreateTexture2D(staging)
AcquireNextFrame → QI(ID3D11Texture2D) → CopyResource → Map/Unmap → ReleaseFrame
```

关键 ABI 细节（踩过的坑，后续维护请勿改动）：

| 项 | 正确值 | 说明 |
|----|--------|------|
| `IDXGIFactory1::EnumAdapters1` | vtable **12** | IDXGIObject 占 3~6，IDXGIFactory 占 7~11 |
| `IDXGIAdapter::EnumOutputs` | **7** | |
| `IDXGIOutput1::DuplicateOutput` | **22** | IDXGIOutput 占 7~18 |
| `IDXGIOutputDuplication::AcquireNextFrame / ReleaseFrame` | **8 / 14** | |
| `ID3D11Device::CreateTexture2D` | **5** | 已用 `GetType()==3(Texture2D)` 实测确认 |
| `ID3D11Texture2D::GetDesc` | **10** | 继承链 IUnknown→DeviceChild→Resource |
| `ID3D11DeviceContext::Map / Unmap / CopyResource` | **14 / 15 / 29** | ⚠ DeviceContext 继承 **ID3D11DeviceChild**，IUnknown 之后还有 4 个基类方法，漏算这 4 个槽位会让 25 落到 `GSSetSamplers` 上，表现为访问违例 |
| `D3D11_USAGE_*` | DEFAULT=**0** IMMUTABLE=1 DYNAMIC=2 STAGING=**3** | ⚠ D3D11 里没有 UNKNOWN，把 DEFAULT 当成 1 会得到 `E_INVALIDARG` |
| `D3D11_MAP_READ` | 1 | |
| 句柄/指针参数 | 全部用 `c_void_p` / `c_size_t` | 用 `c_int` 会截断 64 位句柄 |

### 启动自检（重要）

部分机器的 D3D11 运行时/驱动处于受限或异常状态时会出现：`DuplicateOutput` 成功、
`AcquireNextFrame` 也返回 `S_OK`，但**复制出来的帧恒为全零（画面全黑）**。
此时若静默启用原生 DXGI，所有检测节点都会看到"全黑画面"，**比回退 BitBlt 更糟**。

因此 `initialize()` 末尾会调用 `_selftest_pipeline()`：用一张已知图案的小纹理实测
「建纹理 → CopyResource → Map 读回」整条通路，内容能正确搬回才启用原生 DXGI，
否则打印明确警告并放弃（回退 BitBlt）。

日志可据此判断当前实际通道：
* `[DXGI] 已启用原生 Desktop Duplication（ctypes vtable，无需 comtypes）` → 真 DXGI 生效
* `[DXGI-native] 复制/读回通路自检未通过 → 放弃原生 DXGI，改用 BitBlt` → 已回退

> 本次开发机（自动化远程会话 + 显示器休眠过）自检未通过 → 自动回退 BitBlt，属预期行为。
> 游戏实机运行时 D3D11 状态正常，自检应能通过。

### 顺带修好的

* D3D11 设备改为**绑定到拥有该输出的适配器**（`pAdapter` + `DriverType=UNKNOWN`）。
  用 `pAdapter=NULL, HARDWARE` 时混合显卡机器可能选到另一块适配器 ——
  此时 `DuplicateOutput` 仍会成功，但 `AcquireNextFrame` 永远超时。
* `IDXGIOutputDuplication` 只在桌面**发生变化**时才交付帧；静止画面靠"最后一帧"
  继续工作（`_frame_buffer` 保留上一帧），无变化时自动回退 BitBlt，不会卡死。
* 显示器休眠/锁屏时 DWM 停止呈现 → DXGI 也会没有帧（BitBlt 仍能读到内存里的合成结果）。

---

## 二、宏绑核 `OverflowError: int too long to convert`

### 根因

`engine/precision.py` 里 `GetCurrentThread` 被声明为 `restype = wintypes.HANDLE`，
所以返回的是完整 64 位伪句柄 `0xFFFFFFFFFFFFFFFE`；而
`SetThreadAffinityMask` **没有声明 argtypes**，ctypes 按 32 位 `int` 传参 →
`ArgumentError argument 1: OverflowError: int too long to convert`。

副作用更严重：即使不报错，句柄被截断成 `0xFFFFFFFE` 后 `SetThreadAffinityMask`
会返回 0（失败），而旧代码**不检查返回值**，日志里照样打印"→ CPU n"，等于绑核一直是坏的。

### 修复

* 补声明：`SetThreadAffinityMask(restype=c_size_t, argtypes=[HANDLE, c_size_t])`、
  `GetProcessAffinityMask`。
* `set_thread_affinity()` 改为**返回 bool**：索引非法 / 不在进程允许的核集合内 /
  系统调用失败 → `False`，不再静默成功；`_affinity_warn` 对同一警告只打印一次。
* `clear_thread_affinity()` 改为恢复**进程亲和掩码**（而不是 `(1<<cpu_count)-1`），
  避免把线程放到进程本身不允许的核上。
* `宏执行框架3.2.py` 的绑核日志改为按返回值打印"已绑核 / 绑定失败"。

实测（本机 8 核）：`set_thread_affinity(3)` → `True`，随后读回上一掩码为 `32`，
说明线程真的被绑到 CPU5；非法索引（8/63/99/-1/'x'）返回 `False` 并给出警告。

---

## 三、顶栏状态条布局

### 问题

`.status-grid` 是 `grid-template-columns: repeat(4, minmax(0,1fr))` —— **固定 4 列**，
6 个状态块必然折成两行，且列数写死、窗口变宽也不会变成一行；单个状态块是
"标签在上、数值在下"，块高约 58px，两行加上内边距共约 140px 的纵向占用。

### 修复（`webui/styles.css`）

* `.status-grid` 改为 `display:flex; flex-wrap:wrap` —— 状态块按内容宽度排布，
  **窗口够宽时一行 6 枚，变窄自动折行**。
* `.pill` 改为单行胶囊：`inline-flex + align-items:baseline`，标签 11px、数值 13px，
  内边距 `4px 11px` → 高度约 27px，顶栏总高约 43px（原约 140px）。
* `.topbar` 右侧留出 36px 折叠按钮槽位（原来按钮会压在最后一枚状态块上）；
  折叠按钮改垂直居中，折叠态加 `min-height:30px`（原来会退化成几像素的细条）。
* `@media (max-width:700px)`：`.status-grid` 从 grid 规则里移出（flex 已自动换行），
  改为进一步压缩内边距与字号。

`.pill` / `.status-grid` 只在顶栏使用，改动范围可控。

---

## 四、变更文件

| 文件 | 变更 |
|------|------|
| `automation/detection/dxgi_duplication.py` | **新增**：纯 ctypes 的原生 Desktop Duplication + 启动自检 |
| `automation/detection/dxgi_capture.py` | comtypes 不可用时先尝试原生 DXGI，再退 BitBlt；`acquire_frame`/释放接入原生路径 |
| `engine/precision.py` | `SetThreadAffinityMask`/`GetProcessAffinityMask` 声明签名；绑核返回 bool + 校验 + 警告去重；`clear_thread_affinity` 恢复进程掩码 |
| `宏执行框架3.2.py` | 绑核日志按返回值区分成功/失败 |
| `webui/styles.css` | 顶栏状态条改流式自适应布局，压缩纵向占用 |

## 五、验证

```bash
# 原生 DXGI 自检（会打印是否可用；不可用则自动回退 BitBlt）
python automation/detection/dxgi_duplication.py 0

# 绑核
python -c "import sys;sys.path.insert(0,r'.');from engine import precision as p;print(p.set_thread_affinity(3), p.clear_thread_affinity())"

# 上一轮回归
python plugins/anti_jump/test_backend.py
```

顶栏改动无法在本环境启动 GUI 验证，请在 `start.bat` 启动后目测：宽窗口应一行 6 枚状态块，
窗口拉窄后逐枚折行，顶栏高度明显变矮。
