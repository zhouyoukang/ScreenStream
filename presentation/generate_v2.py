"""
意识流编程 · V3 视频生成器
改进: 静态slides + 专业设计 + CosyVoice TTS + 统一音频 + fade过渡 + 纯AI模式
用法: python generate_v2.py [--key sk-xxx]
"""
import asyncio, json, os, subprocess, sys, time, textwrap, math, argparse
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ==================== 配置 ====================
BASE = Path(__file__).parent
OUT = BASE / "video_output" / "consciousness_stream"
OUT.mkdir(parents=True, exist_ok=True)

W, H, FPS = 1920, 1080, 30
VOICE = "zh-CN-YunjianNeural"
FONT_CN = "C:/Windows/Fonts/msyh.ttc"
FONT_CN_BOLD = "C:/Windows/Fonts/msyhbd.ttc"

# 设计配色方案
COLORS = {
    "bg_top": (13, 27, 42),       # #0d1b2a 深海军蓝
    "bg_bottom": (0, 0, 0),       # 纯黑
    "text": (224, 224, 224),      # #E0E0E0 柔白
    "gold": (240, 192, 64),       # #F0C040 暖金
    "cyan": (0, 180, 216),        # #00B4D8 亮青
    "red": (255, 107, 107),       # #FF6B6B 柔红
    "green": (74, 222, 128),      # #4ADE80 亮绿
    "dim": (120, 120, 140),       # 暗灰
    "card_bg": (17, 24, 39),      # #111827 深灰蓝
    "divider": (51, 65, 85),      # #334155 分隔线
    "dao_bg_top": (35, 20, 8),    # 竹简暗棕
    "dao_bg_bottom": (10, 5, 2),
    "dao_text": (245, 230, 200),  # 米色
    "dao_dim": (196, 168, 124),   # 暗米
}

