# label spec 字段参考

`generate_zpl(label_spec=…)` 吃的就是这个 JSON。尺寸默认 **mm**，带 `_dots` 后缀的直接给打印机点（203 dpi ≈ 8 dots/mm）。

表里的 `symbology`、`type`、字母位序全部来自 `builder.BARCODE_SPECS` / 手册 `Format:` 行，不是记忆。

---

## 1. 顶层键

| 键 | 类型 | 作用 | 发出的 ZPL |
|---|---|---|---|
| `dpi` | int | 打印头分辨率，152/203/300/600 | — （只影响换算） |
| `width_mm` / `height_mm` | float | 标签物理尺寸 | `^PW` / `^LL` |
| `print_width_dots` / `label_length_dots` | int | 直接给点数，覆盖上面两个 | `^PW` / `^LL` |
| `quantity` | int | 份数 | `^PQ` |
| `darkness` | int −30…30 | **绝对**浓度 | `~SD`（不是 `^MD`，`^MD` 是跨任务累积的增量） |
| `char_encoding` | int | `^CI` 值；有中文且没给时自动 `28`（UTF-8） | `^CI` |
| `print_speed` / `slew_speed` / `backfeed_speed` | 1–6 或 A/D | 打印/走纸/回退速度 | `^PR` |
| `mirror` / `invert` | bool | 镜像 / 反白 | `^PM` / `^PO` |
| `shift_left` / `label_top` | int | 整版左移 / 顶偏移 | `^LS` / `^LT` |
| `media_tracking` | `{mode, black_mark_offset}` | 介质跟踪 | `^MN` |
| `print_mode` | `{mode, media_loss}` | 撕纸/剥离/切刀模式 | `^MM` |
| `barcode_defaults` | `{module_width, ratio, bar_height}` | 全局 `^BY` | `^BY` |
| `default_font` | `{font, height, width}` | 默认字体 | `^CF` |
| `default_orientation` | N/R/I/B | 默认方向 | `^FW` |
| `fields` | list | 元素列表，见 §2 | — |

`^PW`/`^LL` 超出范围（`^PW` 2–`PW_MAX`、`^LL` 1–`LL_MAX`）会报 `error`。

---

## 2. fields 的七种 type

| type | 发出什么 | 关键键 |
|---|---|---|
| `text` | `^FO` → `^A0N`/`^A@` → (`^FB`) → (`^FH`) → `^FD` → `^FS` | `data`、`size_mm`/`size_dots`、`font_file`、`width_mm`/`width_dots`、`block`、`no_hex` |
| `barcode` | `^FO` → (`^BY`) → `^B…` → `^FD` → `^FS` | `symbology`、`data`、见 §3 |
| `note` / `box` | `^GB`（**同一条命令**，两个名字） | `width_*`、`height_*`、`thickness`、`rounding`、`reverse` |
| `circle` | `^GC` | `diameter_*`、`thickness` |
| `reverse` | `^FR` | 作用于随后的字段 |
| `image` | `^XGR:<name>,1,1`（引用打印机内已存的图形） | `name`、`device`(R/E) |

**坐标**：每个元素都可用 `x_mm/y_mm` 或 `x_dots/y_dots`，**逐轴独立**——`x_dots` + `y_mm` 混用是合法的（居中条码时常用）。只写 `x_dots` 不会把 `y` 归零。

**text 专有**：

- `font_file`：`E:SIMSUN.TTF` 这类打印机内置 TrueType → 发 `^A@N,h,w,<font>`；宽度缺省时取高度，**不要留空**（`^A@N,28,,E:SIMSUN.TTF` 是坑）。
- `size_dots`：照片反推来的尺寸，范围 10–32000（`^A` 可缩放字体下限 10 dots）。
- `block`：`{width_dots|width_mm, lines, line_spacing, alignment(C/L/R/J), hanging_indent}` → `^FB`。**居中靠它，不要手算 x**。
- `no_hex`：默认遇到特殊字符会加 `^FH` + 十六进制转义；`no_hex=true` 关掉。

---

## 3. 28 种条码（key / 命令 / 位序 / 默认）

`symbology` 用小写 key。**字母位序按各制式自己的 `Format:` 行**，不能套 `^BC` 的 `o,h,f,g,e`。

