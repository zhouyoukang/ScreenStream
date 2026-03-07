"""
双机secrets.env同步检查
用法: python sync_check.py
比较笔记本和台式机(SMB)的secrets.env是否一致
"""
import os
import hashlib
import sys

# 路径配置
LAPTOP_SECRETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "secrets.env")
DESKTOP_SECRETS_SMB = r"W:\道\道生一\一生二\secrets.env"  # SMB共享路径


def file_hash(path):
    """计算文件SHA256"""
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def compare_keys(path1, path2):
    """比较两个env文件的键差异"""
    def load_keys(path):
        keys = set()
        if not os.path.exists(path):
            return keys
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    keys.add(line.split("=", 1)[0].strip())
        return keys
    
    keys1 = load_keys(path1)
    keys2 = load_keys(path2)
    
    only_in_1 = keys1 - keys2
    only_in_2 = keys2 - keys1
    
    return only_in_1, only_in_2


def main():
    print("=" * 60)
    print("双机 secrets.env 同步检查")
    print("=" * 60)
    
    # 检查笔记本
    laptop_hash = file_hash(LAPTOP_SECRETS)
    if laptop_hash:
        print(f"\n✅ 笔记本: {LAPTOP_SECRETS}")
        print(f"   SHA256: {laptop_hash[:16]}...")
    else:
        print(f"\n❌ 笔记本: {LAPTOP_SECRETS} 不存在")
        sys.exit(1)
    
    # 检查台式机(SMB)
    desktop_hash = file_hash(DESKTOP_SECRETS_SMB)
    if desktop_hash:
        print(f"✅ 台式机: {DESKTOP_SECRETS_SMB}")
        print(f"   SHA256: {desktop_hash[:16]}...")
    else:
        print(f"⚠️  台式机: {DESKTOP_SECRETS_SMB} 不可达（SMB未连接？）")
        print("   跳过同步比较")
        sys.exit(0)
    
    # 比较
    if laptop_hash == desktop_hash:
        print("\n✅ 双机secrets.env完全同步")
    else:
        print("\n🔴 双机secrets.env不同步!")
        only_laptop, only_desktop = compare_keys(LAPTOP_SECRETS, DESKTOP_SECRETS_SMB)
        if only_laptop:
            print(f"   仅笔记本有: {', '.join(sorted(only_laptop))}")
        if only_desktop:
            print(f"   仅台式机有: {', '.join(sorted(only_desktop))}")
        if not only_laptop and not only_desktop:
            print("   键名相同，但值不同")
        sys.exit(1)


if __name__ == "__main__":
    main()
