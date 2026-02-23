"""快速dump UI节点"""
import xml.etree.ElementTree as ET, re, sys

path = sys.argv[1] if len(sys.argv) > 1 else r"e:\道\道生一\一生二\手机操控库\ui_dump.xml"
root = ET.parse(path).getroot()
for n in root.iter('node'):
    t = n.get('text', '').strip()
    d = n.get('content-desc', '').strip()
    b = n.get('bounds', '')
    if (t or d) and len(t + d) > 1:
        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
        if m:
            cx = (int(m[1]) + int(m[3])) // 2
            cy = (int(m[2]) + int(m[4])) // 2
            label = t or d
            if len(label) > 65:
                label = label[:65] + '...'
            print(f'[{cx:4d},{cy:4d}] {label}')
