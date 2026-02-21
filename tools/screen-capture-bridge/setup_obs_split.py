"""
OBS 分段录制配置工具
- 将OBS从Simple模式切换到Advanced模式
- 启用自动分段录制（按时间/大小）
- 确保分段文件可被AI实时处理

⚠️ 必须在OBS未录制时运行！
"""
import configparser
import shutil
import sys
from pathlib import Path
from datetime import datetime

OBS_PROFILE_DIR = Path.home() / "AppData/Roaming/obs-studio/basic/profiles"

def find_profiles():
    """查找所有OBS配置文件"""
    profiles = []
    if OBS_PROFILE_DIR.exists():
        for p in OBS_PROFILE_DIR.iterdir():
            ini = p / "basic.ini"
            if ini.exists():
                profiles.append((p.name, ini))
    return profiles

def backup_config(ini_path: Path):
    """备份原始配置"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = ini_path.parent / f"basic.ini.backup_{ts}"
    shutil.copy2(ini_path, backup)
    print(f"✅ 已备份: {backup}")
    return backup

def configure_split(ini_path: Path, split_minutes: int = 5, split_size_mb: int = 2048):
    """
    配置OBS分段录制
    
    Args:
        ini_path: basic.ini路径
        split_minutes: 每段时长(分钟)，默认5分钟
        split_size_mb: 每段大小上限(MB)，默认2GB
    """
    config = configparser.RawConfigParser()
    config.optionxform = str  # 保持大小写
    config.read(str(ini_path), encoding='utf-8-sig')
    
    # 读取当前SimpleOutput的关键设置，迁移到AdvOut
    simple_path = config.get('SimpleOutput', 'FilePath', fallback='D:/屏幕录制')
    simple_format = config.get('SimpleOutput', 'RecFormat2', fallback='mkv')
    simple_encoder = config.get('SimpleOutput', 'RecEncoder', fallback='x264')
    simple_vbitrate = config.get('SimpleOutput', 'VBitrate', fallback='2500')
    simple_abitrate = config.get('SimpleOutput', 'ABitrate', fallback='160')
    
    # 1. 切换到Advanced模式
    current_mode = config.get('Output', 'Mode', fallback='Simple')
    config.set('Output', 'Mode', 'Advanced')
    print(f"📝 输出模式: {current_mode} → Advanced")
    
    # 2. 配置AdvOut录制参数（继承Simple模式的设置）
    if not config.has_section('AdvOut'):
        config.add_section('AdvOut')
    
    config.set('AdvOut', 'RecType', 'Standard')
    config.set('AdvOut', 'RecFilePath', simple_path.replace('/', '\\\\'))
    config.set('AdvOut', 'RecFormat2', simple_format)
    config.set('AdvOut', 'RecEncoder', 'obs_x264')
    config.set('AdvOut', 'RecTracks', '1')
    config.set('AdvOut', 'RecUseRescale', 'false')
    
    # 3. 启用自动分段
    config.set('AdvOut', 'RecSplitFile', 'true')
    config.set('AdvOut', 'RecSplitFileType', 'Time')
    config.set('AdvOut', 'RecSplitFileTime', str(split_minutes))
    config.set('AdvOut', 'RecSplitFileSize', str(split_size_mb))
    config.set('AdvOut', 'RecSplitFileResetTimestamps', 'true')
    
    # 4. 编码器设置
    config.set('AdvOut', 'Track1Bitrate', simple_abitrate)
    config.set('AdvOut', 'AudioEncoder', 'ffmpeg_aac')
    config.set('AdvOut', 'RecAudioEncoder', 'ffmpeg_aac')
    
    print(f"📂 录制目录: {simple_path}")
    print(f"🎬 录制格式: {simple_format}")
    print(f"✂️  自动分段: 每 {split_minutes} 分钟")
    print(f"📏 大小上限: {split_size_mb} MB/段")
    
    # 写回配置
    with open(str(ini_path), 'w', encoding='utf-8') as f:
        config.write(f, space_around_delimiters=False)
    
    print(f"\n✅ 配置已写入: {ini_path}")
    print("⚠️  请重启OBS使配置生效")

def show_current_config(ini_path: Path):
    """显示当前录制相关配置"""
    config = configparser.RawConfigParser()
    config.optionxform = str
    config.read(str(ini_path), encoding='utf-8-sig')
    
    mode = config.get('Output', 'Mode', fallback='?')
    print(f"\n{'='*50}")
    print(f"当前OBS配置 ({ini_path.parent.name})")
    print(f"{'='*50}")
    print(f"输出模式: {mode}")
    
    if mode == 'Simple':
        section = 'SimpleOutput'
        print(f"录制目录: {config.get(section, 'FilePath', fallback='?')}")
        print(f"录制格式: {config.get(section, 'RecFormat2', fallback='?')}")
        print(f"编码器:   {config.get(section, 'RecEncoder', fallback='?')}")
        print(f"视频码率: {config.get(section, 'VBitrate', fallback='?')} kbps")
        print(f"分段录制: ❌ Simple模式不支持自动分段")
    else:
        section = 'AdvOut'
        print(f"录制目录: {config.get(section, 'RecFilePath', fallback='?')}")
        print(f"录制格式: {config.get(section, 'RecFormat2', fallback='?')}")
        print(f"编码器:   {config.get(section, 'RecEncoder', fallback='?')}")
        split = config.get(section, 'RecSplitFile', fallback='false')
        if split == 'true':
            stype = config.get(section, 'RecSplitFileType', fallback='?')
            stime = config.get(section, 'RecSplitFileTime', fallback='?')
            ssize = config.get(section, 'RecSplitFileSize', fallback='?')
            print(f"分段录制: ✅ 已启用")
            print(f"分段方式: {stype} (每{stime}分钟 / {ssize}MB)")
        else:
            print(f"分段录制: ❌ 未启用")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='OBS分段录制配置工具')
    parser.add_argument('--show', action='store_true', help='仅显示当前配置')
    parser.add_argument('--split-minutes', type=int, default=5, help='分段时长(分钟), 默认5')
    parser.add_argument('--split-size', type=int, default=2048, help='分段大小上限(MB), 默认2048')
    parser.add_argument('--profile', type=str, default=None, help='指定配置文件名')
    args = parser.parse_args()
    
    profiles = find_profiles()
    if not profiles:
        print("❌ 未找到OBS配置文件")
        sys.exit(1)
    
    # 选择配置
    if args.profile:
        target = [(n, p) for n, p in profiles if n == args.profile]
        if not target:
            print(f"❌ 未找到配置: {args.profile}")
            print(f"可用配置: {[n for n, _ in profiles]}")
            sys.exit(1)
        name, ini = target[0]
    else:
        name, ini = profiles[0]
    
    if args.show:
        show_current_config(ini)
        return
    
    # 检查OBS是否在录制
    try:
        import psutil
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] and 'obs-ffmpeg-mux' in proc.info['name'].lower():
                print("❌ OBS正在录制中！请先停止录制再修改配置。")
                sys.exit(1)
    except ImportError:
        print("⚠️  无法检测OBS录制状态(需要psutil)，请确认OBS未在录制")
    
    show_current_config(ini)
    print(f"\n{'='*50}")
    print("即将修改为分段录制模式")
    print(f"{'='*50}")
    
    backup_config(ini)
    configure_split(ini, args.split_minutes, args.split_size)
    print("\n" + "="*50)
    show_current_config(ini)

if __name__ == '__main__':
    main()
