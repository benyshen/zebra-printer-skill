# vendor/ — 内置引擎的来源与同步方式

这里是从 [`zebra-printer-mcp`](https://github.com/benyshen/zebra-printer-mcp) 复制过来的引擎，
目的是让本 skill **脱离原仓库、脱离 MCP 客户端**独立运行。

## 内容

| 路径 | 来源 | 说明 |
|---|---|---|
| `src/zebra_mcp/{builder,knowledge,catalog,transport,render,photo,ocr,vision,xlsx_batch,__init__}.py` | 上游 `src/zebra_mcp/` | **不含 `server.py`**：那是 MCP 服务端外壳，会引入 `mcp` SDK 依赖 |
| `data/command_catalog.txt` | 上游 `data/` 同名文件 | 253 条 ZPL 命令目录，1.25 KB |
| `data/ocr/*.onnx`, `ppocr_keys_v1.txt` | PaddleOCR PP-OCRv4 (Apache-2.0) | 15 MB，为「装上就能认字」而随包分发 |

布局不能改：`knowledge.py` 用 `Path(__file__).parents[2] / "data"` 找数据目录，
所以必须是 `vendor/src/zebra_mcp/` + 同级 `vendor/data/`。改布局会让命令目录退化到 33 条，
校验器连 `^XA`/`^FO` 都会报未知。

## 上游改了怎么同步

```bash
UPSTREAM=/path/to/zebra-printer-mcp
for f in __init__ builder catalog knowledge transport render photo ocr vision xlsx_batch; do
  cp "$UPSTREAM/src/zebra_mcp/$f.py" vendor/src/zebra_mcp/
done
cp "$UPSTREAM/data/command_catalog.txt" vendor/data/
# 模型只需在换版本时更新
.venv/Scripts/python.exe tests/test_skill.py     # 必须仍然 ALL CHECKS PASSED
```

同步后请**只改本仓库的流程层**（`scripts/label.py`、`SKILL.md`、`references/`），
不要在 `vendor/` 里打补丁——否则下次同步会覆盖掉。真需要改引擎行为，改上游仓库再同步过来。

## 已知分叉风险

这是刻意的取舍：换来「一个目录装完就能用」，代价是上游修复不会自动进来。
`tests/test_skill.py` 里的断言（28 种条码三表同集合、模板可校验、spec 与模板逐字节一致）
就是为了让「同步了一半」这种状态在测试里暴露出来。
