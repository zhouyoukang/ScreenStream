import re
with open(r"D:\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js","r",encoding="utf-8",errors="ignore") as f:
    c = f.read()
# Find message types with role/content fields (ChatMessage candidates)
for m in re.finditer(r'newFieldList\(\(\)=>\[\{no:\d+,name:"(?:role|author|source)', c):
    txt = c[m.start():m.start()+800]
    fields = re.findall(r'\{no:(\d+),name:"(\w+)",kind:"(\w+)"(?:,T:(\w+))?', txt)
    if len(fields) >= 3:
        print(f"@{m.start()} ({len(fields)} fields):")
        for fno, fn, fk, ft in fields:
            print(f"  {fno}: {fn} ({fk} T={ft})")
        print()
