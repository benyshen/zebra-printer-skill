# 安装与配置

这份文档覆盖：装在哪、怎么装、依赖是什么、打印机怎么接、怎么验证、怎么升级、出问题怎么查。

只想尽快打一张标签，看 [README](../README.md) 的「安装」和「两条主用法」即可。

---

## 1. 前置条件

| 项目 | 要求 |
|---|---|
| 操作系统 | Windows 10/11（主力验证平台）；macOS / Linux 理论可用，未实机验证 |
| Python | **3.10 以上**。实测 3.14.5（python.org 安装包）与 3.14.7（uv 下载）均可 |
| 磁盘 | 约 400 MB（源码 16 MB + 虚拟环境与依赖约 350 MB） |
| 网络 | 首次安装需访问 PyPI（引擎 + 7 个依赖）；全程离线也可用 `--offline` 走仓库内 wheel；装完后**完全离线可用**（引擎、命令目录、OCR 模型、字体调用全在本地） |
| 打印机 | Zebra 打印机，网络（TCP 9100）/ Windows 打印队列 / USB 三种接法任选其一 |
| 不需要 | 不需要 `zebra-printer-mcp`，不需要 MCP 客户端，不需要注册任何服务 |

`python --version` 不满足时先装 Python；Windows 上装 python.org 版本时勾选「Add python.exe to PATH」。

---

## 2. 三种安装位置

### 2.1 作为 Hermes skill（推荐）

把整个 `zebra-printer-skill` 目录放到 Hermes 的 skills 目录下：

```
<Hermes 用户目录>/skills/zebra-printer-skill/
```

Windows 上通常是：

```
C:\Users\<用户名>\AppData\Local\hermes\skills\zebra-printer-skill
```

放好后重开一个会话，Hermes 会读 `SKILL.md` 的 `description` 决定是否加载——之后你说「照这张标签照片打一张」「打一张 60×40 的商品标签」就会自动命中。

目录名不要改：`SKILL.md` 里的 `name` 字段必须与目录名一致，否则某些版本不会索引到。

### 2.2 普通目录（不给 agent 用，只当工具）

解压到任意位置，例如 `D:\tools\zebra-printer-skill`。之后所有命令都在这个目录里执行。

### 2.3 只当命令行工具用

同上，但只在需要时 `cd` 进去跑 `scripts/label.py`，不接入 Hermes。

---

## 3. 安装依赖

在 skill 根目录执行（**用系统 Python 跑这一步**，它会自己建虚拟环境）：

```bash
python scripts/setup.py
```

它做四件事，全部幂等：

1. **校验引擎 wheel**：`vendor/wheels/zpl_core-0.1.0-py3-none-any.whl` 的 sha256 必须等于 `setup.py` 里的常量，不匹配直接拒绝安装；
2. 在 `.venv/` 建独立虚拟环境（不碰系统 site-packages，不需要管理员权限）；
3. 装引擎：默认从 PyPI 装 `zpl-core==0.1.0`；连不上 PyPI 或加 `--offline` 时退到 `vendor/wheels` 里那份（`--no-index --no-deps`，哈希已校验）；再按 `requirements.txt` 装 7 个运行期依赖；
4. 打印 `READY:` 加解释器路径。

