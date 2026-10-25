---
name: zebra-printer-skill
version: 0.4.0
author: Hermes (Nous Research)
license: MIT
description: 打 ZPL 标签、把标签照片转成 ZPL、用自然语言打标签时加载。自带引擎与 OCR 模型，只需一次 setup，不依赖其它仓库或 MCP 客户端。
metadata:
  hermes:
    tags: [zpl, zebra, label, barcode, printing, ocr, photo, offline]
    related_skills: [zpl-zebra-printing, android-voice-zpl-printing]
---

## When to Use

- 用户发来一张**标签照片**，要"照这个样子再打一张 / 一批"。
- 用户用**自然语言**描述标签（尺寸 + 写什么 + 条码内容），要直接打出来。
- 要在已有标签上改字号、换品名、挪位置，重新出图。
- 要查某条 ZPL 命令、某个条码制式的参数位序、某个问题码是什么意思。

**引擎随 skill 走**：`vendor/wheels/` 里是 [zpl-core](https://github.com/benyshen/zpl-core) 的 wheel（含 OCR 模型），`setup.py` 离线装进 `.venv` 并校验哈希。不依赖 `zebra-printer-mcp`，不需要注册任何 MCP 服务器。装好即用。

**不适用**：RFID 编码、打印机 SNMP 监控、`^GF` 位图流 / `~DG` 字体下载、跨打印机并发调度。

## 一次性安装

```bash
python scripts/setup.py          # 建 .venv、校验并装 zpl-core wheel、装 7 个依赖（首次约 95 MB，1-3 分钟）
python scripts/setup.py --check  # 只检查，不安装
```

成功最后一行是 `READY: <skill>/.venv/Scripts/python.exe`。

装不上、要换镜像、要接 Windows 队列或 USB、要看依赖清单——把用户指向 `docs/install.md`（人看的完整安装与排错文档）。

之后**所有命令都用这个解释器**（下文记作 `$PY`）：

```bash
PY="<skill>/.venv/Scripts/python.exe"      # Windows
PY="<skill>/.venv/bin/python"              # macOS / Linux
```

别用系统 python：`build`/`validate`/`status` 确实零依赖，但 `render` 要 pillow、`photo` 要 opencv + numpy + onnxruntime + zxing-cpp。

## 打印机地址

```bash
export ZEBRA_HOST=<打印机IP>        # 设一次，后续不用再写 --host
$PY scripts/label.py printers       # 不知道地址时先列 Windows 打印队列
$PY scripts/label.py status         # 确认 0000 = PRINTER READY 再打
```

## 任务 A：照片 -> ZPL -> 打印

```bash
# 1) 先出 ZPL 和预览，不出纸
$PY scripts/label.py photo 标签照片.jpg \
    --width 70 --height 70 --paper 76 --paper-height 70 \
    --dry-run --out scratch/a.zpl --preview scratch/a.png

# 2) 看 elements / warnings / issues，确认无误后去掉 --dry-run
$PY scripts/label.py photo 标签照片.jpg \
    --width 70 --height 70 --paper 76 --paper-height 70 --out scratch/a.zpl
```

**尺寸参数怎么给**（最容易错的一步）：

| 参数 | 含义 |
|---|---|
| `--width` / `--height` | **印刷图案**的物理尺寸 |
| `--paper` / `--paper-height` | **纸**的物理尺寸，纸比图案大时必填 |

模切料常见 76 mm 的纸承载 70 mm 图案。只给 `--width` 不给 `--paper`，整版会按 70/76 缩小约 8%（表现就是"整体小了一圈"）。

**`--frame` 怎么选**：

- `auto`（默认）：自动找标签四角做透视校正。照片带桌面背景、拍摄有倾角时用它，几何最准。
- `full`：把整张照片当作标签。**照片已经裁到标签边缘时用它**。

实测同一张照片：`auto` 下 OCR 在字块边缘多吃进一个笔画（`五朵花纯净水` -> `广五朵花纯净水`），换 `full` 就正常。所以——

> **OCR 多字/少字时，第一反应是换 `--frame`，不是重拍。** 单个字仍错，就直接改生成 ZPL 里那段 `^FD`。

`--frame full` 的前提是照片**裁得正好**：宽高比与 `--width/--height` 不符会触发 `ASPECT` 警告，整版被缩放。看到这个警告说明该裁照片或换回 `auto`。

## 任务 B：自然语言 -> 标签

用户说"打一张 60x40 的标签，上面条码 ABC123，下面写南京"，要做的是**写一份 spec JSON**，不是手拼 ZPL：

```json
{"dpi": 203, "width_mm": 60, "height_mm": 40,
 "fields": [
   {"type": "barcode", "symbology": "code128", "data": "ABC123",
    "x_mm": 3.8, "y_mm": 2.6, "height_mm": 9.4, "module_width": 3},
   {"type": "text", "data": "南京", "x_mm": 20, "y_mm": 28,
    "size_mm": 5.4, "font_file": "E:SIMSUN.TTF"}
 ]}
```

```bash
$PY scripts/label.py print spec.json --dry-run --preview scratch/b.png   # 先看
$PY scripts/label.py print spec.json                                     # 再打
```

字段全表（20 个顶层键、7 种 field type、28 种条码的位序与默认值）在 `references/spec-schema.md`。**条码参数位序必须查表，不能套 `^BC` 的格式**——各制式的 `Format:` 行不一样。

必须由用户给、不要猜的四个物理事实：**标签尺寸、dpi、打印机地址、份数**。猜错不报错，只会打出废纸。

## 任务 C：批量打 Excel / 查手册

一行一条标签（文字 + Code 128），整批拼成**一条 ZPL 流、一次 TCP 连接**发出，回显只读一次：

```bash
$PY scripts/label.py xlsx 员工名单.xlsx --width 50 --height 30 \
    --dry-run --preview scratch/first.png        # 先看第一条
$PY scripts/label.py xlsx 员工名单.xlsx --width 50 --height 30
```

| 参数 | 说明 |
|---|---|
| `--name-column` / `--id-column` | Excel 字母（`A`）、1 起序号（`2`）或表头名（`姓名`）；默认 `A` / `B` |
| `--no-header` | 第一行是数据而非表头（默认当表头跳过） |
| `--max-labels` | 安全阀，默认 2000；超出直接拒绝而不是打废纸 |
| `--sheet` | 工作表名，默认第一张 |

**条码列必须是 ASCII**（数字、字母、`-`）。中文姓名放文字列——中文塞进 Code 128 打出来是乱码。

查手册（别凭记忆写 ZPL）：

```bash
$PY scripts/label.py knowledge BY               # 精确命令，^ 可省
$PY scripts/label.py knowledge "darkness|speed" --mode search
$PY scripts/label.py knowledge --mode barcodes   # 28 制式 + 参数规则 + ^BY 默认值
$PY scripts/label.py knowledge --mode sgd        # 27 条 SGD
$PY scripts/label.py knowledge --mode status     # 13 个状态码
$PY scripts/label.py knowledge --mode list       # 253 个命令字
```

## 停止判据

| 看到什么 | 含义 | 动作 |
|---|---|---|
| `issues` 里有 `severity: error` | spec/ZPL 不合法 | 不打印，改 spec |
| 只有 `warning`（`CI_CJK`） | 提示性 | 已确认有内置中文字体的机器可忽略 |
| `warnings` 有 `ASPECT` | 照片宽高比与标签不符 | 整版会缩放：裁照片或换 `--frame` |
| `warnings` 有 `MODULE_TOO_SMALL` | 条码模块太细 | 加大 `--width` 或调 `module_width` |
| `render` 的 `warnings` 报文本超 `^FB` 块宽 | 版式溢出 | 调字号或块宽 |
| `status` 的 `status.code != "0000"` | 打印机没准备好 | 看 `name`（缺纸/开盖/过热） |
| `send` 的 `response` 为空 | ZPL 无语法错（正常） | 成功 |
| `send` 的 `response` 含 `?` 或报错串 | 打印机拒收 | 读回显定位 |
| `labels` 为 0 | 表头没跳过或列选错 | 检查 `--no-header`、`--id-column` |
| `rows_read` 比 `labels` 大很多 | 有条码列空白的行被跳过 | 正常；值不符就回去看表 |
| `render` 的 `approximated` 非空 | 预览有降级（DataMatrix/PDF417/复杂图形） | 预览别当准，实打验证 |

## 硬性纪律

1. **`--dry-run` 必须显式加**，`send` / `print` / `photo` 默认都是真发。
2. **中文标签**：text 字段给 `font_file`（`E:SIMSUN.TTF` / `E:HANS.TTF`），引擎自动加 `^CI28` + UTF-8 字节。不要自己拼 `^A@`，宽度位也别留空。
3. **校验通过 != 能扫**。静区、模块宽、纠错级只有纸和扫码枪知道；出纸前至少 `render` 看一眼版式。
4. **浓度用 `~SD`（绝对），不要 `^MD`**（相对增量会跨任务累积，越打越黑）。
5. **`job_id` 只证明入队**（windows/usb 通道）。要确凿证据用 tcp 看回显。
6. **表格线不自动重建**：照片复刻出的 ZPL 没有 `^GB` 边框，需要时手工补（见 `references/calibration.md` 第 6 条）。
7. **文字位置别手算**：多行/居中用 `block`（`^FB`），让打印机自己排。

## 照片复刻的校准

第一版打完对不上，按 `references/calibration.md` 六条逐项核对：纸 vs 印刷区、字高不用墨迹宽反推、零售码模块数查表、HRI 判据、位置微调用 `--offset-x/--offset-y`、表格线手工补。那张 70x70 标签就是靠这六条从"整体小一圈"调到实机 99%。

## 资产地图

| 路径 | 内容 |
|---|---|
| `scripts/setup.py` | 建 `.venv` + 装依赖；`--check` 只检查 |
| `scripts/label.py` | `photo` / `build` / `validate` / `render` / `status` / `send` / `print` / `printers` / `knowledge` / `xlsx` |
| `vendor/wheels/zpl_core-0.1.0-py3-none-any.whl` | 引擎本体（wheel，14.1 MB）：10 个模块 + 253 条命令目录 + PP-OCRv4 模型，装进 `.venv` 的 site-packages |
| `references/spec-schema.md` | label spec 全键表：20 顶层键、7 种 field type、28 制式位序与默认值 |
| `references/calibration.md` | 照片复刻六条校准规则（实机验证） |
| `templates/` | 两张 70x70 标签（ZR668 实机确认"输出完全正确"） |
| `examples/warehouse-70x70.spec.json` | 上面那张标签的 spec，可直接改 |
| `examples/product-70x70.spec.json` | 表格框商品标签（品名/五月花矿泉水/EAN-13），实机打印过 |
| `examples/employees.xlsx` | `xlsx` 子命令的样例表：A 列姓名、B 列工号，3 行 |

## 自检

```bash
$PY tests/test_skill.py     # -> ALL CHECKS PASSED
```

检查：内置引擎与模型齐全、无外部仓库依赖、模板可校验、示例 spec 与模板逐字节一致、28 种条码三表同集合、照片链可导入、渲染能出图。

## 已验证的环境

- CPython **3.14.5**（系统安装）与 **3.14.7**（uv 下载）各建全新 venv，均跑通。
- 隔离目录（不在任何工作区内）、未设任何外部引擎变量、无 MCP SDK：`build` / `validate` / `status` 全程零第三方模块加载。
- 实机 ZR668-200dpi（`V86.20.21Z`，TCP 9100）：照片 -> ZPL -> 打印 218 字节、无错误回显；`~HS 0000 = PRINTER READY`。
- 70 mm @ 203 dpi = **559 dots**（`round`，不是 ceil）。
- EAN-13 / UPC-A = **95 模块**；`^BY3` = 285 dots = 35.6 mm，两侧静区各 >=15 mm。
- 内置中文字体：`E:SIMSUN.TTF`、`E:HANS.TTF`、`E:TT0003M_.TTF`。
- 命令目录 253 条 / 条码 28 种（`BARCODE_SPECS` / `BARCODE_CMDS` / `BARCODE_NOTES` 必须同集合，测试有断言）。
