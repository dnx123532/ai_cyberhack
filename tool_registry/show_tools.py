import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

tools = json.load(open('tool_registry/registry.json'))
print(f"{'Tool':<25} {'Category':<15} {'WSL Path'}")
print("-"*80)
for t in tools:
    path = t.get('path', '')
    wsl = path.replace('E:/', '/mnt/e/').replace('\\', '/')
    if wsl.startswith('E:'):
        wsl = '/mnt/e/' + wsl[3:]
    entry = t.get('exec', t['tool']).replace('\\', '/')
    if '/' in entry and not entry.startswith('/mnt'):
        entry = '/mnt/e/' + entry.replace('E:/', '').replace('E:\\', '')
    print(f"{t['tool']:<25} {t['category']:<15} {wsl}")
    print(f"  exec: python3 {wsl}/{t['tool'].lower()}.py {t.get('usage','--help')}")
    print()
