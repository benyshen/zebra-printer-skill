# zebra-printer-skill

把 [zebra-printer-mcp](https://github.com/benyshen/zebra-printer-mcp) 的 ZPL 能力封装成一套**可复用的打印流程**：label spec 建模 → 校验 → 离线渲染看图 → 打印 → 状态回读，外加照片复刻旧标签的实机校准规则。

引擎不在本仓库里。本仓库只有流程、模板、校准知识和一个命令行封装——所以引擎更新时这里不需要跟着改。

## 装什么

只需要一个能跑引擎的 Python（引擎的 `requirements` 见上层仓库）：

```bash
git clone https://github.com/benyshen/zebra-printer-mcp.git
cd zebra-printer-mcp && python -m venv .venv
.venv/Scripts/pip install -e ".[render]"     # [render] 给 render_zpl 用（pillow 等）
```

然后让本仓库找到引擎，二选一：

```bash
# A) 和 zebra-printer-mcp 放在同一个父目录下（自动发现，无需配置）
# B) 显式指定
export ZEBRA_MCP_SRC=/path/to/zebra-printer-mcp/src
```

## 用

```bash
PY=/path/to/zebra-printer-mcp/.venv/Scripts/python.exe

$PY scripts/label.py build    examples/warehouse-70x70.spec.json --out scratch/a.zpl
$PY scripts/label.py validate scratch/a.zpl
$PY scripts/label.py render   scratch/a.zpl --scale 2 --out scratch/a.png
$PY scripts/label.py status   --host <打印机IP>
$PY scripts/label.py send     scratch/a.zpl --host <打印机IP>

# 一条命令走到底，--dry-run 只到预览不出纸
$PY scripts/label.py print    examples/warehouse-70x70.spec.json --host <打印机IP> --dry-run
```

每个子命令都打印 JSON，出错退出码为 1，方便脚本和 agent 判断。

## 内容

| 路径 | 内容 |
|---|---|
| `SKILL.md` | 什么时候用、五步闭环、停止判据、七条硬性纪律 |
| `references/spec-schema.md` | label spec 全键表：顶层 20 键、7 种 field type、28 种条码位序与默认值、专属键、单位换算 |
| `references/calibration.md` | 照片复刻的六条校准规则（70×70 标签实机验证，相似度 99%） |
| `templates/warehouse-label-70x70.zpl` | 70×70 仓库标签，ZR668 实机确认“输出完全正确” |
| `templates/photo-reprint-70x70.zpl` | 同尺寸照片复刻的校准版 |
| `examples/warehouse-70x70.spec.json` | 上面那张标签的 spec |
| `scripts/label.py` | 命令行封装 |
| `scripts/_bootstrap.py` | 定位并导入引擎 |
| `tests/test_skill.py` | 自检（文件齐全、模板可校验、spec≡模板、三张条码表同集合、引用不断链） |

## 能不能不装引擎？

**不能**——本仓库是薄封装，引擎缺失时 `_bootstrap` 会直接报错并给出克隆命令（刻意如此，引擎修复能自动传导）。

但**引擎 ≠ MCP**：不必注册 MCP 服务器、不必装 `mcp` 包，`label.py` 就能 build/validate/send/status。只有 `render` 需要 `[render]` extras（缺 `python-barcode` 时 1D 码降级为占位框，会列进 `approximated`）。

要彻底独立得把 5 个模块（1,683 行 / ≈89 KB）+ `data/command_catalog.txt`（1.25 KB）拷进来，且必须保持 `src/zebra_mcp/` 与同级 `data/` 的布局——否则命令目录退化成 33 条，校验器会把 `^XA`/`^FO` 之类全报未知。详见 `SKILL.md` 的「依赖边界」。

## 自检

```bash
$PY tests/test_skill.py     # → ALL CHECKS PASSED
```

## 边界

不做 RFID、`^GF` 位图流、`~DG` 字体下载、SNMP 监控、并发调度。校验通过不代表码能扫——静区、模块宽、纠错级只有纸和扫码枪能确认。

## License

MIT
