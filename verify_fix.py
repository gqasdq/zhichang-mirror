import sys

files = [
    r'ui\pages\gold_detector.py',
    r'ui\pages\gold_workshop.py',
    r'ui\pages\gene.py',
    r'ui\pages\parallel.py'
]

print("Verifying files...")
errors = []
for f in files:
    try:
        with open(f, 'r', encoding='utf-8') as fh:
            content = fh.read()
        compile(content, f, 'exec')
        print(f'  [OK] {f}')
    except Exception as e:
        print(f'  [FAIL] {f}: {e}')
        errors.append(f)

if errors:
    print(f'\n!!! Still broken: {len(errors)} files !!!')
    sys.exit(1)
else:
    print('\n=== All files passed ===')