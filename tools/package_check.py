from pathlib import Path
import ast

root = Path(__file__).resolve().parents[1]
files = list(root.rglob('*.py'))
failed = []
for path in files:
    try:
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    except Exception as exc:
        failed.append((path, exc))
print(f'Python AST check: {len(files)-len(failed)}/{len(files)} passed')
for path, exc in failed:
    print('FAIL', path, exc)
assert not failed
main = (root/'main.py').read_text(encoding='utf-8')
for forbidden in ('api.openai.com','generativelanguage.googleapis.com','localhost:11434'):
    assert forbidden not in main
print('Provider endpoint scan: PASS')
print('Package check: PASS')
