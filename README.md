# zebra-printer-skill

一个**自带引擎**的 Hermes skill：给一张标签照片就能反推成 ZPL，或者直接用自然语言描述要打什么，就能打到 Zebra 打印机上。

不需要克隆 `zebra-printer-mcp`，不需要注册 MCP 服务器，不需要 MCP SDK。装好这个目录、跑一次 setup 即可。

## 安装（干净机器，一次性）

```bash
python scripts/setup.py          # 建 .venv，装 7 个包（首次约 80 MB）
python scripts/setup.py --check  # 只检查
```

之后所有命令用 skill 自己的解释器：

```bash
PY="<skill>/.venv/Scripts/python.exe"    # Windows
PY="<skill>/.venv/bin/python"            # macOS / Linux
```

```bash
export ZEBRA_HOST=192.168.28.90          # 打印机地址，设一次
$PY scripts/label.py status              # 0000 = PRINTER READY
```

## 两条主用法

**照片 -> ZPL -> 打印**

```bash
$PY scripts/label.py photo 标签.jpg --width 70 --height 70 --paper 76 --paper-height 70 \
    --dry-run --out scratch/a.zpl --preview scratch/a.png

# 看过 elements / warnings 后去掉 --dry-run 就出纸
$PY scripts/label.py photo 标签.jpg --width 70 --height 70 --paper 76 --paper-height 70
```

`--width/--height` 是**图案**尺寸，`--paper/--paper-height` 是**纸**尺寸（模切料常是 76 mm 纸载 70 mm 图案，只给前者会整体缩 8%）。

**自然语言 -> 标签**

写一份 spec JSON，然后一条命令走完 build -> validate -> 渲染 -> 发送：

```bash
$PY scripts/label.py print spec.json --dry-run --preview scratch/b.png
$PY scripts/label.py print spec.json
```

spec 的字段全表见 `references/spec-schema.md`（20 个顶层键、7 种 field type、28 种条码的位序与默认值）。

## 子命令

| 命令 | 作用 |
|---|---|
| `photo <image>` | 照片 -> ZPL（可同时打印） |
| `build <spec.json>` | spec -> ZPL |
| `validate <file>` | 按手册命令目录校验 |
| `render <file.zpl>` | 离线渲染 PNG，先看版式 |
| `status` | `~HI`/`~HS` 查型号与状态字 |
| `send <file.zpl>` | 发送（tcp / windows 队列 / usb） |
| `print <spec.json>` | build+validate+render+send |
| `printers` | 列 Windows 打印队列 |

全部输出 JSON，出错退出码 1。

## 目录

| 路径 | 内容 |
|---|---|
| `SKILL.md` | 触发条件、安装、两条主任务、停止判据、七条纪律 |
| `references/spec-schema.md` | label spec 全键表 + 28 制式位序 |
| `references/calibration.md` | 照片复刻六条校准规则（实机 99%） |
| `vendor/src/zebra_mcp/` | 引擎本体，10 个模块，无 MCP 服务端 |
| `vendor/data/` | 命令目录 253 条 + PP-OCRv4 模型 15 MB |
| `templates/` `examples/` | 两张实机验证过的 70x70 标签 |
| `scripts/` | `setup.py` / `label.py` / `_bootstrap.py` |
| `tests/test_skill.py` | 自检 |

## 自检

```bash
$PY tests/test_skill.py     # -> ALL CHECKS PASSED
```

## 边界

不做 RFID、`^GF` 位图流、`~DG` 字体下载、SNMP 监控、并发调度。校验通过不代表码能扫——静区、模块宽、纠错级只有纸和扫码枪能确认。表格线不会从照片自动重建，需要时补 `^GB`。

## License

MIT（`vendor/` 内含的 PaddleOCR 模型为 Apache-2.0）
