"""Generate full SRT from AI segment ASS subtitles + reaction captions (no title card version)"""
import re, os

BASE = os.path.dirname(os.path.abspath(__file__))
CS_DIR = os.path.join(BASE, "presentation", "video_output", "consciousness_stream")

STRUCTURE = [
    ("seg0_cold_open",       16.1,   0.0,   "ai"),
    ("seg1_hybrid",          36.0,  16.6,   "ai"),
    ("reaction_A",           15.1,  53.1,   "rec"),
    ("seg2_why_it_works",    63.8,  68.7,   "ai"),
    ("seg3_mirror_blindspot",83.0, 133.0,   "ai"),
    ("reaction_B",           15.1, 216.5,   "rec"),
    ("seg4_step_four",       34.6, 232.1,   "ai"),
    ("seg5_danger_dao",      53.0, 267.2,   "ai"),
    ("seg6_closing",         59.5, 320.7,   "ai"),
    ("reaction_C",           46.0, 380.7,   "rec"),
]

SEG_ASS_MAP = {
    "seg0_cold_open": "seg0_cold_open",
    "seg1_hybrid": "seg1_method_result",
    "seg2_why_it_works": "seg2_why_it_works",
    "seg3_mirror_blindspot": "seg3_mirror_blindspot",
    "seg4_step_four": "seg4_step_four",
    "seg5_danger_dao": "seg5_danger_dao",
    "seg6_closing": "seg6_closing",
}

REACTION_SUBS = {
    "reaction_A": [(0.5,4.0,"(碰撞高点)"),(4.5,8.0,"我靠...牛逼牛逼"),(8.5,14.0,"这个太厉害了")],
    "reaction_B": [(0.5,5.0,"你叫别人不要做的事"),(5.5,10.0,"你自己正在做"),(10.5,14.0,"这面镜子...")],
    "reaction_C": [(0.5,6.0,"这个方法论自己验证了自己"),(7.0,15.0,"意识流编程做出来的视频"),(15.5,22.0,"讲的是意识流编程"),(23.0,30.0,"它自己检查了自己的创造者"),(31.0,38.0,"牛逼...真的牛逼"),(39.0,45.0,"包括这句话")],
}

def parse_ass_time(t):
    m = re.match(r'(\d+):(\d+):(\d+)\.(\d+)', t)
    if not m: return 0.0
    return int(m[1])*3600 + int(m[2])*60 + int(m[3]) + int(m[4])/100.0

def fmt(seconds):
    h,r = divmod(seconds,3600); m,r = divmod(r,60); s = int(r); ms = int((r-s)*1000)
    return f"{int(h):02d}:{int(m):02d}:{s:02d},{ms:03d}"

def extract_ass(seg_name):
    d = SEG_ASS_MAP.get(seg_name)
    if not d: return []
    p = os.path.join(CS_DIR, d, "subtitles.ass")
    if not os.path.exists(p): return []
    out = []
    with open(p,'r',encoding='utf-8') as f:
        for line in f:
            if not line.startswith('Dialogue:'): continue
            parts = line.split(',',9)
            if len(parts)<10: continue
            s,e = parse_ass_time(parts[1]), parse_ass_time(parts[2])
            txt = re.sub(r'\{[^}]*\}','',parts[9].strip())
            if txt: out.append((s,e,txt))
    return out

def main():
    entries = []; idx = 1
    for seg,dur,offset,typ in STRUCTURE:
        if typ == "ai":
            for s,e,txt in extract_ass(seg):
                entries.append((idx, offset+s, min(offset+e, offset+dur), txt)); idx+=1
        elif typ == "rec":
            for s,e,txt in REACTION_SUBS.get(seg,[]):
                entries.append((idx, offset+s, min(offset+e, offset+dur), txt)); idx+=1
    out = os.path.join(BASE,"bilibili_publish","matched_bilibili_hq.srt")
    with open(out,'w',encoding='utf-8') as f:
        for i,s,e,t in entries:
            f.write(f"{i}\n{fmt(s)} --> {fmt(e)}\n{t}\n\n")
    print(f"{len(entries)} entries -> {out}")
    for i,s,e,t in entries[:3]: print(f"  {i}. {fmt(s)} | {t}")
    print("  ...")
    for i,s,e,t in entries[-3:]: print(f"  {i}. {fmt(s)} | {t}")

if __name__=="__main__": main()