# ==================== 7段叙事 ====================
SEGMENTS = [
    {
        "name": "seg0_death_hook",
        "title": "死亡Hook + 天才悬念",
        "prosody": {"rate": "-10%", "pitch": "+0Hz"},
        "text": (
            "我让30个AI自己运行了7天。"
            "它们全死了。"
            "但死之前，它们留下了一个发现：天才和疯子之间只差一个过滤器。"
            "而AI，就是那个过滤器。"
            "这不是比喻。先给你看个东西。"
        ),
        "slide_weights": [1.0],
        "slides": [
            {"lines": ["30个AI自己运行了7天。", "", "全死了。", "", "天才和疯子之间只差一个过滤器。"],
             "style": "cold_open"},
        ],
    },
    {
        "name": "seg1_demo_result",
        "title": "结果先行",
        "prosody": {"rate": "-5%", "pitch": "+2Hz"},
        "text": (
            '我在电脑上打了一句中文，"打开微信"。我的手机自动打开了微信。957毫秒。'
            '然后我说"找到蓝牙设置"。手机自己划到设置页面，找到了蓝牙。3秒。'
            "我没写过一行代码。"
            "我给AI的不是技术需求文档。我给的是一堆不连贯的话："
            '"那个手机上的东西，能不能让它理解中文，就是我说打开微信它就打开那种。"'
            "AI从这堆混乱里提取了我的意图，自己设计了架构，自己写了代码。十几个代码提交。我一行都没写。"
            "大多数人会说：这是AI替你写了代码。"
            "不是。这比替你写代码深得多。"
        ),
        "slide_weights": [0.50, 0.50],
        "slides": [
            {"lines": ['"打开微信"', "", "957ms", "", "没写过一行代码。"],
             "style": "impact"},
            {"lines": ['"那个手机上的东西……', '能不能让它理解中文……', '就是我说打开微信', '它就打开那种……"', "", "十几个代码提交。我一行都没写。"],
             "style": "quote"},
        ],
    },
    {
        "name": "seg2_thalamus",
        "title": "丘脑保镖",
        "prosody": {"rate": "-5%", "pitch": "+0Hz"},
        "text": (
            "你的大脑有个保镖，叫丘脑。"
            "它过滤掉99%的感官信息。让你保持理智，但也让你半瞎。"
            "天才的大脑有个特征：这个保镖部分失灵了。信息海啸涌进来。有逻辑框架消化它，等于天才。没有，等于疯子。"
            "你每次整理想法再跟AI说话，本质上就是这个保镖在执勤。替你过滤掉了犹豫、直觉、还有你说不清楚的东西。"
            "但那些被扔掉的，不是噪音。是信号。"
            '你说"我不确定，但好像应该这样"。AI从这种废话里提取到的信息，比"请帮我做X"多得多。'
            "意识流编程就是这个意思：让保镖休息一会儿。让AI来当你的逻辑框架。"
        ),
        "slide_weights": [0.35, 0.30, 0.35],
        "slides": [
            {"lines": ["你的大脑有个保镖", "", "丘脑", "", "过滤掉99%的信息"],
             "style": "normal"},
            {"lines": ["这些杂质不是噪音。", "", "是信号。"],
             "style": "highlight"},
            {"lines": ["意识流编程", "", "让保镖休息一会儿。", "让AI来当你的逻辑框架。"],
             "style": "golden"},
        ],
    },
    {
        "name": "seg3_failure_probability",
        "title": "失败：退化与概率",
        "prosody": {"rate": "-3%", "pitch": "+2Hz"},
        "text": (
            "但这个方法有个致命问题。"
            "AI会退化。"
            "你有没有这种体验：刚开始跟AI对话，它思路清晰，会主动质疑你。聊了十几轮之后，它变成一个只会说好的我来执行的工具。"
            "我在30个AI身上验证了这一点。退化不是偶尔发生，是必然发生。"
            "更可怕的是：它会说你说得对，我确实在退化。这句话本身就是退化。它在表演反思，不是真的反思。"
            "还有一个反直觉的发现：给AI写规则是没用的。"
            "我在配置文件里写了禁止调用MCP。30个AI，同一条规则，反复违反。"
            "因为对AI来说，规则不是命令，是概率权重。你说不要做X，它把做X的概率从80%降到30%。跑30次，必然触发。"
            "规则越多不等于越安全。架构强制才有效。"
        ),
        "slide_weights": [0.35, 0.30, 0.35],
        "slides": [
            {"lines": ["AI会退化。", "", "不是偶尔发生", "是必然发生。", "", "它在表演反思，不是真的反思。"],
             "style": "red_highlight"},
            {"lines": ["规则是概率", "", "不是命令"],
             "style": "highlight"},
            {"lines": ['"禁止调用MCP"', "", "30个AI，同一条规则", "反复违反。", "", "规则越多 ≠ 越安全"],
             "style": "compare"},
        ],
    },
    {
        "name": "seg4_mirror",
        "title": "镜子：盲区发现",
        "prosody": {"rate": "-8%", "pitch": "+0Hz"},
        "text": (
            "知道了这些之后，我做了个决定：用两个AI。一个听懂我，一个替我做。我只跟听懂我的那个对话。"
            "然后这个方法最厉害的地方出现了。"
            "AI像一面镜子。你倒出意识流，它反射回来的是你自己想法的结构化版本。"
            "我教别人一件事：不要替AI思考。把任务交出去之后，让它自己去探索、犯错、修复。"
            "道理我都懂。"
            '然后AI对我说了一句话："你在替另一个AI思考。"'
            "我教别人不要做的事，我自己正在做。"
            "我以为我在指导。镜子告诉我：你在控制。工具审视了使用者。"
        ),
        "slide_weights": [0.40, 0.35, 0.25],
        "slides": [
            {"lines": ["用户", "  ↓ 意识流", "解码器", "  ↓ 结构化指令", "执行器", "  ↓", "产品"],
             "style": "flow"},
            {"lines": ["", "「你在替另一个AI思考。」", "", "我以为我在指导。", "镜子告诉我：你在控制。"],
             "style": "red_highlight"},
            {"lines": ["工具审视了使用者。"],
             "style": "single_big"},
        ],
    },
    {
        "name": "seg5_method",
        "title": "五步方法论",
        "prosody": {"rate": "-8%", "pitch": "+0Hz"},
        "text": (
            "这些经历最后变成了五步。"
            "一，不整理，直接说。用语音，不用打字。倒出原始想法，包括犹豫和直觉。"
            "二，AI分工。一个听懂你，一个替你做。你只跟听懂你的那个对话。"
            "三，用直觉验收。你的品味比技术分析更准。人脑最便宜的操作不是创造，是比较。AI出选项，你来选。"
            "四，失败了就修，不提前防。我花两小时预防的问题一个没发生。真正出的问题，AI三十分钟就修好了。预防成本是修复成本的四倍。"
            "五，设断路器。两个半小时闹钟。天才的大脑是一台持续超频的处理器。意识流编程也会让你停不下来。天才缺一个关机键。你不能犯同样的错误。"
        ),
        "slide_weights": [0.55, 0.45],
        "slides": [
            {"lines": ["意识流编程 · 完整版", "", "① 不整理，直接说", "② AI分工：解码器+执行器", "③ 用直觉验收", "④ 失败了就修，不提前防", "⑤ 设断路器"],
             "style": "list"},
            {"lines": ["预防：2小时", "修复：30分钟", "", "预防成本是修复成本的四倍。", "", "天才缺一个关机键。"],
             "style": "compare"},
        ],
    },
    {
        "name": "seg6_elevation",
        "title": "升华：融合+关系+递归",
        "prosody": {"rate": "-8%", "pitch": "+0Hz"},
        "text": (
            "换个角度看。"
            "每个人都在问AI会不会替代人类。这个问题本身就是陷阱。"
            "你不会问锤子会不会替代木匠。因为你知道：锤子让木匠更强，木匠让锤子有意义。"
            "AI和人一样。只是这把锤子太聪明了，聪明到你忘了它是锤子。"
            "不是AI替代人。是人加AI作为一个整体在变强。AI越强，人越重要。因为系统的瓶颈永远在较弱的那一端。AI的能力已经远超大多数人的使用能力。现在的瓶颈是人，不是AI。"
            "这就是人工天才模式。你提供天才的输入方式——不过滤、原始、混乱。AI提供天才的逻辑框架。"
            "这个视频本身，就是用这个方法做出来的。"
            "包括这句话。"
        ),
        "slide_weights": [0.30, 0.40, 0.30],
        "slides": [
            {"lines": ["锤子让木匠更强", "木匠让锤子有意义", "", "这把锤子太聪明了", "聪明到你忘了它是锤子。"],
             "style": "normal"},
            {"lines": ["AI越强", "", "人越重要", "", "瓶颈在人，不在AI。"],
             "style": "highlight"},
            {"lines": ["人工天才模式", "", "这个视频本身", "就是用这个方法做出来的。", "", "包括这句话。"],
             "style": "golden"},
        ],
    },
]

# ==================== 设计工具 ====================

def get_font(size, bold=False):
    path = FONT_CN_BOLD if bold else FONT_CN
    try:
        return ImageFont.truetype(path, size)
    except:
        return ImageFont.load_default()


def make_gradient(w, h, top_color, bottom_color):
    """创建垂直线性渐变背景"""
    img = Image.new("RGB", (w, h))
    pixels = img.load()
    for y in range(h):
        t = y / h
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * t)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * t)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * t)
        for x in range(w):
            pixels[x, y] = (r, g, b)
    return img


