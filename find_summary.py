with open('gex_viewer.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if '_compute_flat_summary' in line:
            print(f'Line {i}: {line.strip()}')
            for j in range(max(0, i-2), min(len(lines), i+3)):
                print(f'  {j}: {lines[j].rstrip()}')
            print()
