# vendor/ 里放什么，为什么，怎么换

这里只有一样东西：**zpl-core 引擎的 wheel**。

```
vendor/wheels/zpl_core-0.1.0-py3-none-any.whl   13.8 MB
sha256  3fbe0e56fd40a04d0d801f1e6c5a45e2dba6da7f6fa17178e5f68d8b40354894
```

这个哈希与 PyPI 上 `zpl_core-0.1.0-py3-none-any.whl` 的 sha256 **完全相同**——也就是说，`setup.py` 从 PyPI 装的那份和这里兜底的那份是同一个文件，不是两次构建。

zpl-core 已发布到 PyPI（https://pypi.org/project/zpl-core/），所以这里的作用从"唯一来源"变成"离线兜底"：

- 有网：`setup.py` 直接 `pip install zpl-core==0.1.0`，vendor 里的 wheel 只用来核验（哈希不符仍然拒绝安装）
- 无网：`python scripts/setup.py --offline` 强制用这份 wheel，`--no-index --no-deps` 不碰网络
- wheel 被删掉也能装（在线场景），`--offline` 下缺 wheel 直接报错并提示重建

## 为什么是 wheel，不是源码副本

v0.3.0 及以前，这里放的是 `vendor/src/zebra_mcp/` —— 10 个引擎模块的手工副本。它能用，但有两个问题：

1. **代码分叉**。上游修 bug 不会自动进来，得手工同步，同步一半就静默漂移。
2. **审计不了**。副本长得像源码，看起来可改，改了就成了第二份实现。

wheel 是**构建产物**：不可编辑、有版本号、有哈希。skill 装的永远和 zpl-core 仓库 `v0.1.0` 发布的一致。

## 数据在哪

以前 `vendor/data/` 放命令目录和 PP-OCRv4 权重，现在它们在 **wheel 里**（`zpl_core/data/`），随包安装：
`command_catalog.txt`（253 条）、`ocr/*.onnx`（14.9 MB）。skill 目录因此少了 15 MB 的散落文件。

## 升级引擎的步骤

```bash
# 1. 从 zpl-core 源码构建（hatchling 后端）
cd /e/workspace/zpl-core
git pull                        # 或切到目标 tag
.venv/Scripts/python.exe -m pip wheel . -w dist --no-deps
# → dist/zpl_core-0.2.0-py3-none-any.whl

# 2. 换进 skill，改三个常量
cp dist/zpl_core-0.2.0-py3-none-any.whl ../zebra-printer-skill/vendor/wheels/
rm ../zebra-printer-skill/vendor/wheels/zpl_core-0.1.0-*.whl
# scripts/setup.py：ENGINE_WHEEL / ENGINE_SHA256 / ENGINE_REQ 三行
sha256sum ../zebra-printer-skill/vendor/wheels/zpl_core-0.2.0-py3-none-any.whl

# 3. 重装并自检
.venv/Scripts/python.exe scripts/setup.py     # 会先校验哈希，不匹配直接拒绝
.venv/Scripts/python.exe tests/test_skill.py
```

`setup.py` 在装之前校验 sha256，不匹配就**拒绝安装**——防止"vendor 里的 wheel 被悄悄换掉"。

## 校验

- `tests/test_skill.py` 断言：wheel 存在、哈希等于 `setup.py` 里的常量、`zpl_core` 解析到 `.venv` 的 site-packages 而**不是** skill 目录内、仓库里没有 `vendor/src`。 
- 装完跑 `setup.py --check`：报告引擎版本与导入路径。

## 相关仓库

- 引擎：https://github.com/benyshen/zpl-core（MIT）
- MCP 外壳：https://github.com/benyshen/zebra-printer-mcp（MIT，依赖同一个包）