| key | 名称 | 命令 | 手册页 | 参数位序 | 默认值 |
|---|---|---|---|---|---|
| `aztec` | Aztec | `^BO` | p.124 | a,b,c,d,e,f,g | a=N b=2 c=N d=0 e=N |
| `codabar` | Codabar | `^BK` | p.118 | o,e,h,f,g,k,l | o=N e=N f=Y g=N k=A l=A |
| `codablock` | CODABLOCK | `^BB` | p.99 | o,h,s,c,r,m | o=N h=8 s=Y m=A |
| `code11` | Code 11 | `^B1` | p.72 | o,e,h,f,g | o=N e=N f=Y g=N |
| `code128` | Code 128 / GS1-128 | `^BC` | p.94 | o,h,f,g,e,m | o=N f=Y g=N e=N m=N |
| `code39` | Code 39 | `^B3` | p.70 | o,e,h,f,g | o=N e=N f=Y g=N |
| `code49` | Code 49 | `^B4` | p.74 | o,h,f,m | o=N f=N m=2 |
| `code93` | Code 93 | `^BA` | p.87 | o,h,f,g,e | o=N f=Y g=N e=N |
| `datamatrix` | Data Matrix | `^BX` | p.144 | o,h,s,c,r | o=N s=200 c=0 r=1 |
| `ean13` | EAN-13 | `^BE` | p.109 | o,h,f,g | o=N f=Y g=N |
| `ean8` | EAN-8 | `^B8` | p.83 | o,h,f,g | o=N f=Y g=N |
| `gs1databar` | GS1 DataBar | `^BR` | p.135 | a,b,c,d,e,f | a=R b=1 d=1 e=25 f=22 |
| `i2of5` | Interleaved 2 of 5 | `^B2` | p.68 | o,h,f,g,e,j | o=N f=Y g=N e=N j=N |
| `industrial2of5` | Industrial 2 of 5 | `^BI` | p.114 | o,h,f,g | o=N f=Y g=N |
| `logmars` | LOGMARS | `^BL` | p.120 | o,h,g | o=N g=N |
| `micropdf417` | MicroPDF417 | `^BF` | p.111 | o,h,m | o=N m=0 |
| `msi` | MSI | `^BM` | p.122 | o,e,h,f,g,E | o=N e=B f=Y g=N E=N |
| `pdf417` | PDF417 | `^B7` | p.79 | o,h,s,c,r,t | o=N s=0 c=1 r=3 t=N |
| `planet` | Planet Code | `^B5` | p.78 | o,h,f,g | o=N f=N g=N |
| `plessey` | Plessey | `^BP` | p.126 | o,e,h,f,g | o=N e=N f=Y g=N |
| `postnet` | POSTNET | `^BZ` | p.150 | o,h,f,g,t | o=N f=N g=N t=0 |
| `qrcode` | QR Code | `^BQ` | p.128 | a,b,c,d,e | a=N b=2 c=0 d=Q e=7 |
| `std2of5` | Standard 2 of 5 | `^BJ` | p.116 | o,h,f,g | o=N f=Y g=N |
| `upca` | UPC-A | `^B9` | p.85 | o,h,f,g,e | o=N f=Y g=N e=N |
| `upce` | UPC-E | `^B0` | p.66 | o,e,h,f,g | o=N e=N f=Y g=N |
| `upcext` | UPC/EAN add-on | `^BS` | p.137 | o,h,f,g | o=N f=Y g=Y |
| `upsmaxicode` | UPS MaxiCode | `^BD` | p.106 | m,n,t | m=2 n=1 t=1 |
| `usps` | USPS IM Barcode | `^BZ` | p.150 | o,h,f,g,t | o=N f=N g=N t=3 |

### 通用条码键

`symbology`、`data`、`x_*`/`y_*`、`orientation`(N/R/I/B)、`height_mm`/`height_dots`、`module_width`(1–10)、`module_ratio`(2.0–3.0)、`bar_height`、`no_hex`。

后三个（`module_*`/`bar_height`）会**就地重发 `^BY`**——一张标签上两个条码可以各自不同宽度。

### 各制式专属键

| 制式 | 专属键 |
|---|---|
| `datamatrix` | `module_size_dots`(1–25)、`quality`(0/50/80/100/140/200)、`columns`、`rows` |
| `qrcode` | `scale`(1–100)、`ec_level`(H/Q/M/L)、`model`(1/2)、`mask`(0–7) |
| `pdf417` | `security_level`、`columns`、`row_ratio` |
| `micropdf417` | `mode`(0–33) —— **不是** PDF417 的 s/c/r |
| `gs1databar` | `symbology_type`(1–12)、`magnification`、`separator_height`、`segment_width`；**高度走 `e` 位**，不在 `h` |
| `code49` | `interpret_pos`(N/A/B)、`mode` |
| `codablock` | `security`(Y/N)、`columns`、`rows`、`mode`(A/E/F) |
| `codabar` | `start_char`、`stop_char`(A–D) |
| `upsmaxicode` | `mode`、`symbol_number`、`total_symbols`（**没有方向参数**） |
| `msi` | `check_digit`(A/B/C/D) |

### 两个必须记住的数据规则

- **QR `^FD` 必须以 `<纠错级><输入模式>,` 开头**（手册 p.129 标 Mandatory）。`qrcode` 会自动加，等价 `^FDQA,<data>`（H 级时 `^FDHA,`）。手写 ZPL 时漏了，码扫不出来但语法不报错。
- **GS1 DataMatrix 没有单独的 key**：用 `datamatrix`，数据前面加 FNC1 转义 `>8`（手册：FNC1 由 `>8` 调用，插在 AI 前）。

---

## 4. 单位与排版

- `mm → dots`：`round(mm × dpi / 25.4)`。70 mm @ 203 dpi = `70 × 7.9921 = 559.45` → **559**。用 round，不要 ceil（ceil 会得到 560，整版右移 1 dot）。
- 居中两种：`text` 用 `^FB...,C` 让打印机自己居中；`barcode` 没有内建居中，得自己算 `x = (label_width − symbol_width) / 2`。
- **静区**：1D 码两侧留 ≥ 10×模块宽。EAN-13/UPC-A 是 95 模块，`^BY3` = 285 dots。

---

## 5. 校验能查出什么、查不出什么

`validate_zpl` 依次做四件事：抹掉 `^FD` 里的数据（`100~200` 不该被当命令）→ 对照 253 条命令目录 → 检查 `^BQ` 的 `^FD` 前缀 → 检查 `^XA`/`^XZ` 配对。

**查不出**的：静区不够、模块太细扫不出、纠错级选错、打印机缺字体。这些要么靠 `render_zpl` 看版式，要么只能打出来扫。

问题码分组：命令/位置（`UNKNOWN_CMD` 等）、字体与编码（`CI_CJK`、`TEXT_SIZE`）、条码语义（`QR_FD_PREFIX`、`BC_HEIGHT`、`MPDF_MODE`、`DM_QUALITY`…）、版式（`PW`、`LL`）、照片重建（`ASPECT`、`MODULE_TOO_SMALL`、`OCR_DROPPED`）。