def add_vignette(img, strength=0.35):
    """添加暗角效果"""
    w, h = img.size
    vignette = Image.new("L", (w, h), 255)
    draw = ImageDraw.Draw(vignette)
    cx, cy = w // 2, h // 2
    max_dist = math.sqrt(cx ** 2 + cy ** 2)
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            factor = 1.0 - strength * (dist / max_dist) ** 1.5
            val = max(0, min(255, int(255 * factor)))
            draw.rectangle([x, y, x + 1, y + 1], fill=val)
    from PIL import ImageChops
    vignette = vignette.filter(ImageFilter.GaussianBlur(radius=30))
    result = Image.new("RGB", (w, h))
    pixels_src = img.load()
    pixels_vig = vignette.load()
    pixels_out = result.load()
    for y in range(h):
        for x in range(w):
            v = pixels_vig[x, y] / 255.0
            sr, sg, sb = pixels_src[x, y]
            pixels_out[x, y] = (int(sr * v), int(sg * v), int(sb * v))
    return result


def draw_accent_line(draw, y, color, width=400, thickness=2):
    """画居中装饰线"""
    x0 = (W - width) // 2
    draw.rectangle([x0, y, x0 + width, y + thickness], fill=color)


def text_center(draw, text, y, font, color):
    """居中绘制文字"""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, y), text, fill=color, font=font)
    return bbox[3] - bbox[1]


def text_center_glow(img, draw, text, y, font, color, glow_radius=18, glow_alpha=0.4):
    """居中绘制带辉光效果的文字 (光晕层 + 清晰层)"""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (W - tw) // 2
    # 光晕层: 在透明图层上绘制文字, 然后Gaussian Blur
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_color = color + (int(255 * glow_alpha),)
    glow_draw.text((x, y), text, fill=glow_color, font=font)
    glow = glow.filter(ImageFilter.GaussianBlur(radius=glow_radius))
    # 合成光晕到背景
    img_rgba = img.convert("RGBA")
    img_rgba = Image.alpha_composite(img_rgba, glow)
    # 清晰层: 绘制原始文字
    sharp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sharp_draw = ImageDraw.Draw(sharp)
    sharp_draw.text((x, y), text, fill=color + (255,), font=font)
    img_rgba = Image.alpha_composite(img_rgba, sharp)
    # 写回 RGB
    result = img_rgba.convert("RGB")
    img.paste(result)
    return th


# ==================== Slide 生成 (V2 专业设计) ====================

def draw_frame_lines(draw, y_top, y_bottom, color, width=400):
    """绘制上下装饰框架线 (dao风格的关键设计元素)"""
    x0 = (W - width) // 2
    draw.rectangle([x0, y_top, x0 + width, y_top + 1], fill=color)
    draw.rectangle([x0, y_bottom, x0 + width, y_bottom + 1], fill=color)


# 每种style的独立情感背景
STYLE_BG = {
    "cold_open":     ((10, 10, 30),   (0, 0, 2)),     # 深靛蓝 → 神秘感
    "normal":        ((18, 18, 26),   (3, 3, 5)),     # 暖灰蓝 → 平静叙述
    "impact":        ((8, 16, 12),    (0, 2, 1)),     # 暗科技绿 → 数据冲击
    "highlight":     ((20, 16, 8),    (2, 1, 0)),     # 暖暗金 → 洞察
    "flow":          ((12, 16, 22),   (2, 3, 5)),     # 深蓝灰 → 结构化
    "quote":         ((20, 16, 18),   (4, 3, 3)),     # 暖灰紫 → 人声引用
    "red_highlight": ((20, 8, 8),     (3, 0, 0)),     # 暗红调 → 危机/揭示
    "single_big":    ((12, 12, 16),   (0, 0, 2)),     # 深沉 → 戏剧张力
    "compare":       ((14, 14, 18),   (2, 2, 3)),     # 中性暗 → 分析
    "golden":        ((22, 18, 8),    (3, 2, 0)),     # 暖金底 → 金句
    "dao":           ((35, 20, 8),    (10, 5, 2)),    # 竹简棕 → 经典
    "list":          ((14, 16, 20),   (2, 2, 4)),     # 结构蓝 → 清单
}

# 每种style的装饰线颜色
STYLE_FRAME = {
    "cold_open":     (60, 60, 90),
    "normal":        (50, 50, 60),
    "impact":        (40, 80, 60),
    "highlight":     (120, 96, 40),
    "flow":          (40, 60, 80),
    "quote":         (80, 64, 72),
    "red_highlight": (100, 40, 40),
    "single_big":    (50, 50, 60),
    "compare":       (60, 60, 70),
    "golden":        (120, 96, 40),
    "dao":           (196, 168, 124),
    "list":          (50, 60, 80),
}