引擎是独立包 [zpl-core](https://github.com/benyshen/zpl-core)，wheel 里同时带着 253 条命令目录和 PP-OCRv4 权重，所以装完就能查手册、能认字，不需要额外下载模型。

成功输出末尾形如：

```
READY: D:\tools\zebra-printer-skill\.venv\Scripts\python.exe
```

**之后所有命令都用这个解释器**（下文记作 `$PY`）：

```bash
PY="<skill>/.venv/Scripts/python.exe"    # Windows
PY="<skill>/.venv/bin/python"            # macOS / Linux
```

只检查不安装：

```bash
python scripts/setup.py --check
```

### 依赖清单

wheel 之外的 7 个包（都由 `requirements.txt` 管；引擎本身不在这里）：

| 包 | 用途 | 缺了会怎样 |
|---|---|---|
| `pillow` | 离线渲染 PNG、读照片 | `render` / `photo` 不可用 |
| `segno` | 渲染 QR | QR 预览降级（打印不受影响） |
| `python-barcode` | 渲染一维码 | 一维码预览降级 |
| `opencv-python-headless` | 照片矫正、图像处理 | `photo` 不可用 |
| `numpy` | 数组运算（cv2 依赖） | `photo` 不可用 |
| `onnxruntime` | 跑 PP-OCRv4 文字识别 | `photo` 只出条码不出文字 |
| `zxing-cpp` | 照片条码解码兜底 | 条码识别率下降 |

**只打 spec 定义好的标签**（`build` / `validate` / `send` / `status`）其实一个第三方包都不需要——这几个功能只用标准库。整套 `requirements.txt` 是为 `render` 和 `photo` 装的。

### 内网 / 镜像源

`setup.py` 不拦环境变量，pip 的镜像配置照样生效：

```bash
PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple python scripts/setup.py
```

完全离线时，先在有网机器上把轮子下到一个目录：

```bash
pip download -r requirements.txt -d wheels/
```

再把 `wheels/` 一起拷过去，然后手动装：

```bash
.venv/Scripts/python.exe -m pip install --no-index --find-links wheels -r requirements.txt
```

---

## 4. 验证安装

按顺序做这三步，都过了再谈打印。

```bash
# 1) 依赖齐不齐
$PY scripts/setup.py --check

# 2. 项目自检（结构、内置引擎、条码表、模板、渲染）
$PY tests/test_skill.py          # 末行应为 ALL CHECKS PASSED

# 3) 打印机通不通
export ZEBRA_HOST=<打印机IP>
$PY scripts/label.py status      # status.code 为 0000 即就绪
```

`status` 正常返回类似：

```json
{"ok": true, "status": {"code": "0000", "name": "PRINTER READY", "level": "ok"},
 "identification": {"printer": "ZR668-200dpi", "firmware": "V86.20.21Z", "dots_per_mm": "8"}}
```

---

## 5. 打印机接入

### 5.1 网络打印机（推荐）

Zebra 默认用 raw ZPL 端口 **9100**，不走驱动、不需要共享。

```bash
export ZEBRA_HOST=<打印机IP>
$PY scripts/label.py status
$PY scripts/label.py print label.spec.json
```

地址怎么查：打印机面板的网络设置、路由器 DHCP 列表，或系统里已装驱动的话 `$PY scripts/label.py printers`。ZR668 这类机型也可以用 SGD 查：

```zpl
! U1 getvar "device.ip.address"
```

排不通时依次确认：同一网段能 ping 通、9100 端口没被防火墙拦、打印机没被别的作业占住（`status` 的 `name` 会说明）。

### 5.2 Windows 打印队列

打印机已在本机装好驱动时用这条通道，按队列名发送（走 RAW，不经过驱动重新解释）：

```bash
$PY scripts/label.py printers                  # 列出队列名
$PY scripts/label.py send label.zpl --transport windows --printer "ZDesigner ZR668-203dpi ZPL"
```

### 5.3 USB

USB 直连且系统里能看到队列时，同样给队列名：

```bash
$PY scripts/label.py send label.zpl --transport usb --printer "<队列名>"
```

这条通道正常只返回 `job_id`（证明已入队），不返回打印机回显。要确凿证据用 5.1。

---

## 6. 目录结构

```
zebra-printer-skill/
├── SKILL.md                    agent 入口：触发条件、两条主任务、停止判据、纪律
├── README.md                   人看的快速上手
├── LICENSE                     MIT
├── requirements.txt            7 个运行期依赖
├── docs/install.md             本文件
├── scripts/
│   ├── setup.py                建 .venv + 校验 wheel 哈希 + 装引擎与依赖
│   └── label.py                全部子命令的唯一入口，输出 JSON
├── vendor/
│   ├── PROVENANCE.md           引擎 wheel 的来源、哈希、升级步骤
│   └── wheels/
│       └── zpl_core-0.1.0-py3-none-any.whl   引擎本体（14.1 MB）
│                                              含 253 条命令目录 + PP-OCRv4 模型
├── references/
│   ├── spec-schema.md          label spec 全键表、28 种条码位序
│   └── calibration.md          照片复刻六条校准规则
├── templates/                  两张实机验证过的 70×70 标签
├── examples/                   spec 示例 + 渲染预览图
└── tests/test_skill.py         自检
```

引擎是**普通安装的包**：`scripts/setup.py` 把 `vendor/wheels/` 里的 wheel 装进 `.venv/Lib/site-packages`，数据跟着包走（`zpl_core/data/`）。所以不再有"vendor/src 与 vendor/data 必须保持相对位置"这种约束——`label.py` 直接 `from zpl_core import ...`，不需要任何 `sys.path` 拼接。

`setup.py` 装之前会校验 wheel 的 sha256；哈希对不上直接拒绝安装（防止 vendor 里的引擎被悄悄换掉）。升级步骤见 `vendor/PROVENANCE.md`。

---

## 7. 升级与同步

**升级依赖**（改了 `requirements.txt` 之后）：

```bash
$PY -m pip install -r requirements.txt
```

**同步上游引擎**：`vendor/` 是从 [`zebra-printer-mcp`](https://github.com/benyshen/zebra-printer-mcp) 复制进来的分叉，上游修 bug 不会自动进来。同步命令见 `vendor/PROVENANCE.md`，同步后必须重跑 `tests/test_skill.py`。

不要在 `vendor/` 里直接改代码——下次同步会覆盖。要改引擎行为，改上游再同步。

---

## 8. 卸载

```bash
rm -rf <skill>/.venv      # 依赖
rm -rf <skill>            # 整个 skill（含源码与模型）
```

没有注册表项、没有系统服务、没有全局包，删目录即净。

---

## 9. 故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| `ModuleNotFoundError: No module named 'cv2'` / `'PIL'` | 用了系统 python，不是 `.venv` 里的 | 改用 `.venv/Scripts/python.exe`（或 `bin/python`） |
| `ModuleNotFoundError: No module named 'mcp'` | 装错了包（那是 MCP 服务端） | 本 skill 不需要 `mcp`，确认用的是 skill 目录里的 `label.py` |
| `no printer address: pass --host <ip> or set ZEBRA_HOST` | 没给地址 | `export ZEBRA_HOST=...` 或加 `--host` |
| `ConnectionRefusedError: [WinError 10061]` | 地址错、端口错、防火墙、打印机不在线 | 先 `ping`，再 `status`，确认 9100 |
| `send` 返回 `response` 含 `?` 或多个 `?` | 打印机拒收该 ZPL | 按回显定位命令；先 `validate` 一遍 |
| `send` 的 `response` 为空 | 正常（无语法错误） | 无需处理 |
| `warnings` 有 `ASPECT` | 照片宽高比与标签尺寸不符，整版会缩放 | 裁照片到标签边缘，或改用 `--frame auto` |
| `warnings` 有 `MODULE_TOO_SMALL` | 条码模块太细，扫描枪可能读不到 | 加大标签宽度或 `module_width`，或减少数据量 |
| OCR 多字 / 少字（如多出一个偏旁） | 透视校正把边缘碎片带进了文字块 | 换 `--frame full` 重跑；仍错就改生成的 `^FD` |
| 中文打不出来 / 打问号 | 字体文件不对或没带 `char_encoding` | `font_file` 用打印机内置字体（如 `E:SIMSUN.TTF`），spec 里 `"char_encoding": 28` |
| 整版偏小一圈 | 只给了图案尺寸、没给纸尺寸 | 补 `--paper` / `--paper-height`（模切料常是 76 mm 纸载 70 mm 图案） |
| 越打越黑 | 用了相对浓度 `^MD`，跨任务累积 | 改用绝对浓度 `~SD` |
| `render` 报缺 segno / python-barcode | 可选渲染依赖没装 | `$PY -m pip install -r requirements.txt`；或忽略（打印不受影响） |
| `setup.py` 卡在 pip | 网络到 PyPI 不通 | 配 `PIP_INDEX_URL` 走镜像，或离线装轮子 |
| `status` 一直拿不到 `~HS` | 打印机不支持 SGD / 端口不是 raw 9100 | 换 9100 通道；或只在 `send` 后看 `response` |

---

## 10. 边界与安全

**不做**：RFID 编码、打印机 SNMP 监控、`^GF` 位图流、`~DG` 字体下载、跨打印机并发调度、作业队列管理。

**校验通过 ≠ 能扫**。`validate` 只按命令目录和参数位序查语法；静区是否够、模块宽是否够、纠错级是否合适，只有出纸后用扫码枪能确认。

**不要把打印机地址、凭据写进公开仓库或文档**。`ZEBRA_HOST` 用环境变量传，仓库里一律写 `<打印机IP>` 占位。
