#!/usr/bin/env python3
"""
ModelForge Toolkit — OpenSCAD渲染/验证/预览工具

AI推理由 Cascade Agent 完成，本脚本只做机械操作。

命令:
  python forge.py check                          # 环境检查
  python forge.py render  <scad> [<stl>]         # 渲染STL
  python forge.py validate <stl>                  # 几何验证
  python forge.py preview <scad> <output_dir>     # 多角度预览PNG
  python forge.py info <stl>                      # STL信息
"""

import json
import math
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ================================================================
# Configuration
# ================================================================

OPENSCAD_SEARCH = [
    r"D:\openscad\openscad.com",
    r"D:\openscad\openscad.exe",
    r"C:\Program Files\OpenSCAD\openscad.exe",
    r"C:\Program Files (x86)\OpenSCAD\openscad.exe",
    "/usr/bin/openscad",
    "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD",
]

RENDER_FN = 64
PREVIEW_SIZE = "1200,900"
RENDER_TIMEOUT = 300

CAMERAS = {
    "front": "0,0,0,0,0,0",
    "right": "0,0,0,0,0,90",
    "top":   "0,0,0,90,0,0",
    "iso":   "0,0,0,55,0,25",
}

# Manufacturing defaults (FDM)
FDM_MIN_WALL = 1.2        # mm
FDM_MAX_OVERHANG = 45     # degrees from vertical
FDM_MIN_BRIDGE = 5        # mm max unsupported span
FDM_LAYER_HEIGHT = 0.2    # mm typical
FDM_NOZZLE = 0.4          # mm typical
THICKNESS_SAMPLES = 500   # ray-cast samples for wall thickness


def find_openscad():
    env = os.getenv("OPENSCAD_PATH")
    if env and Path(env).exists():
        return env
    for p in OPENSCAD_SEARCH:
        if Path(p).exists():
            return p
    return shutil.which("openscad") or shutil.which("openscad.com")

# ================================================================
# Commands
# ================================================================

def cmd_check():
    """Verify environment."""
    print("ModelForge Environment Check\n")
    ok = True

    scad = find_openscad()
    if scad:
        try:
            r = subprocess.run([scad, "--version"], capture_output=True, text=True, timeout=10)
            ver = (r.stdout.strip() or r.stderr.strip()).split("\n")[0]
            print(f"  OK  OpenSCAD: {ver}")
        except Exception:
            print(f"  OK  OpenSCAD: {scad}")
    else:
        print("  FAIL  OpenSCAD: NOT FOUND")
        ok = False

    for pkg in ["trimesh", "numpy"]:
        try:
            m = __import__(pkg)
            print(f"  OK  {pkg}: {getattr(m, '__version__', '?')}")
        except ImportError:
            label = "WARN" if pkg == "trimesh" else "FAIL"
            print(f"  {label}  {pkg}: not installed")
            if pkg != "trimesh":
                ok = False

    print()
    print("Ready!" if ok else "Fix issues above.")
    return 0 if ok else 1


def cmd_render(scad_path, stl_path=None, fn=None):
    """Render .scad → .stl. Returns JSON result to stdout."""
    scad_path = Path(scad_path)
    if not scad_path.exists():
        return _fail(f"File not found: {scad_path}")

    if stl_path is None:
        stl_path = scad_path.with_suffix(".stl")
    else:
        stl_path = Path(stl_path)

    openscad = find_openscad()
    if not openscad:
        return _fail("OpenSCAD not found")

    quality = fn or RENDER_FN
    cmd = [openscad, "-o", str(stl_path), "-D", f"$fn={quality}", str(scad_path)]

    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=RENDER_TIMEOUT)
    except subprocess.TimeoutExpired:
        return _result(False, 0, f"TIMEOUT after {RENDER_TIMEOUT}s", time.time() - t0)

    dt = time.time() - t0
    success = stl_path.exists() and stl_path.stat().st_size > 0
    size = stl_path.stat().st_size if success else 0

    return _result(success, size, r.stderr, dt)