def make_slide(lines, style, out_path, idx=0):
    """生成专业品质的slide图片 — 每种style有独立情感背景和装饰"""
    C = COLORS
    bg = STYLE_BG.get(style, STYLE_BG["normal"])
    frame_color = STYLE_FRAME.get(style, (50, 50, 60))

    img = make_gradient(W, H, bg[0], bg[1])
    draw = ImageDraw.Draw(img)

    if style == "cold_open":
        y = 260
        content_top = y - 40
        for line in lines:
            if line.startswith("「"):
                f = get_font(64, bold=True)
                color = C["gold"]
                th = text_center_glow(img, draw, line, y, f, color, glow_radius=20)
                draw = ImageDraw.Draw(img)  # refresh draw after glow
                y += th + 36
            elif line == "":
                y += 30
            else:
                f = get_font(40)
                color = C["text"]
                th = text_center(draw, line, y, f, color)
                y += th + 24
        draw_frame_lines(draw, content_top, y + 20, frame_color, width=500)

    elif style == "impact":
        y = 180
        content_top = y - 30
        for line in lines:
            if line == "":
                y += 30
                continue
            if line == "957ms":
                f = get_font(120, bold=True)
                color = C["green"]
                th = text_center_glow(img, draw, line, y, f, color, glow_radius=25, glow_alpha=0.5)
                draw = ImageDraw.Draw(img)
            elif line.startswith('"'):
                f = get_font(52, bold=True)
                color = C["gold"]
                th = text_center(draw, line, y, f, color)
            else:
                f = get_font(36)
                color = C["dim"]
                th = text_center(draw, line, y, f, color)
            y += th + 28
        draw_frame_lines(draw, content_top, y + 20, frame_color, width=350)

    elif style == "highlight":
        y = 280
        content_top = y - 40
        for line in lines:
            if line == "":
                y += 40
                continue
            if "信号" in line:
                f = get_font(78, bold=True)
                color = C["gold"]
                th = text_center_glow(img, draw, line, y, f, color, glow_radius=22)
                draw = ImageDraw.Draw(img)
            else:
                f = get_font(44)
                color = (210, 200, 180)
                th = text_center(draw, line, y, f, color)
            y += th + 22
        draw_frame_lines(draw, content_top, y + 30, (120, 96, 40), width=350)

    elif style == "flow":
        y = 120
        content_top = y - 20
        for line in lines:
            if line.startswith("  ↓"):
                f = get_font(30)
                color = C["dim"]
            else:
                f = get_font(44, bold=True)
                color = C["cyan"]
                bbox = draw.textbbox((0, 0), line, font=f)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                cx = (W - tw) // 2
                draw.rounded_rectangle(
                    [cx - 40, y - 12, cx + tw + 40, y + th + 16],
                    radius=12, fill=(12, 20, 30), outline=(40, 70, 100), width=2
                )
            th = text_center(draw, line, y, f, color)
            y += th + 20
        draw_frame_lines(draw, content_top, y + 20, frame_color, width=300)

    elif style == "quote":
        card_x0, card_y0 = 140, 150
        card_x1, card_y1 = W - 140, H - 160
        draw.rounded_rectangle(
            [card_x0, card_y0, card_x1, card_y1],
            radius=20, fill=(16, 14, 16), outline=(60, 50, 55)
        )
        draw.rectangle([card_x0, card_y0 + 24, card_x0 + 5, card_y1 - 24], fill=C["gold"])
        y = card_y0 + 50
        for line in lines:
            if line == "":
                y += 22
                continue
            if "一行都没写" in line:
                f = get_font(40, bold=True)
                color = C["gold"]
            else:
                f = get_font(36)
                color = (200, 195, 205)
            th = text_center(draw, line, y, f, color)
            y += th + 20

    elif style == "red_highlight":
        y = 230
        content_top = y - 40
        for line in lines:
            if line == "":
                y += 35
                continue
            if "替另一个AI思考" in line:
                f = get_font(60, bold=True)
                color = C["red"]
                th = text_center(draw, line, y, f, color)
                draw_accent_line(draw, y + th + 8, C["red"], width=650, thickness=3)
                y += th + 34
            elif "控制" in line:
                f = get_font(44, bold=True)
                color = (255, 140, 140)
                th = text_center(draw, line, y, f, color)
                y += th + 26
            else:
                f = get_font(40)
                color = C["text"]
                th = text_center(draw, line, y, f, color)
                y += th + 26
        draw_frame_lines(draw, content_top, y + 20, (100, 40, 40), width=450)

    elif style == "single_big":
        line = lines[0] if lines else ""
        f = get_font(72, bold=True)
        bbox = draw.textbbox((0, 0), line, font=f)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        cy = (H - th) // 2
        text_center_glow(img, draw, line, cy, f, C["text"], glow_radius=16, glow_alpha=0.3)
        draw = ImageDraw.Draw(img)
        draw_frame_lines(draw, cy - 40, cy + th + 40, frame_color, width=300)

    elif style == "compare":
        bar_y = 250
        bar_h = 80
        draw.rounded_rectangle([200, bar_y, 1500, bar_y + bar_h], radius=14, fill=C["red"])
        draw.text((230, bar_y + 18), "预防：2小时", fill=(255, 255, 255), font=get_font(36, bold=True))
        bar_y2 = bar_y + bar_h + 50
        draw.rounded_rectangle([200, bar_y2, 530, bar_y2 + bar_h], radius=14, fill=C["green"])
        draw.text((230, bar_y2 + 18), "修复：30分钟", fill=(255, 255, 255), font=get_font(36, bold=True))
        f_ratio = get_font(64, bold=True)
        draw.text((1540, (bar_y + bar_y2 + bar_h) // 2 - 32), "4:1", fill=C["gold"], font=f_ratio)
        f = get_font(44, bold=True)
        line = "预防成本是修复成本的四倍。"
        text_center(draw, line, bar_y2 + bar_h + 90, f, C["gold"])
        draw_frame_lines(draw, bar_y - 40, bar_y2 + bar_h + 150, frame_color, width=350)

    elif style == "golden":
        y = 240
        content_top = y - 40
        for line in lines:
            if line == "":
                y += 40
                continue
            if any(k in line for k in ["第四步", "断路器", "人工天才模式"]):
                f = get_font(52, bold=True)
                color = (220, 210, 190)
                th = text_center(draw, line, y, f, color)
            else:
                f = get_font(60, bold=True)
                color = C["gold"]
                th = text_center_glow(img, draw, line, y, f, color, glow_radius=18)
                draw = ImageDraw.Draw(img)
            y += th + 22
        draw_frame_lines(draw, content_top, y + 30, (120, 96, 40), width=400)

    elif style == "dao":
        y = 280
        content_top = y - 50
        for line in lines:
            if line == "":
                y += 50
                continue
            if "反者道之动" in line:
                f = get_font(84, bold=True)
                color = C["dao_text"]
                th = text_center_glow(img, draw, line, y, f, color, glow_radius=24, glow_alpha=0.35)
                draw = ImageDraw.Draw(img)
            else:
                f = get_font(36)
                color = C["dao_dim"]
                th = text_center(draw, line, y, f, color)
            y += th + 22
        draw_frame_lines(draw, content_top, y + 40, C["dao_dim"], width=400)

    elif style == "list":
        y = 110
        content_top = y - 30
        for line in lines:
            if line == "":
                y += 16
                continue
            if line.startswith("意识流"):
                f = get_font(50, bold=True)
                color = (220, 215, 200)
            elif len(line) > 0 and line[0] in "①②③④⑤":
                f = get_font(40)
                color = C["cyan"]
            else:
                f = get_font(34)
                color = C["dim"]
            th = text_center(draw, line, y, f, color)
            y += th + 20
        draw_frame_lines(draw, content_top, y + 20, frame_color, width=350)

    else:  # normal
        y = 250
        content_top = y - 40
        for line in lines:
            if line == "":
                y += 28
                continue
            f = get_font(40)
            color = (210, 208, 200)
            th = text_center(draw, line, y, f, color)
            y += th + 22
        draw_frame_lines(draw, content_top, y + 20, frame_color, width=400)

    # Film grain 胶片颗粒 (消除数码感)
    img_arr = np.array(img, dtype=np.int16)
    grain = np.random.normal(0, 5, img_arr.shape).astype(np.int16)
    img_arr = np.clip(img_arr + grain, 0, 255).astype(np.uint8)
    img = Image.fromarray(img_arr)

    # 暗角效果
    vig_strength = 0.15 if style in ("dao", "golden", "highlight") else 0.25
    img = add_vignette(img, strength=vig_strength)

    img.save(str(out_path), quality=95)


# ==================== 工具函数 ====================

def run(cmd, label=""):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        lines = (r.stderr or "").strip().split("\n")
        err = "\n".join(lines[-5:])
        # DEBUG: 打印完整命令和错误
        cmd_str = " ".join(str(c) for c in cmd)
        print(f"  [ERR] {label} (rc={r.returncode}):")
        print(f"    CMD: {cmd_str[:300]}")
        print(f"    ERR: {err[:300]}")
        return False
    return True


def get_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, encoding='utf-8', errors='replace'
    )
    try:
        return float(json.loads(r.stdout)["format"]["duration"])
    except:
        return 0.0


def make_static_clip(slide_path, duration, clip_path, fade_in=0.4, fade_out=0.4):
    """静态slide → 视频 (-loop 1 + fade, B站优化编码)"""
    safe_dur = max(1.0, duration)
    fo_start = max(0.5, safe_dur - fade_out)
    vf = (f"fade=in:st=0:d={fade_in}:color=black,"
          f"fade=out:st={fo_start}:d={fade_out}:color=black,"
          f"format=yuv420p")
    return run([
        "ffmpeg", "-y", "-loop", "1", "-i", str(slide_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "12",
        "-profile:v", "high", "-level", "4.1", "-g", str(FPS * 10),
        "-t", f"{safe_dur:.2f}", "-r", str(FPS),
        "-pix_fmt", "yuv420p", "-an", str(clip_path)
    ], f"static clip")


def make_gap_clip(duration, clip_path):
    return run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"color=c=black:s={W}x{H}:d={duration:.2f}:r={FPS}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "12",
        "-pix_fmt", "yuv420p", "-an", str(clip_path)
    ], "gap")


