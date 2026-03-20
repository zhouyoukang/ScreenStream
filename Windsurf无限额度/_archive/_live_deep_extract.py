"""Deep extract: parse windsurfAuthStatus fully + decode protobuf model configs"""
import sqlite3, json, os, base64, struct, sys

DB = os.path.expandvars(r'%APPDATA%\Windsurf\User\globalStorage\state.vscdb')
conn = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
cur = conn.cursor()

# 1. Full windsurfAuthStatus structure
print("=" * 70)
print("FULL windsurfAuthStatus STRUCTURE")
print("=" * 70)
cur.execute("SELECT value FROM ItemTable WHERE key='windsurfAuthStatus'")
row = cur.fetchone()
if not row:
    print("NOT FOUND")
    sys.exit(1)

auth = json.loads(row[0])
print(f"Top-level keys: {list(auth.keys())}")

# Print each key with type and size
for k, v in auth.items():
    if isinstance(v, str):
        print(f"  {k}: str({len(v)})")
    elif isinstance(v, list):
        print(f"  {k}: list({len(v)})")
        if v and isinstance(v[0], dict):
            print(f"    [0] keys: {list(v[0].keys())[:10]}")
    elif isinstance(v, dict):
        print(f"  {k}: dict({len(v)}) keys={list(v.keys())[:8]}")
    elif isinstance(v, (int, float, bool)):
        print(f"  {k}: {v}")
    else:
        print(f"  {k}: {type(v).__name__}")

# 2. Decode protobuf - raw field inspection
print("\n" + "=" * 70)
print("PROTOBUF RAW FIELD INSPECTION")
print("=" * 70)
pb_b64 = auth.get('userStatusProtoBinaryBase64', '')
if pb_b64:
    data = base64.b64decode(pb_b64)
    print(f"Total bytes: {len(data)}")
    
    # Simple protobuf wire format parser
    def parse_protobuf_fields(data, max_fields=200):
        fields = {}
        pos = 0
        count = 0
        while pos < len(data) and count < max_fields:
            try:
                # Read varint tag
                tag = 0
                shift = 0
                while pos < len(data):
                    b = data[pos]
                    pos += 1
                    tag |= (b & 0x7F) << shift
                    shift += 7
                    if not (b & 0x80):
                        break
                
                field_num = tag >> 3
                wire_type = tag & 0x07
                
                if wire_type == 0:  # Varint
                    val = 0
                    shift = 0
                    while pos < len(data):
                        b = data[pos]
                        pos += 1
                        val |= (b & 0x7F) << shift
                        shift += 7
                        if not (b & 0x80):
                            break
                    fields.setdefault(field_num, []).append(('varint', val))
                elif wire_type == 1:  # 64-bit
                    val = struct.unpack_from('<Q', data, pos)[0]
                    pos += 8
                    fields.setdefault(field_num, []).append(('fixed64', val))
                elif wire_type == 2:  # Length-delimited
                    length = 0
                    shift = 0
                    while pos < len(data):
                        b = data[pos]
                        pos += 1
                        length |= (b & 0x7F) << shift
                        shift += 7
                        if not (b & 0x80):
                            break
                    val = data[pos:pos+length]
                    pos += length
                    fields.setdefault(field_num, []).append(('bytes', val))
                elif wire_type == 5:  # 32-bit
                    val = struct.unpack_from('<I', data, pos)[0]
                    pos += 4
                    fields.setdefault(field_num, []).append(('fixed32', val))
                else:
                    break
                count += 1
            except:
                break
        return fields
    
    fields = parse_protobuf_fields(data)
    print(f"Top-level fields: {len(fields)}")
    
    for fnum in sorted(fields.keys()):
        vals = fields[fnum]
        for wtype, val in vals[:3]:  # max 3 values per field
            if wtype == 'varint':
                print(f"  Field {fnum:3d} (varint): {val}")
            elif wtype == 'bytes':
                # Try decode as UTF-8
                try:
                    txt = val.decode('utf-8')
                    if txt.isprintable() and len(txt) < 200:
                        print(f"  Field {fnum:3d} (string): {txt[:150]}")
                    else:
                        print(f"  Field {fnum:3d} (bytes): {len(val)}B")
                except:
                    print(f"  Field {fnum:3d} (bytes): {len(val)}B")
            elif wtype in ('fixed64', 'fixed32'):
                print(f"  Field {fnum:3d} ({wtype}): {val}")
        if len(vals) > 3:
            print(f"  Field {fnum:3d}: ... +{len(vals)-3} more values")

# 3. Search for model-related strings in protobuf
print("\n" + "=" * 70)
print("MODEL STRINGS IN PROTOBUF")
print("=" * 70)
if pb_b64:
    import re
    text_chunks = re.findall(b'[\x20-\x7e]{8,}', data)
    model_strings = [s.decode() for s in text_chunks if any(k in s.lower() for k in [b'claude', b'gpt', b'swe', b'sonnet', b'opus', b'gemini', b'kimi', b'model', b'credit', b'free', b'cascade'])]
    print(f"Model-related strings ({len(model_strings)}):")
    for s in sorted(set(model_strings))[:50]:
        print(f"  {s[:120]}")

# 4. Look for model configs in other auth fields
print("\n" + "=" * 70)
print("MODEL CONFIG SEARCH IN ALL AUTH FIELDS")
print("=" * 70)
for k, v in auth.items():
    if isinstance(v, list) and v:
        if isinstance(v[0], dict) and any(mk in str(v[0]).lower() for mk in ['model', 'credit', 'cost', 'display']):
            print(f"\n  {k} ({len(v)} items):")
            for item in v[:5]:
                print(f"    {json.dumps(item)[:300]}")
    elif isinstance(v, dict):
        if any(mk in str(v).lower() for mk in ['model', 'credit', 'cost', 'multiplier']):
            print(f"\n  {k}: {json.dumps(v)[:500]}")

# 5. Screenshot model list from user's image
print("\n" + "=" * 70)
print("USER'S VISIBLE MODEL LIST (from screenshot)")
print("=" * 70)
visible_models = [
    ("SWE-1.5 Fast", "0.5x", "Recently Used"),
    ("Claude Opus 4.6 Thinking 1M", "12x", "Recently Used"),
    ("GPT-5.3-Codex Medium", "2x", "Recently Used, New"),
    ("Claude Sonnet 4.5", "2x", "Recommended"),
    ("Kimi K2.5", "1x", "Recommended, New"),
    ("SWE-1.5", "Free", "Recommended"),
]
print(f"{'Model':<35} {'Cost':<8} {'Category'}")
print("-" * 60)
for name, cost, cat in visible_models:
    print(f"  {name:<33} {cost:<8} {cat}")

conn.close()
print("\nDONE")