def cmd_validate(stl_path):
    """Validate STL geometry. Returns JSON with issues list."""
    stl_path = Path(stl_path)
    if not stl_path.exists():
        return _fail(f"File not found: {stl_path}")

    issues = []
    info = {}

    sz = stl_path.stat().st_size
    info["file_size"] = sz
    if sz < 500:
        issues.append(f"STL too small ({sz} bytes)")

    try:
        import trimesh
        mesh = trimesh.load(str(stl_path))

        info["vertices"] = len(mesh.vertices)
        info["faces"] = len(mesh.faces)
        info["volume_mm3"] = round(float(mesh.volume), 2)
        info["is_watertight"] = bool(mesh.is_watertight)
        bounds = mesh.bounding_box.extents
        info["bounds_mm"] = [round(float(b), 2) for b in bounds]

        if hasattr(mesh, "is_volume") and not mesh.is_volume:
            issues.append("Mesh not watertight (not manifold)")
        if any(d > 500 for d in bounds):
            issues.append(f"Too large: {bounds[0]:.0f}x{bounds[1]:.0f}x{bounds[2]:.0f}mm")
        if all(d < 1.0 for d in bounds):
            issues.append(f"Too small: {bounds[0]:.1f}x{bounds[1]:.1f}x{bounds[2]:.1f}mm")
        if mesh.volume < 1.0:
            issues.append(f"Volume too small: {mesh.volume:.2f}mm3")

    except ImportError:
        issues.append("trimesh not installed, geometry checks skipped")
    except Exception as e:
        issues.append(f"Validation error: {e}")

    result = {"valid": len(issues) == 0, "issues": issues, "info": info}
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 1