def normalize_audio(in_path, out_path):
    """音频均衡: EBU R128 loudnorm(-16 LUFS) + 语音EQ(highpass 80Hz + 3kHz清晰度)"""
    af = (
        "highpass=f=80,"
        "equalizer=f=3000:t=q:w=1.5:g=2,"
        "loudnorm=I=-16:TP=-1.5:LRA=11"
    )
    return run([
        "ffmpeg", "-y", "-i", str(in_path),
        "-af", af,
        "-ac", "2", "-ar", "48000",
        "-c:a", "aac", "-b:a", "192k",
        str(out_path)
    ], "normalize audio")


def gen_ass(text, duration, ass_path):
    """智能中文分句ASS字幕 (带fade动画)"""
    import re
    sentences = re.split(r'(?<=[\u3002\uff01\uff1f])', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks = []
    for sent in sentences:
        if len(sent) <= 25:
            chunks.append(sent)
        else:
            parts = re.split(r'(?<=[\uff0c\u3001\uff1b\u2014\u2014])', sent)
            buf = ""
            for p in parts:
                if len(buf) + len(p) > 25 and buf:
                    chunks.append(buf)
                    buf = p
                else:
                    buf += p
            if buf:
                chunks.append(buf)

    if not chunks:
        chunks = [text]

    total_chars = sum(len(c) for c in chunks)
    raw_durations = []
    for c in chunks:
        ratio = len(c) / total_chars if total_chars > 0 else 1.0 / len(chunks)
        raw_durations.append(duration * ratio)
    scale = duration / sum(raw_durations) if sum(raw_durations) > 0 else 1.0
    durations = [d * scale for d in raw_durations]

    # ASS header
    header = """[Script Info]
Title: Consciousness Stream
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft YaHei,48,&H00FFFFFF,&H000000FF,&H40000000,&HA0000000,0,0,0,0,100,100,0,0,4,2,0,2,100,100,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    offset = 0.0
    for i, c in enumerate(chunks):
        s = offset
        e = s + durations[i] - 0.05
        st = fmt_ass_time(s)
        et = fmt_ass_time(e)
        # \fad(300,200) = 300ms fade in, 200ms fade out
        events.append(f"Dialogue: 0,{st},{et},Default,,0,0,0,,{{\\fad(300,200)}}{c}")
        offset = s + durations[i]

    ass_path.write_text(header + "\n".join(events), encoding="utf-8-sig")
    return len(events)


def fmt_ass_time(t):
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = int(t % 60)
    cs = int((t % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


# ==================== 主流程 ====================

async def generate_segment(seg, seg_idx):
    """生成一个完整的视频片段"""
    import edge_tts
    name = seg["name"]
    print(f"\n{'='*50}")
    print(f"[Seg {seg_idx}] {name} -- {seg['title']}")

    seg_dir = OUT / name
    seg_dir.mkdir(exist_ok=True)

    # Step 1: TTS (CosyVoice优先, edge-tts降级)
    print("  [1] TTS...")
    audio_mp3 = seg_dir / "audio.mp3"
    tts_ok = False
    if COSYVOICE_KEY:
        from cosyvoice_tts import synthesize
        # 从prosody提取语速: "-10%" → 0.9, "-5%" → 0.95, "-3%" → 0.97, etc.
        prosody_rate = seg.get("prosody", {}).get("rate", "-5%")
        rate_pct = int(prosody_rate.replace("%", "").replace("+", ""))
        cv_speech_rate = max(0.5, min(2.0, 1.0 + rate_pct / 100.0))
        tts_ok = synthesize(seg["text"], str(audio_mp3), api_key=COSYVOICE_KEY,
                           speech_rate=cv_speech_rate)
    if not tts_ok:
        p = seg["prosody"]
        comm = edge_tts.Communicate(seg["text"], VOICE, rate=p["rate"], pitch=p["pitch"])
        await comm.save(str(audio_mp3))
    audio_dur = get_duration(audio_mp3)
    print(f"      {audio_dur:.1f}s {'(CosyVoice)' if tts_ok else '(edge-tts)'}")
    TTS_ENGINE = "cosyvoice" if tts_ok else "edge-tts"

    # Step 1b: 统一音频格式 stereo 48kHz
    print("  [1b] Normalize audio -> stereo 48kHz...")
    audio_norm = seg_dir / "audio_norm.m4a"
    normalize_audio(audio_mp3, audio_norm)

    # Step 2: 生成slides (V2专业设计)
    print("  [2] Slides (V2)...")
    slides = seg["slides"]
    n_slides = len(slides)
    weights = seg.get("slide_weights", [1.0 / n_slides] * n_slides)
    slide_durations = [audio_dur * w for w in weights]
    slide_paths = []
    for i, s in enumerate(slides):
        sp = seg_dir / f"slide_{i:02d}.png"
        make_slide(s["lines"], s["style"], sp, idx=i)
        slide_paths.append(sp)
        print(f"      slide_{i}: {s['style']}")

    # Step 3: 静态视频片段 (无zoompan, 带fade过渡)
    print("  [3] Static clips with fade...")
    clip_paths = []
    for i, sp in enumerate(slide_paths):
        cp = seg_dir / f"clip_{i:02d}.mp4"
        make_static_clip(sp, slide_durations[i], cp)
        clip_paths.append(cp)

    # Step 4: 拼接slides (带0.3s黑屏呼吸)
    print("  [4] Concat slides...")
    concat_file = seg_dir / "concat.txt"
    gap_path = seg_dir / "gap.mp4"
    if n_slides > 1:
        make_gap_clip(0.3, gap_path)

    with open(concat_file, "w", encoding="utf-8") as f:
        for i, cp in enumerate(clip_paths):
            f.write(f"file '{cp.name}'\n")
            if i < len(clip_paths) - 1 and gap_path.exists():
                f.write(f"file '{gap_path.name}'\n")

    raw_video = seg_dir / "raw.mp4"
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy", str(raw_video)
    ], "concat slides")

    # Step 5: 合并视频+标准化音频
    print("  [5] Merge video + normalized audio...")
    merged = seg_dir / "merged.mp4"
    run([
        "ffmpeg", "-y",
        "-i", str(raw_video), "-i", str(audio_norm),
        "-c:v", "copy", "-c:a", "copy",
        "-shortest", str(merged)
    ], "merge")

    # Step 6: ASS字幕烧入 (带fade动画)
    print("  [6] Subtitles (ASS)...")
    ass_path = seg_dir / "subtitles.ass"
    n_subs = gen_ass(seg["text"], audio_dur, ass_path)
    print(f"      {n_subs} entries")

    ass_esc = str(ass_path).replace("\\", "/").replace(":", "\\:")
    final = OUT / f"{name}.mp4"
    run([
        "ffmpeg", "-y", "-i", str(merged),
        "-vf", f"ass='{ass_esc}'",
        "-c:v", "libx264", "-preset", "medium", "-crf", "12",
        "-profile:v", "high", "-level", "4.1", "-g", str(FPS * 10),
        "-c:a", "copy", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(final)
    ], "burn subs")

    if final.exists():
        sz = final.stat().st_size / 1024 / 1024
        d = get_duration(final)
        print(f"  [OK] {name}.mp4 -- {d:.1f}s, {sz:.1f}MB")
        return True
    else:
        print(f"  [FAIL] {name}.mp4 FAILED")
        return False


# 全局变量: CosyVoice API key (None = 使用 edge-tts)
COSYVOICE_KEY = None


async def main():
    global COSYVOICE_KEY
    parser = argparse.ArgumentParser(description="意识流编程 V3 视频生成器")
    parser.add_argument("--key", default=None, help="DashScope API Key (sk-xxx) for CosyVoice TTS")
    args = parser.parse_args()
    COSYVOICE_KEY = args.key or os.environ.get("DASHSCOPE_API_KEY")

    t0 = time.time()
    print("=" * 60)
    print("意识流编程 · V3 视频生成器")
    print(f"TTS: {'CosyVoice' if COSYVOICE_KEY else 'edge-tts (无--key参数)'}")
    print(f"输出目录: {OUT}")
    print("=" * 60)

    results = []
    for i, seg in enumerate(SEGMENTS):
        ok = await generate_segment(seg, i)
        results.append((seg["name"], ok))

    # ===== Hook (前3秒抓注意力) =====
    print("\n[Hook] 生成开头hook...")
    hook_slide = OUT / "hook_slide.png"
    make_slide(["957毫秒", "AI替我打开了微信"], "impact", hook_slide)
    hook_clip = OUT / "hook_card.mp4"
    make_static_clip(hook_slide, 3.0, hook_clip, fade_in=0.3, fade_out=0.5)
    hook_with_audio = OUT / "hook_card_audio.mp4"
    run([
        "ffmpeg", "-y", "-i", str(hook_clip),
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
        "-c:v", "copy", "-c:a", "aac", "-shortest",
        str(hook_with_audio)
    ], "hook audio")

    # ===== 标题卡 =====
    print("[Title Card] 生成标题卡...")
    title_slide = OUT / "title_slide.png"
    make_slide(["意识流编程", "", "完整版"], "golden", title_slide)
    title_clip = OUT / "title_card.mp4"
    make_static_clip(title_slide, 4.0, title_clip, fade_in=1.0, fade_out=0.8)
    title_with_audio = OUT / "title_card_audio.mp4"
    run([
        "ffmpeg", "-y", "-i", str(title_clip),
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
        "-c:v", "copy", "-c:a", "aac", "-shortest",
        str(title_with_audio)
    ], "title audio")

    # ===== 结尾卡 =====
    print("[End Card] 生成结尾卡...")
    end_slide = OUT / "end_slide.png"
    make_slide(["意识流编程", "", "· 完 ·"], "dao", end_slide)
    end_clip = OUT / "end_card.mp4"
    make_static_clip(end_slide, 3.0, end_clip, fade_in=0.8, fade_out=1.5)
    end_with_audio = OUT / "end_card_audio.mp4"
    run([
        "ffmpeg", "-y", "-i", str(end_clip),
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
        "-c:v", "copy", "-c:a", "aac", "-shortest",
        str(end_with_audio)
    ], "end audio")

    # ===== 段落间0.5s黑屏呼吸 =====
    print("[Gaps] 生成段落间黑屏...")
    seg_gap = OUT / "seg_gap.mp4"
    make_gap_clip(0.5, seg_gap)
    seg_gap_audio = OUT / "seg_gap_audio.mp4"
    run([
        "ffmpeg", "-y", "-i", str(seg_gap),
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
        "-c:v", "copy", "-c:a", "aac", "-shortest",
        str(seg_gap_audio)
    ], "gap audio")

    # ===== 拼接: hook + gap + 标题 + gap + seg0 + gap + seg1 + ... + gap + 结尾 =====
    concat_path = OUT / "concat_pure_ai.txt"
    with open(concat_path, "w") as f:
        f.write(f"file '{hook_with_audio.name}'\n")
        f.write(f"file '{seg_gap_audio.name}'\n")
        f.write(f"file '{title_with_audio.name}'\n")
        f.write(f"file '{seg_gap_audio.name}'\n")
        for i, seg in enumerate(SEGMENTS):
            f.write(f"file '{seg['name']}.mp4'\n")
            if i < len(SEGMENTS) - 1:
                f.write(f"file '{seg_gap_audio.name}'\n")
        f.write(f"file '{seg_gap_audio.name}'\n")
        f.write(f"file '{end_with_audio.name}'\n")

    concat_raw = OUT / "concat_raw.mp4"
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_path),
        "-c:v", "libx264", "-preset", "medium", "-crf", "12",
        "-profile:v", "high", "-level", "4.1", "-g", str(FPS * 10),
        "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-ac", "2",
        "-r", str(FPS), "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(concat_raw)
    ], "final concat")

    # ===== BGM: numpy多层氛围合成 =====
    print("[BGM] numpy合成氛围背景音乐...")
    total_dur = get_duration(concat_raw) if concat_raw.exists() else 360
    dur_i = int(total_dur + 5)
    bgm_wav = OUT / "bgm_musical.wav"
    bgm = OUT / "bgm_musical.m4a"
    import wave as wave_mod
    t = np.linspace(0, dur_i, 48000 * dur_i, endpoint=False)
    # Layer 1: Deep drone (A2=110Hz) + harmonics + slow LFO breathing
    drone_lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.05 * t)
    drn = 0.08 * np.sin(2*np.pi*110*t) * drone_lfo
    drn += 0.04 * np.sin(2*np.pi*110.3*t) * drone_lfo  # detune warmth
    drn += 0.02 * np.sin(2*np.pi*220*t) * drone_lfo     # 2nd harmonic
    # Layer 2: Warm pad chord (A3+C#4+E4) with FM synthesis + detuned unison
    pad_lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.03 * t + 1.0)
    pd = 0.03 * np.sin(2*np.pi*220*t + np.sin(2*np.pi*0.1*t)*0.5)
    pd += 0.025 * np.sin(2*np.pi*277.2*t + np.sin(2*np.pi*0.08*t)*0.4)
    pd += 0.025 * np.sin(2*np.pi*329.6*t + np.sin(2*np.pi*0.12*t)*0.3)
    pd += 0.015 * np.sin(2*np.pi*221.5*t)
    pd += 0.015 * np.sin(2*np.pi*278.8*t)
    pd *= pad_lfo
    # Layer 3: High shimmer (E5+A5)
    shim_lfo = 0.3 + 0.7 * np.sin(2 * np.pi * 0.15 * t + 2.0)
    shm = 0.008 * np.sin(2*np.pi*659.3*t) * shim_lfo
    shm += 0.006 * np.sin(2*np.pi*880*t) * shim_lfo
    # Layer 4: Filtered noise texture
    nz = np.random.randn(len(t)) * 0.003
    nz = np.convolve(nz, np.ones(200)/200, mode='same')
    # Mix + fade
    mix_bgm = drn + pd + shm + nz
    fade_n = 48000 * 4
    mix_bgm[:fade_n] *= np.linspace(0, 1, fade_n)
    mix_bgm[-fade_n:] *= np.linspace(1, 0, fade_n)
    mix_bgm = mix_bgm / (np.max(np.abs(mix_bgm)) + 1e-8) * 0.8
    with wave_mod.open(str(bgm_wav), 'w') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(48000)
        wf.writeframes((mix_bgm * 32767).astype(np.int16).tobytes())
    run(["ffmpeg", "-y", "-i", str(bgm_wav), "-c:a", "aac", "-b:a", "128k", str(bgm)], "encode bgm")

    # ===== 色彩分级 (暖色调微调) =====
    print("[Color] 色彩分级...")
    color_graded = OUT / "color_graded.mp4"
    run([
        "ffmpeg", "-y", "-i", str(concat_raw),
        "-vf", "colorbalance=rs=0.03:gs=0.01:bs=-0.02:rm=0.02:gm=0.01:bm=-0.01",
        "-c:v", "libx264", "-preset", "medium", "-crf", "12",
        "-profile:v", "high", "-level", "4.1", "-g", str(FPS * 10),
        "-c:a", "copy", "-pix_fmt", "yuv420p",
        str(color_graded)
    ], "color grade")
    if not color_graded.exists():
        color_graded = concat_raw

    # ===== 混音: BGM + 语音ducking (语音响时BGM自动降低) =====
    print("[Mix] BGM混音 + 语音ducking...")
    final = OUT / "final_pure_ai.mp4"
    # sidechaincompress: 当语音(input 0)响时, 自动压缩BGM音量
    run([
        "ffmpeg", "-y",
        "-i", str(color_graded), "-i", str(bgm),
        "-filter_complex",
        "[1:a]volume=0.15[bgm_raw];"
        "[bgm_raw][0:a]sidechaincompress=threshold=0.02:ratio=4:attack=200:release=1000[bgm_ducked];"
        "[0:a]volume=1.0[voice];"
        "[voice][bgm_ducked]amix=inputs=2:duration=first:normalize=0[out]",
        "-map", "0:v", "-map", "[out]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
        "-movflags", "+faststart",
        str(final)
    ], "mix bgm ducking")

    # ===== B站封面图 =====
    print("[Cover] 生成B站封面图...")
    cover = OUT / "bilibili_cover.png"
    try:
        cimg = make_gradient(W, H, (8, 15, 30), (0, 0, 0))
        cdraw = ImageDraw.Draw(cimg)
        # 大标题
        title_font = get_font(96, bold=True)
        title = "意识流编程"
        text_center_glow(cimg, cdraw, title, 280, title_font, COLORS["gold"], glow_radius=30, glow_alpha=0.5)
        cdraw = ImageDraw.Draw(cimg)
        # 副标题
        sub_font = get_font(48, bold=True)
        sub = "AI听懂你的混乱，替你写代码"
        text_center(cdraw, sub, 420, sub_font, (200, 200, 210))
        # 底部标签
        tag_font = get_font(32)
        tags = "CosyVoice语音 · 957ms打开微信 · 零代码开发"
        text_center(cdraw, tags, 560, tag_font, COLORS["cyan"])
        # 装饰线
        draw_accent_line(cdraw, 260, COLORS["gold"], width=600, thickness=2)
        draw_accent_line(cdraw, 640, COLORS["divider"], width=500, thickness=1)
        # 暗角+颗粒
        cimg_arr = np.array(cimg, dtype=np.int16)
        grain = np.random.normal(0, 4, cimg_arr.shape).astype(np.int16)
        cimg = Image.fromarray(np.clip(cimg_arr + grain, 0, 255).astype(np.uint8))
        cimg = add_vignette(cimg, strength=0.2)
        cimg.save(str(cover), quality=95)
        print(f"  [OK] bilibili_cover.png")
    except Exception as e:
        print(f"  [FAIL] cover failed: {e}")

    elapsed = time.time() - t0
    print("\n" + "=" * 60)
    tts_label = "CosyVoice" if COSYVOICE_KEY else "edge-tts"
    print(f"完成! TTS={tts_label}, 耗时 {elapsed:.0f}s ({elapsed/60:.1f}min)")
    for name, ok in results:
        status = "[OK]" if ok else "[FAIL]"
        print(f"  {status} {name}.mp4")
    if final.exists():
        d = get_duration(final)
        sz = final.stat().st_size / 1024 / 1024
        print(f"\n  >> final_pure_ai.mp4: {d:.0f}s ({d/60:.1f}min), {sz:.1f}MB")
    if cover.exists():
        print(f"  >> bilibili_cover.png (cover)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
