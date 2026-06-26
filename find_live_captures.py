with open('gex_viewer.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if 'CREATE TABLE' in line and 'live_captures' in line:
            print(f'Line {i}: {line.strip()}')
            for j in range(max(0, i), min(len(lines), i+35)):
                print(f'  {j}: {lines[j].rstrip()}')
            print()
