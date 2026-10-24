---
name: zebra-printer-skill
version: 0.1.0
author: Hermes (Nous Research)
license: MIT
description: 打 ZPL 标签、复刻旧标签照片、做 Zebra 打印脚本时加载。封装 zebra-printer-mcp 引擎的建模→校验→渲染→打印闭环，附实机校准规则。
metadata:
  hermes:
    tags: [zpl, zebra, label, barcode, printing, mcp, skill]
    related_skills: [zpl-zebra-printing, android-voice-zpl-printing]
---

## When to Use

- 要出一张 ZPL 标签：给尺寸和内容，生成 / 校验 / 预览 / 打印。
- 手上只有一张旧标签照片（或旧标签实物），要照原样重打一批。
- 批量名单打标签（xlsx → 一行一标签）。
- 需要查某条 ZPL 命令的语法、某个条码制式的参数位序、某个问题码是什么意思。

**不适用**：RFID 编码、打印机 SNMP 监控、`^GF` 位图流 / `~DG` 字体下载、跨打印机并发调度。这些引擎不做，见 §5。

## 这个 skill 与引擎的关系

本仓库**不含引擎代码**，只含流程、模板、校准知识和命令行封装。真正的实现是
[`zebra-printer-mcp`](https://github.com/benyshen/zebra-printer-mcp)（9 个 MCP 工具 + `zebra_mcp` 包）。

`scripts/_bootstrap.py` 按顺序找引擎：`ZEBRA_MCP_SRC` → `../zebra-printer-mcp/src` → `../../zebra-printer-mcp/src` → `ZEBRA_MCP_HOME` → `~/workspace/...` → `E:\workspace\...`。
找不到会明确报错，告诉你克隆什么、设哪个变量。

```bash
# 引擎和工作目录并排放着就能直接跑；否则显式指定：
export ZEBRA_MCP_SRC=/path/to/zebra-printer-mcp/src
```

## 依赖边界（什么能脱离什么）

**这个 skill 离不开引擎**——引擎缺失时 `_bootstrap` 直接 `SystemExit` 并给出克隆命令。这是刻意的：引擎的修复能自动传导，不会分叉。

但**引擎不等于 MCP**。三层依赖是分开的：

| 能力 | 需要引擎 | 需要 `mcp` SDK | 需要 `[render]` extras |
|---|---|---|---|
| `build` / `validate` | ✅ | ❌ | ❌ |
| `send`（tcp/windows/usb） | ✅ | ❌ | ❌ |
| `status` | ✅ | ❌（无 SDK 时走本地 `~HS` 回退） | ❌ |
| `render` | ✅ | ❌ | ✅ pillow/segno/python-barcode |

也就是说：**不必注册 MCP 服务器、不必装 `mcp` 包**，`label.py` 就能建模、校验、查看、打印、查状态。只有想用 agent 的工具调用形态时，才需要把 server 注册进客户端。

`render` 缺 `python-barcode` 时不会崩，但 1D 码只画占位框，并把它列进返回的 `approximated[]`——所以**看 `approximated` 是否为空**就知道这张预览的可信度。

### 想彻底独立？代价是分叉

需要把 5 个模块拷进来：`builder.py` / `knowledge.py` / `catalog.py` / `transport.py` / `render.py`（合计 **1,683 行、≈89 KB**），外加 `data/command_catalog.txt`（**1.25 KB**）。

布局必须保持 `src/zebra_mcp/` 与**同级**的 `data/`——`knowledge.py` 用 `Path(__file__).parents[2] / "data"` 找目录。实测把包单独装进 site-packages（`data/` 不在相对位置）时：命令目录退化成 **33 条**，连 `^XA`/`^FO`/`^FD`/`^FS`/`^XZ` 都被报 `UNKNOWN_CMD`，校验器直接失去意义。这一步比“拷文件”更容易踩。

代价：引擎更新不会自动进来，得手动 rebase。**建议保持薄封装**——除非要在完全无网络的机器上离线分发。

## 资产地图

| 路径 | 内容 |
|---|---|
| `scripts/label.py` | 命令行：`build` / `validate` / `render` / `status` / `send` / `print` |
| `scripts/_bootstrap.py` | 定位并导入引擎（`builder/catalog/knowledge/transport`） |
| `references/spec-schema.md` | **label spec 全键表**：顶层 20 键、7 种 field type、28 种条码的位序与默认值、专属键、单位换算 |
| `references/calibration.md` | **照片复刻的六条校准规则**（实机验证，相似度 99%）——做复刻前必读 |
| `templates/warehouse-label-70x70.zpl` | 70×70 仓库标签，ZR668 实机确认“输出完全正确” |
| `templates/photo-reprint-70x70.zpl` | 同尺寸照片复刻的校准版 ZPL |
| `examples/warehouse-70x70.spec.json` | 上面那张标签的 spec，可直接改 |

## 五步闭环

```bash
PY=/path/to/zebra-printer-mcp/.venv/Scripts/python.exe

$PY scripts/label.py build  examples/warehouse-70x70.spec.json --out scratch/a.zpl
$PY scripts/label.py validate scratch/a.zpl
$PY scripts/label.py render  scratch/a.zpl --scale 2 --out scratch/a.png
$PY scripts/label.py status  --host 192.168.28.90
$PY scripts/label.py send    scratch/a.zpl --host 192.168.28.90
```

一条命令走完全流程（`--dry-run` 只到预览，不出纸）：

```bash
$PY scripts/label.py print examples/warehouse-70x70.spec.json --host 192.168.28.90 --dry-run
```

每一步的停止判据：

| 结果 | 含义 | 动作 |
|---|---|---|
| `issues` 里有 `severity: error` | spec 不合法 | **不要打印**，改 spec |
| 只有 `warning`（如 `CI_CJK`） | 可用但要知道风险 | 确认后继续；`CI_CJK` 在已确认有内置中文字体的机器上可忽略 |
| `render` 的 `warnings` 报文本超 `^FB` 块宽 | 版式会溢出 | 调字号或块宽 |
| `status` 的 `status.code != "0000"` | 打印机没准备好 | 看 `name`（缺纸/开盖/过热） |
| `send` 返回 `response` 为空 | 没语法错误（ZPL 无回显=正常） | 成功 |
| `send` 返回 `response` 里有 `?` 或错误串 | 打印机拒收 | 读回显定位 |

## 硬性纪律

1. **`send_zpl` 的 `dry_run` 默认是 false**——`scripts/label.py send` 默认也真发。想先看必须显式 `--dry-run`。
2. **物理事实只能由人给**：标签尺寸、dpi、打印机地址、份数。猜错不会报错，只会打出废纸。
3. **中文标签**：`^CI28`（UTF-8）+ `^A@` 内置 TrueType（`E:SIMSUN.TTF` / `E:HANS.TTF`）。text 字段给 `font_file`，**不要**自己拼 `^A@`，宽度位别留空。
4. **`^A@` 的宽度缺省取高度**，不是留空。`^A@N,28,,E:SIMSUN.TTF` 能打但宽度不可控。
5. **校验通过 ≠ 能扫**。静区、模块宽、纠错级只有纸和扫码枪知道。出纸前至少 `render` 看一眼版式。
6. **`job_id` 只证明入队**（windows/usb 通道），不证明纸出来了。要确凿证据用 `tcp` 看回显。
7. **浓度用 `~SD`（绝对），不要 `^MD`**（相对增量，会跨任务累积，越打越黑）。

## 常见任务怎么起手

**打一张新标签**：照 `examples/warehouse-70x70.spec.json` 改。先用 `_mm` 坐标，别手算 dots。
字段位序查 `references/spec-schema.md` §3，别凭记忆套 `^BC` 的格式。

**复刻照片**：先读 `references/calibration.md` 全六条，再走：

```bash
python -c "import sys;sys.path.insert(0,'src');from zebra_mcp import server;print(server.zpl_from_image('shot.jpg', width_mm=70, height_mm=70, paper_mm=76))"
```

关键三个参数：`width_mm`/`height_mm` = **图案**尺寸，`paper_mm` = **纸**尺寸（模切料常是 76×70 载 70×70）。
第一版必然要校准，按 `calibration.md` 逐条核对，位置微调用 `offset_x_mm`/`offset_y_mm`。

**批量名单**：走引擎的 `print_xlsx`（`xlsx_batch` 模块），一行一标签、单个流发送，别在脚本里循环单发。

**查命令**：

```bash
python -c "import sys;sys.path.insert(0,'src');from zebra_mcp import server;print(server.zpl_knowledge(mode='command', query='^BY'))"
```

## 已验证的环境与数字

- 实机：**ZR668-200dpi**，固件 `V86.20.21Z`，8 dots/mm，8192KB，TCP 9100。
- 70×70 mm @ 203 dpi = **559 dots**（`round`，不是 ceil）。
- EAN-13 / UPC-A = **95 模块**；`^BY3` → 285 dots = 35.6 mm，两侧静区各 ≥15 mm。
- 内置中文字体：`E:SIMSUN.TTF`（10 MB）、`E:HANS.TTF`（19 MB）、`E:TT0003M_.TTF`。
- Fusion 系老固件对 SGD `getvar` 回 `?`；`printer_status` 自动回退到 `~HI`/`~HS`。
- catalog：253 条命令 / 28 种条码制式（三张表 `BARCODE_SPECS`/`BARCODE_CMDS`/`BARCODE_NOTES` 必须同集合，测试里有断言）。

## 自检

```bash
$PY tests/test_skill.py
```

校验：两份模板的每个命令都在命令目录里、示例 spec 与模板语义一致、`build` 无 error、`render` 能出图、条码三表同集合、references 里被引用的文件真实存在。
