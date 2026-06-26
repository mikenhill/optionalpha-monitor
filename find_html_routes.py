with open('gex_viewer.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if '@app.route' in line and ('/' in line and '/api/' not in line):
            print(f'Line {i}: {line.strip()}')
