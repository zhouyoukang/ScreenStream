import xml.etree.ElementTree as ET, re, sys
f = sys.argv[1] if len(sys.argv)>1 else r"e:\道\道生一\一生二\手机操控库\jd_my.xml"
kw = sys.argv[2].split(",") if len(sys.argv)>2 else ["订单","待付","待收","全部","查看","退换"]
root = ET.parse(f).getroot()
for n in root.iter("node"):
    t,d,b = n.get("text",""), n.get("content-desc",""), n.get("bounds","")
    if any(k in t+d for k in kw):
        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
        if m:
            cx,cy = (int(m[1])+int(m[3]))//2, (int(m[2])+int(m[4]))//2
            print(f"t={t!r:35s} d={d!r:20s} cx={cx:4d} cy={cy:4d}")
