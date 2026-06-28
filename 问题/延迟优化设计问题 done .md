## 🔴 致命级

### BUG-1: comtypes DXGI 路径 D3D11CreateDevice 调用方式错误 — 整个 DXGI Desktop Duplication 功能是死代码

- \[故障点] ：\[dxgi\_capture.py:162-189]\(file:///c:/Users/1/Downloads/宏驱动 webui 2.6/automation/detection/dxgi\_capture.py#L162-L189) \_initialize\_comtypes 方法
- \[复现路径] ：在任何 Windows 环境下安装了 comtypes 后执行 capture\_source 节点 → comtypes 路径 100% 抛异常 → 回退到 \_initialize\_ctypes → 实际执行 BitBlt 而非 DXGI Desktop Duplication
- \[底层原因] ： D3D11CreateDevice 通过 comtypes 生成模块是一个 ctypes 函数，返回 HRESULT，device/context 通过输出参数返回。代码却把它当成了返回 device 对象的 COM 方法来调用（ self.\_device = \_D3D11.D3D11CreateDevice(...) ），参数签名和返回值处理完全错误。comtypes 路径必然失败，所谓的 "DXGI 双路径策略" 实际只有 BitBlt 一条路径在工作。设计文档中声称的 0.1-0.5ms 帧缓冲切片性能完全无法实现。

### BUG-2: \_acquire\_frame\_fallback GDI 资源泄漏 — 长时间运行后 GDI 句柄耗尽导致截图全黑

- \[故障点] ：\[dxgi\_capture.py:259-316]\(file:///c:/Users/1/Downloads/宏驱动 webui 2.6/automation/detection/dxgi\_capture.py#L259-L316) \_acquire\_frame\_fallback 方法
- \[复现路径] ：启动 DXGI 后台采集（ctypes 路径），在 60fps 下持续运行 → 每秒 60 次调用 \_acquire\_frame\_fallback → 如果 BitBlt 或 GetDIBits 中间任何一步失败（如分辨率切换瞬间）， hdc 、 hdc\_mem 、 hbitmap 全部泄漏 → 几分钟内 GDI 句柄耗尽 → 所有截图返回全黑
- \[底层原因] ：整个函数没有 try-finally 保护，GDI 资源（GetDC、CreateCompatibleDC、CreateCompatibleBitmap）在异常路径上不会被释放。

### BUG-3: 后台线程未初始化 COM — comtypes 路径即使修复后也会在线程中崩溃

- \[故障点] ：\[dxgi\_capture.py:359-365]\(file:///c:/Users/1/Downloads/宏驱动 webui 2.6/automation/detection/dxgi\_capture.py#L359-L365) \_capture\_loop 方法
- \[复现路径] ：修复 BUG-1 后，comtypes DXGI 路径在主线程初始化成功 → 后台线程 \_capture\_loop 调用 acquire\_frame → AcquireNextFrame 等 COM 调用在线程中执行 → COM 未在该线程初始化 → RPC\_E\_WRONG\_THREAD 异常
- \[底层原因] ： CoInitializeEx 在 initialize() 中被调用（主线程），但 \_capture\_loop 在 daemon 线程中运行 COM 对象，每个使用 COM 的线程必须自己调用 CoInitializeEx 。

## 🟠 体验级

### BUG-4: CaptureManager.\_capture\_bitblt GDI 资源泄漏

- \[故障点] ：\[capture\_manager.py:56-116]\(file:///c:/Users/1/Downloads/宏驱动 webui 2.6/automation/detection/capture\_manager.py#L56-L116) \_capture\_bitblt 方法
- \[复现路径] ：DXGI 未启动 + 区域 < 500x500 → 走 BitBlt 路径 → CreateCompatibleDC 成功但 CreateCompatibleBitmap 返回 NULL → SelectObject 失败 → 异常跳到 except → hdc\_mem 和 hbitmap （如果非零）不会被清理
- \[底层原因] ：try 块中创建了 hdc\_mem 和 hbitmap ，但 finally 只释放了 hdc ，没有清理 hdc\_mem 和 hbitmap 。

### BUG-5: target\_hex 解析无防御 — 畸形颜色值导致节点静默走 no 端口

- \[故障点] ：\[handlers/detection.py:51-55]\(file:///c:/Users/1/Downloads/宏驱动 webui 2.6/automation/handlers/detection.py#L51-L55) \_handle\_check\_color 中颜色解析
- \[复现路径] ：用户在颜色检测节点输入 target\_color="" 或 "red" 或 "#FF" → target\_hex\[1:3] 抛 IndexError → 外层 catch 走 no 端口 → 用户完全不知道为什么检测失败
- \[底层原因] ：缺少对 target\_hex 格式的校验和容错。

### BUG-6: DXGICapture 单例模式名不副实 — 多图并行时创建多个 DXGI 线程

- \[故障点] ：\[dxgi\_capture.py:398-431]\(file:///c:/Users/1/Downloads/宏驱动 webui 2.6/automation/detection/dxgi\_capture.py#L398-L431) DXGICapture 类
- \[复现路径] ：用户同时执行两个宏图，每个图都有 capture\_source 节点 → 每个 CaptureManager 调用 DXGICapture() → **init** 每次创建新的 \_DXGICaptureImpl() → 两个独立的 DXGI 后台线程同时截图 → 资源浪费 + 潜在冲突
- \[底层原因] ： DXGICapture 声明了 \_instance 和 \_init\_lock （想做单例），但 **init** 每次都创建新实例， get\_instance() 创建的实例从未被 CaptureManager 使用。

### BUG-7: \_capture\_manager 无线程安全保护

- \[故障点] ：\[engine.py:65]\(file:///c:/Users/1/Downloads/宏驱动 webui 2.6/automation/engine.py#L65) + \[handlers/detection.py:24-25]\(file:///c:/Users/1/Downloads/宏驱动 webui 2.6/automation/handlers/detection.py#L24-L25) + \[capture.py:32]\(file:///c:/Users/1/Downloads/宏驱动 webui 2.6/automation/detection/capture.py#L32)
- \[复现路径] ：monitor 线程中执行检测节点 → capture\_screen 读取 ctx.\_capture\_manager → 同时主线程执行 capture\_source 节点赋值 ctx.\_capture\_manager = CaptureManager(ctx) → 竞态条件：可能读到半初始化的对象
- \[底层原因] ： \_capture\_manager 的读写没有通过 \_data\_lock 保护，而其他类似属性（ variables 、 check\_results ）都有 safe\_set/safe\_get 方法。

### BUG-8: check\_screen 硬编码 "screen" 模式 — 与其他检测节点不一致

- \[故障点] ：\[handlers/detection.py:441]\(file:///c:/Users/1/Downloads/宏驱动 webui 2.6/automation/handlers/detection.py#L441) \_handle\_check\_screen 中 resolve\_region("screen", region\_param, None)
- \[复现路径] ：用户在窗口模式下使用 check\_screen 节点 → 坐标按窗口偏移计算但实际按屏幕坐标截图 → 检测位置完全错误
- \[底层原因] ：check\_screen 节点定义中没有 mode 和 hwnd\_var 参数，handler 硬编码了 "screen" 模式。

## 🟡 隐患级

### BUG-9: image\_cache TOCTOU 竞态 — 高并发下缓存形同虚设

- \[故障点] ：\[image\_cache.py:21-30]\(file:///c:/Users/1/Downloads/宏驱动 webui 2.6/automation/detection/image\_cache.py#L21-L30) load\_template 方法
- \[潜在风险] ：两次 \_cache\_lock 之间释放了锁，多个线程可能同时执行 cv2.imread 读取同一文件。虽然不会导致数据损坏，但在高频 wait 轮询场景下，缓存几乎不起作用，每次都从硬盘读取。更严重的是， OSError 分支在文件被删除后仍返回旧缓存数据，可能导致使用过期的模板图片。

### BUG-10: multi\_match 模式 confidence 始终为 0

- \[故障点] ：\[handlers/detection.py:344]\(file:///c:/Users/1/Downloads/宏驱动 webui 2.6/automation/handlers/detection.py#L344) + \[handlers/detection.py:349]\(file:///c:/Users/1/Downloads/宏驱动 webui 2.6/automation/handlers/detection.py#L349)
- \[潜在风险] ：multi\_match 模式下 confidence 永远为 0.0，后续节点如果依赖置信度做判断（如 store\_var 存储的 confidence 字段），会得到错误数据。未来增加基于置信度的过滤功能时，multi\_match 将完全失效。

### BUG-11: \_try\_reinitialize 在后台线程运行时释放 COM 资源

- \[故障点] ：\[dxgi\_capture.py:367-378]\(file:///c:/Users/1/Downloads/宏驱动 webui 2.6/automation/detection/dxgi\_capture.py#L367-L378) \_try\_reinitialize 方法
- \[潜在风险] ： \_try\_reinitialize 调用 \_release\_resources 释放 COM 对象，但后台线程可能仍在 \_capture\_loop 中使用这些对象。如果 stop\_background 的 join(timeout=3.0) 超时， \_release\_resources 会在后台线程仍在运行时被调用，导致访问已释放的 COM 对象。

