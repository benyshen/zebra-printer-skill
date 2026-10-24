# 照片复刻 70x70 标签的校准后 ZPL（实机打印，相似度 99%，ZR668-200dpi）
# 与 warehouse-label-70x70.zpl 的差就是校准结果：
#   - 标题/品名/品名值字号 47/32/43（墨迹宽不卡字高，见 references/calibration.md 第 2 条）
#   - EAN-13 条码 285 dots（95 模块 x ^BY3，居中 x=134）
#   - 表格线是手工补的 4 条 ^GB（照片里的线不自动识别，calibration.md 第 6 条）
#   - 打印顺序 = photo.convert 的字段顺序
^XA^PW559^LL559^CI28
^FO16,96^GB527,400,3,B,0^FS
^FO16,176^GB527,2,2,B,0^FS
^FO16,272^GB527,2,2,B,0^FS
^FO134,298^BY3,3,10^BEN,110^FD6934024512123^FS
^FO203,38^A@N,47,47,E:SIMSUN.TTF^FD仓库标签^FS
^FO75,134^A@N,32,32,E:SIMSUN.TTF^FD品名^FS
^FO68,194^A@N,43,43,E:SIMSUN.TTF^FD五朵花纯净水^FS
^XZ
