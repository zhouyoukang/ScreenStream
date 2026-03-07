"""Generate a synthetic dancing stick figure video for hip sync testing.
Uses only numpy + cv2 (opencv-python). Creates a 15s video with a figure
that moves hips up/down and twists left/right rhythmically.
"""
import numpy as np
import cv2
import math
from pathlib import Path

OUT = Path(__file__).parent / "douyin_cache"
OUT.mkdir(exist_ok=True)
OUT_FILE = str(OUT / "dance_test.mp4")

W, H = 640, 480
FPS = 30
DURATION = 15  # seconds
TOTAL_FRAMES = FPS * DURATION
BPM = 120
BEAT_PERIOD = 60.0 / BPM  # seconds per beat

# Stick figure keypoints (normalized 0-1, will be scaled)
# Format: (x, y) base position
BASE = {
    "head":        (0.5, 0.18),
    "neck":        (0.5, 0.25),
    "l_shoulder":  (0.38, 0.28),
    "r_shoulder":  (0.62, 0.28),
    "l_elbow":     (0.30, 0.38),
    "r_elbow":     (0.70, 0.38),
    "l_wrist":     (0.28, 0.48),
    "r_wrist":     (0.72, 0.48),
    "l_hip":       (0.44, 0.52),
    "r_hip":       (0.56, 0.52),
    "l_knee":      (0.42, 0.70),
    "r_knee":      (0.58, 0.70),
    "l_ankle":     (0.40, 0.88),
    "r_ankle":     (0.60, 0.88),
}

BONES = [
    ("head", "neck"),
    ("neck", "l_shoulder"), ("neck", "r_shoulder"),
    ("l_shoulder", "l_elbow"), ("l_elbow", "l_wrist"),
    ("r_shoulder", "r_elbow"), ("r_elbow", "r_wrist"),
    ("neck", "l_hip"), ("neck", "r_hip"),
    ("l_hip", "r_hip"),
    ("l_hip", "l_knee"), ("l_knee", "l_ankle"),
    ("r_hip", "r_knee"), ("r_knee", "r_ankle"),
]

HIP_COLOR = (0, 140, 255)  # orange
BONE_COLOR = (255, 255, 0)  # cyan
JOINT_COLOR = (0, 255, 255)  # yellow

def animate_keypoints(t):
    """Generate animated keypoints at time t (seconds)"""
    kps = {k: list(v) for k, v in BASE.items()}
    
    phase = 2 * math.pi * t / BEAT_PERIOD
    
    # Hip vertical bounce (main movement)
    hip_bounce = math.sin(phase) * 0.06
    kps["l_hip"][1] += hip_bounce
    kps["r_hip"][1] += hip_bounce
    # Propagate to knees/ankles
    kps["l_knee"][1] += hip_bounce * 0.7
    kps["r_knee"][1] += hip_bounce * 0.7
    kps["l_ankle"][1] += hip_bounce * 0.4
    kps["r_ankle"][1] += hip_bounce * 0.4
    
    # Hip twist (rotation)
    twist = math.sin(phase * 0.5) * 0.04
    kps["l_hip"][0] += twist
    kps["r_hip"][0] -= twist
    kps["l_knee"][0] += twist * 0.5
    kps["r_knee"][0] -= twist * 0.5
    
    # Hip sway (left-right)
    sway = math.sin(phase * 0.75 + 1.0) * 0.03
    for part in ["l_hip", "r_hip", "l_knee", "r_knee", "l_ankle", "r_ankle"]:
        kps[part][0] += sway
    
    # Arm swing
    arm_swing = math.sin(phase + 0.5) * 0.05
    kps["l_elbow"][1] += arm_swing
    kps["r_elbow"][1] -= arm_swing
    kps["l_wrist"][1] += arm_swing * 1.5
    kps["r_wrist"][1] -= arm_swing * 1.5
    kps["l_wrist"][0] -= abs(arm_swing) * 0.5
    kps["r_wrist"][0] += abs(arm_swing) * 0.5
    
    # Upper body slight movement
    body_sway = math.sin(phase * 0.5) * 0.015
    for part in ["head", "neck", "l_shoulder", "r_shoulder"]:
        kps[part][0] += body_sway
        kps[part][1] += math.sin(phase) * 0.02
    
    return kps

def draw_figure(frame, kps):
    """Draw stick figure on frame"""
    # Scale to pixel coords
    pts = {k: (int(v[0] * W), int(v[1] * H)) for k, v in kps.items()}
    
    # Draw bones
    for a, b in BONES:
        is_hip = "hip" in a or "hip" in b
        color = HIP_COLOR if is_hip else BONE_COLOR
        thickness = 4 if is_hip else 2
        cv2.line(frame, pts[a], pts[b], color, thickness, cv2.LINE_AA)
    
    # Draw joints
    for name, pt in pts.items():
        is_hip = "hip" in name
        r = 8 if is_hip else 5
        color = HIP_COLOR if is_hip else JOINT_COLOR
        cv2.circle(frame, pt, r, color, -1, cv2.LINE_AA)
        if is_hip:
            cv2.circle(frame, pt, r+3, (255, 255, 255), 2, cv2.LINE_AA)
    
    # Draw hip center cross
    hc = ((pts["l_hip"][0] + pts["r_hip"][0])//2, (pts["l_hip"][1] + pts["r_hip"][1])//2)
    cv2.drawMarker(frame, hc, (0, 255, 0), cv2.MARKER_CROSS, 20, 2)
    
    # Head circle
    cv2.circle(frame, pts["head"], 18, JOINT_COLOR, 2, cv2.LINE_AA)
    
    return frame

def main():
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(OUT_FILE, fourcc, FPS, (W, H))
    
    print(f"Generating {DURATION}s dance video at {BPM}BPM...")
    for i in range(TOTAL_FRAMES):
        t = i / FPS
        frame = np.zeros((H, W, 3), dtype=np.uint8)
        
        # Dark gradient background
        for y in range(H):
            v = int(20 + 15 * y / H)
            frame[y, :] = (v, v, v+5)
        
        # Animate and draw
        kps = animate_keypoints(t)
        draw_figure(frame, kps)
        
        # HUD
        beat_num = int(t / BEAT_PERIOD) + 1
        phase_pct = (t % BEAT_PERIOD) / BEAT_PERIOD * 100
        hip_y = (kps["l_hip"][1] + kps["r_hip"][1]) / 2
        twist_angle = math.degrees(math.atan2(
            kps["r_hip"][1] - kps["l_hip"][1],
            kps["r_hip"][0] - kps["l_hip"][0]
        ))
        
        cv2.putText(frame, f"Beat #{beat_num} ({phase_pct:.0f}%)", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)
        cv2.putText(frame, f"Hip Y: {hip_y:.3f} | Twist: {twist_angle:.1f}deg", (10, 45),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)
        cv2.putText(frame, f"t={t:.1f}s / {DURATION}s", (W-150, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (80, 80, 80), 1)
        
        writer.write(frame)
    
    writer.release()
    size_kb = Path(OUT_FILE).stat().st_size // 1024
    print(f"Done: {OUT_FILE} ({size_kb}KB, {W}x{H}, {FPS}fps, {DURATION}s)")

if __name__ == "__main__":
    main()
