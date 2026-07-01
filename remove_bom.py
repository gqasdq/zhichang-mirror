import os

files = [
    r'ui\pages\gold_detector.py',
    r'ui\pages\gold_workshop.py',
    r'ui\pages\gene.py',
    r'ui\pages\parallel.py'
]

for f in files:
    with open(f, 'rb') as fh:
        content = fh.read()
    
    if content.startswith(b'\xef\xbb\xbf'):
        content = content[3:]
        with open(f, 'wb') as fh:
            fh.write(content)
        print(f'[FIXED] BOM removed: {f}')
    else:
        print(f'[OK] No BOM: {f}')

print('\nDone. Now verify.')