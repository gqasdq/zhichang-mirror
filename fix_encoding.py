import os
import sys

# 需要修复的文件列表
files = [
    r'ui\pages\gold_detector.py',
    r'ui\pages\gold_workshop.py',
    r'ui\pages\gene.py',
    r'ui\pages\parallel.py'
]

print("Starting fix...")

for f in files:
    if not os.path.exists(f):
        print(f'SKIP (not found): {f}')
        continue
    
    print(f'Processing: {f}')
    
    # 读取二进制
    with open(f, 'rb') as fh:
        content = fh.read()
    
    # 1. 去掉BOM
    if content.startswith(b'\xef\xbb\xbf'):
        content = content[3:]
        print(f'  [FIX] BOM removed')
    else:
        print(f'  [OK] No BOM found')
    
    # 2. 逐行检查并修复损坏的docstring
    lines = content.split(b'\n')
    fixed_lines = []
    in_docstring = False
    docstring_lines = []
    
    for i, line in enumerate(lines):
        try:
            line.decode('utf-8')
            # 行可以正常解码
            if in_docstring:
                docstring_lines.append(line)
                if b'"""' in line and len(docstring_lines) > 1:
                    # docstring结束，检查是否包含损坏字符
                    full_doc = b'\n'.join(docstring_lines)
                    try:
                        full_doc.decode('utf-8')
                        fixed_lines.extend(docstring_lines)
                    except:
                        # 有损坏，重新生成干净的docstring
                        print(f'  [FIX] Docstring repaired at line {i-len(docstring_lines)+2}')
                        fixed_lines.append(b'"""')
                        fixed_lines.append(b'Auto-generated module docstring.')
                        fixed_lines.append(b'"""')
                    docstring_lines = []
                    in_docstring = False
            else:
                fixed_lines.append(line)
                if b'"""' in line and b'#' not in line:
                    # 可能进入docstring
                    if line.count(b'"""') == 1:
                        in_docstring = True
                        docstring_lines = [line]
        except UnicodeDecodeError:
            # 这行有损坏
            print(f'  [FIX] Corrupted line at {i+1}')
            if in_docstring:
                docstring_lines.append(b'# [corrupted line removed]')
            else:
                fixed_lines.append(b'# [corrupted line removed]')
    
    # 写回
    with open(f, 'wb') as fh:
        fh.write(b'\n'.join(fixed_lines))
    
    print(f'  [DONE]')

print('\n=== Fix complete ===')
print('Now run verification: python verify_fix.py')