def cmd_preview(scad_path, output_dir):
    """Render multi-angle preview PNGs."""
    scad_path = Path(scad_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    openscad = find_openscad()
    if not openscad:
        return _fail("OpenSCAD not found")

    results = []
    for name, cam in CAMERAS.items():
        png = output_dir / f"preview_{name}.png"
        cmd = [
            openscad, "-o", str(png),
            "--imgsize", PREVIEW_SIZE,
            "--camera", cam,
            "--viewall", "--autocenter",
            "--colorscheme", "Tomorrow Night",
            "-D", f"$fn={RENDER_FN}",
            str(scad_path),
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=120)
            if png.exists() and png.stat().st_size > 100:
                results.append(str(png))
        except Exception:
            pass

    print(json.dumps({"previews": results, "count": len(results)}))
    return 0


# ================================================================
# New Commands: Project Management + Comparison + Manufacturing
# ================================================================

def cmd_init(project_name, base_dir=None):
    """Initialize a project directory for a modeling job."""
    base = Path(base_dir) if base_dir else Path("projects")
    proj = base / project_name
    if proj.exists():
        return _fail(f"Project already exists: {proj}")

    for d in ["reference", "parts", "output", "iterations"]:
        (proj / d).mkdir(parents=True, exist_ok=True)

    # Empty iteration log
    log_path = proj / "iteration_log.json"
    log_path.write_text(json.dumps({"project": project_name, "created": _now(), "iterations": []}, indent=2), encoding="utf-8")

    # Assembly template
    asm = proj / "assembly.scad"
    asm.write_text(f"""// ============================================================\n// {project_name} — Assembly\n// Generated by ModelForge\n// ============================================================\n\n/* [Render] */\nquality = 64;  // [16:8:128]\nexplode = 0;   // [0:5:100] Explode distance for assembly view\n\n// Include sub-parts from parts/ directory\n// use <parts/part_name.scad>\n\n// Assembly\n// part_a();\n// translate([explode, 0, 0]) part_b();\n""", encoding="utf-8")

    print(json.dumps({"success": True, "project_dir": str(proj), "structure": ["reference/", "parts/", "output/", "iterations/", "assembly.scad", "iteration_log.json"]}))
    return 0


def cmd_compare(reference_img, rendered_img, output_path, iteration=None):
    """Generate side-by-side comparison image (reference vs rendered)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return _fail("Pillow not installed: pip install Pillow")

    ref_path = Path(reference_img)
    ren_path = Path(rendered_img)
    if not ref_path.exists():
        return _fail(f"Reference not found: {ref_path}")
    if not ren_path.exists():
        return _fail(f"Rendered not found: {ren_path}")

    ref = Image.open(ref_path).convert("RGB")
    ren = Image.open(ren_path).convert("RGB")

    # Normalize heights
    target_h = max(ref.height, ren.height, 600)
    ref = _resize_to_height(ref, target_h)
    ren = _resize_to_height(ren, target_h)

    # Compose: [label bar] + [reference | divider | rendered]
    bar_h = 40
    divider_w = 4
    canvas_w = ref.width + divider_w + ren.width
    canvas_h = target_h + bar_h
    canvas = Image.new("RGB", (canvas_w, canvas_h), (30, 30, 30))

    # Paste images
    canvas.paste(ref, (0, bar_h))
    canvas.paste(ren, (ref.width + divider_w, bar_h))

    # Draw labels
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except Exception:
        font = ImageFont.load_default()

    iter_label = f"  Iteration {iteration}" if iteration else ""
    draw.text((10, 8), f"REFERENCE", fill=(100, 200, 255), font=font)
    draw.text((ref.width + divider_w + 10, 8), f"RENDERED{iter_label}", fill=(100, 255, 100), font=font)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    draw.text((canvas_w - 200, 8), ts, fill=(150, 150, 150), font=font)

    # Divider line
    draw.rectangle([ref.width, bar_h, ref.width + divider_w, canvas_h], fill=(255, 100, 0))

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(str(out))

    print(json.dumps({"success": True, "output": str(out), "size": [canvas_w, canvas_h], "iteration": iteration}))
    return 0


def cmd_manufacture(stl_path, tech="fdm"):
    """Analyze STL for 3D printing manufacturability. Returns JSON report."""
    stl_path = Path(stl_path)
    if not stl_path.exists():
        return _fail(f"File not found: {stl_path}")

    try:
        import trimesh
        import numpy as np
    except ImportError:
        return _fail("trimesh/numpy not installed")

    try:
        mesh = trimesh.load(str(stl_path))
    except Exception as e:
        return _fail(f"Cannot load STL: {e}")

    report = {"file": str(stl_path), "technology": tech, "timestamp": _now()}
    issues = []
    warnings = []

    # --- Basic geometry ---
    bounds = mesh.bounding_box.extents
    report["bounds_mm"] = [round(float(b), 2) for b in bounds]
    report["volume_mm3"] = round(float(mesh.volume), 2)
    report["surface_area_mm2"] = round(float(mesh.area), 2)
    report["faces"] = len(mesh.faces)
    report["is_watertight"] = bool(mesh.is_watertight)
    report["is_manifold"] = bool(getattr(mesh, 'is_volume', mesh.is_watertight))

    if not report["is_watertight"]:
        issues.append("Mesh is not watertight — cannot slice for printing")
    if not report["is_manifold"]:
        issues.append("Mesh is not manifold — self-intersections or holes")

    # --- Bounding box sanity ---
    bbox_vol = float(np.prod(bounds))
    fill_ratio = float(mesh.volume) / bbox_vol if bbox_vol > 0 else 0
    report["fill_ratio"] = round(fill_ratio, 3)
    if any(d > 300 for d in bounds):
        warnings.append(f"Large model: {bounds[0]:.0f}x{bounds[1]:.0f}x{bounds[2]:.0f}mm — check print bed size")
    if any(d < 2 for d in bounds):
        issues.append(f"Tiny dimension detected: min axis = {min(bounds):.1f}mm")

    # --- Wall thickness (ray-based sampling) ---
    thickness_stats = _analyze_wall_thickness(mesh, THICKNESS_SAMPLES)
    report["wall_thickness"] = thickness_stats
    min_wall = FDM_MIN_WALL if tech == "fdm" else 0.5
    if thickness_stats["min"] < min_wall:
        issues.append(f"Wall too thin: {thickness_stats['min']:.2f}mm < {min_wall}mm minimum")
    if thickness_stats["pct_below_min"] > 10:
        warnings.append(f"{thickness_stats['pct_below_min']:.0f}% of sampled points below {min_wall}mm wall thickness")

    # --- Overhang analysis ---
    overhang_stats = _analyze_overhangs(mesh, FDM_MAX_OVERHANG if tech == "fdm" else 90)
    report["overhangs"] = overhang_stats
    if tech == "fdm" and overhang_stats["pct_area"] > 20:
        warnings.append(f"{overhang_stats['pct_area']:.0f}% surface area is overhang (>{FDM_MAX_OVERHANG}°) — needs supports")
    if tech == "fdm" and overhang_stats["pct_area"] > 50:
        issues.append(f"Excessive overhangs: {overhang_stats['pct_area']:.0f}% — redesign recommended")

    # --- Print bed contact ---
    bed_stats = _analyze_bed_contact(mesh)
    report["bed_contact"] = bed_stats
    if bed_stats["area_mm2"] < 25:
        warnings.append(f"Small bed contact: {bed_stats['area_mm2']:.1f}mm² — adhesion may fail")
    if not bed_stats["is_flat"]:
        warnings.append("No flat bottom surface detected — may need brim/raft")

    # --- Printability score ---
    score = 100
    score -= len(issues) * 20
    score -= len(warnings) * 5
    if not report["is_watertight"]:
        score -= 30
    if thickness_stats["pct_below_min"] > 0:
        score -= min(20, thickness_stats["pct_below_min"])
    if overhang_stats["pct_area"] > 20:
        score -= min(15, (overhang_stats["pct_area"] - 20) / 2)
    report["printability_score"] = max(0, min(100, round(score)))

    report["issues"] = issues
    report["warnings"] = warnings
    report["print_ready"] = len(issues) == 0

    print(json.dumps(report, indent=2))
    return 0 if report["print_ready"] else 1


def cmd_log(project_dir, data_json):
    """Append iteration data to project's iteration_log.json."""
    proj = Path(project_dir)
    log_path = proj / "iteration_log.json"
    if not log_path.exists():
        return _fail(f"No iteration_log.json in {proj}")

    try:
        data = json.loads(data_json)
    except json.JSONDecodeError as e:
        return _fail(f"Invalid JSON: {e}")

    log = json.loads(log_path.read_text(encoding="utf-8"))
    iteration_num = len(log["iterations"]) + 1
    data["iteration"] = iteration_num
    data["timestamp"] = _now()
    log["iterations"].append(data)
    log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")

    print(json.dumps({"success": True, "iteration": iteration_num}))
    return 0


def cmd_report(project_dir):
    """Generate markdown iteration report from iteration_log.json."""
    proj = Path(project_dir)
    log_path = proj / "iteration_log.json"
    if not log_path.exists():
        return _fail(f"No iteration_log.json in {proj}")

    log = json.loads(log_path.read_text(encoding="utf-8"))
    project = log.get("project", "Unknown")
    iters = log.get("iterations", [])

    lines = [
        f"# {project} — Iteration Report",
        f"",
        f"> Generated by ModelForge on {_now()}",
        f"> Total iterations: {len(iters)}",
        f"",
    ]

    for it in iters:
        n = it.get("iteration", "?")
        ts = it.get("timestamp", "")
        lines.append(f"## Iteration {n} ({ts})")
        lines.append("")

        if "deviations" in it:
            lines.append("### Deviations")
            for d in it["deviations"]:
                lines.append(f"- {d}")
            lines.append("")

        if "fixes" in it:
            lines.append("### Fixes Applied")
            for f in it["fixes"]:
                lines.append(f"- {f}")
            lines.append("")

        if "metrics" in it:
            lines.append("### Metrics")
            for k, v in it["metrics"].items():
                lines.append(f"- **{k}**: {v}")
            lines.append("")

        if "verdict" in it:
            lines.append(f"**Verdict**: {it['verdict']}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Summary
    if iters:
        last = iters[-1]
        lines.append("## Convergence Summary")
        lines.append("")
        converged = last.get("converged", False)
        lines.append(f"- **Converged**: {'Yes ✅' if converged else 'No ❌'}")
        lines.append(f"- **Total iterations**: {len(iters)}")
        if "metrics" in last:
            lines.append(f"- **Final metrics**: {json.dumps(last['metrics'])}")
        lines.append("")

    report_text = "\n".join(lines)
    report_path = proj / "report.md"
    report_path.write_text(report_text, encoding="utf-8")

    print(json.dumps({"success": True, "report": str(report_path), "iterations": len(iters)}))
    return 0


# ================================================================
# Manufacturing Analysis Helpers
# ================================================================

def _analyze_wall_thickness(mesh, n_samples):
    """Estimate wall thickness via inward ray casting."""
    import numpy as np
    try:
        # Sample face centroids
        n = min(n_samples, len(mesh.faces))
        indices = np.random.choice(len(mesh.faces), size=n, replace=False)
        origins = mesh.triangles_center[indices]
        normals = mesh.face_normals[indices]

        # Cast rays inward (opposite of face normal)
        ray_dirs = -normals
        # Offset origins slightly inward to avoid self-intersection
        origins_offset = origins + ray_dirs * 0.01

        locations, index_ray, index_tri = mesh.ray.intersects_location(
            ray_origins=origins_offset, ray_directions=ray_dirs
        )

        if len(locations) == 0:
            return {"min": 0, "max": 0, "mean": 0, "median": 0, "pct_below_min": 100, "samples": n}

        # Compute distances
        thicknesses = []
        for i in range(n):
            hits = locations[index_ray == i]
            if len(hits) > 0:
                dists = np.linalg.norm(hits - origins_offset[i], axis=1)
                # Take the first hit (closest) as wall thickness
                thicknesses.append(float(np.min(dists)))

        if not thicknesses:
            return {"min": 0, "max": 0, "mean": 0, "median": 0, "pct_below_min": 100, "samples": n}

        arr = np.array(thicknesses)
        min_wall = FDM_MIN_WALL
        pct_below = float(np.sum(arr < min_wall) / len(arr) * 100)

        return {
            "min": round(float(np.min(arr)), 2),
            "max": round(float(np.max(arr)), 2),
            "mean": round(float(np.mean(arr)), 2),
            "median": round(float(np.median(arr)), 2),
            "pct_below_min": round(pct_below, 1),
            "samples": len(thicknesses),
        }
    except Exception as e:
        return {"error": str(e), "min": 0, "max": 0, "mean": 0, "median": 0, "pct_below_min": 0, "samples": 0}


def _analyze_overhangs(mesh, max_angle_deg):
    """Analyze overhang faces (angle from build direction Z-up)."""
    import numpy as np
    try:
        normals = mesh.face_normals
        # Angle between face normal and -Z (downward = worst overhang)
        # Overhang = face normal has negative Z component
        # The angle from vertical: acos(abs(normal.z))
        z_component = normals[:, 2]

        # Faces pointing downward have z < 0
        # Overhang angle from vertical = acos(-z) for downward faces
        # We define overhang as: angle from horizontal > max_angle
        # Equivalently: the face normal points below the threshold
        threshold_rad = math.radians(90 - max_angle_deg)  # from vertical
        overhang_mask = z_component < -math.cos(math.radians(max_angle_deg))

        face_areas = mesh.area_faces
        total_area = float(np.sum(face_areas))
        overhang_area = float(np.sum(face_areas[overhang_mask]))

        pct = (overhang_area / total_area * 100) if total_area > 0 else 0

        return {
            "overhang_faces": int(np.sum(overhang_mask)),
            "total_faces": len(mesh.faces),
            "overhang_area_mm2": round(overhang_area, 2),
            "pct_area": round(pct, 1),
            "threshold_deg": max_angle_deg,
        }
    except Exception as e:
        return {"error": str(e), "overhang_faces": 0, "pct_area": 0, "threshold_deg": max_angle_deg}


def _analyze_bed_contact(mesh):
    """Analyze print bed contact (bottom surface)."""
    import numpy as np
    try:
        z_min = float(mesh.bounds[0][2])
        tolerance = 0.1  # mm

        # Find faces near z_min with upward-facing normals (sitting on bed)
        centroids = mesh.triangles_center
        normals = mesh.face_normals
        face_areas = mesh.area_faces

        near_bottom = centroids[:, 2] < (z_min + tolerance)
        facing_down = normals[:, 2] < -0.9  # nearly flat bottom
        contact_mask = near_bottom & facing_down

        contact_area = float(np.sum(face_areas[contact_mask]))
        is_flat = contact_area > 10  # at least 10mm² flat bottom

        return {
            "area_mm2": round(contact_area, 2),
            "is_flat": is_flat,
            "z_min_mm": round(z_min, 2),
            "contact_faces": int(np.sum(contact_mask)),
        }
    except Exception as e:
        return {"error": str(e), "area_mm2": 0, "is_flat": False, "z_min_mm": 0}


def _resize_to_height(img, target_h):
    """Resize PIL image to target height preserving aspect ratio."""
    ratio = target_h / img.height
    new_w = int(img.width * ratio)
    return img.resize((new_w, target_h))


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def cmd_info(stl_path):
    """Print STL mesh info as JSON."""
    stl_path = Path(stl_path)
    if not stl_path.exists():
        return _fail(f"File not found: {stl_path}")

    info = {"file": str(stl_path), "size_bytes": stl_path.stat().st_size}

    try:
        import trimesh
        mesh = trimesh.load(str(stl_path))
        info["vertices"] = len(mesh.vertices)
        info["faces"] = len(mesh.faces)
        info["volume_mm3"] = round(float(mesh.volume), 2)
        info["is_watertight"] = bool(mesh.is_watertight)
        bounds = mesh.bounding_box.extents
        info["bounds_mm"] = [round(float(b), 2) for b in bounds]
        center = mesh.centroid
        info["centroid_mm"] = [round(float(c), 2) for c in center]
    except ImportError:
        info["error"] = "trimesh not installed"
    except Exception as e:
        info["error"] = str(e)

    print(json.dumps(info, indent=2))
    return 0

# ================================================================
# Helpers
# ================================================================

def _fail(msg):
    print(json.dumps({"success": False, "error": msg}))
    return 1


def _result(success, size, stderr, dt):
    # Parse errors/warnings from OpenSCAD stderr
    errors = []
    warnings = []
    for line in (stderr or "").splitlines():
        lt = line.strip()
        if not lt:
            continue
        if "ERROR" in lt.upper():
            errors.append(lt)
        elif "WARNING" in lt and "deprecated" not in lt.lower() and "Ignoring" not in lt:
            warnings.append(lt)

    out = {
        "success": success,
        "stl_size": size,
        "seconds": round(dt, 2),
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(out, indent=2))
    return 0 if success else 1

# ================================================================
# CLI
# ================================================================

USAGE = """ModelForge Toolkit — AI推理由Cascade Agent完成，本脚本做渲染/验证/预览/对比/制造分析

Core Commands:
  python forge.py check                              环境检查
  python forge.py render  <scad> [<stl>] [--fn N]     渲染STL
  python forge.py validate <stl>                      几何验证(JSON)
  python forge.py preview <scad> <output_dir>         4视角PNG
  python forge.py info <stl>                          STL网格信息(JSON)

Autonomous Loop Commands:
  python forge.py init <project_name> [<base_dir>]    创建项目目录结构
  python forge.py compare <ref> <rendered> <out> [--iter N]  参考图vs渲染图对比
  python forge.py manufacture <stl> [--tech fdm|sla]  制造性分析(JSON)
  python forge.py log <project_dir> '<json>'          记录迭代数据
  python forge.py report <project_dir>                生成迭代报告(Markdown)
"""

def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(USAGE)
        return 0

    cmd = args[0].lower()

    if cmd == "check":
        return cmd_check()

    elif cmd == "render":
        if len(args) < 2:
            print("Usage: forge.py render <scad> [<stl>] [--fn N]")
            return 1
        scad = args[1]
        stl = args[2] if len(args) > 2 and not args[2].startswith("-") else None
        fn = None
        if "--fn" in args:
            idx = args.index("--fn")
            fn = int(args[idx + 1]) if idx + 1 < len(args) else RENDER_FN
        return cmd_render(scad, stl, fn)

    elif cmd == "validate":
        if len(args) < 2:
            print("Usage: forge.py validate <stl>")
            return 1
        return cmd_validate(args[1])

    elif cmd == "preview":
        if len(args) < 3:
            print("Usage: forge.py preview <scad> <output_dir>")
            return 1
        return cmd_preview(args[1], args[2])

    elif cmd == "info":
        if len(args) < 2:
            print("Usage: forge.py info <stl>")
            return 1
        return cmd_info(args[1])

    elif cmd == "init":
        if len(args) < 2:
            print("Usage: forge.py init <project_name> [<base_dir>]")
            return 1
        return cmd_init(args[1], args[2] if len(args) > 2 else None)

    elif cmd == "compare":
        if len(args) < 4:
            print("Usage: forge.py compare <reference> <rendered> <output> [--iter N]")
            return 1
        iteration = None
        if "--iter" in args:
            idx = args.index("--iter")
            iteration = int(args[idx + 1]) if idx + 1 < len(args) else None
        return cmd_compare(args[1], args[2], args[3], iteration)

    elif cmd == "manufacture":
        if len(args) < 2:
            print("Usage: forge.py manufacture <stl> [--tech fdm|sla]")
            return 1
        tech = "fdm"
        if "--tech" in args:
            idx = args.index("--tech")
            tech = args[idx + 1] if idx + 1 < len(args) else "fdm"
        return cmd_manufacture(args[1], tech)

    elif cmd == "log":
        if len(args) < 3:
            print("Usage: forge.py log <project_dir> '<json_data>'")
            return 1
        return cmd_log(args[1], args[2])

    elif cmd == "report":
        if len(args) < 2:
            print("Usage: forge.py report <project_dir>")
            return 1
        return cmd_report(args[1])

    else:
        print(f"Unknown command: {cmd}")
        print(USAGE)
        return 1


if __name__ == "__main__":
    sys.exit(main())
