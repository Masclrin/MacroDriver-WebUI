# -*- coding: utf-8 -*-
import re

files = [
    r'c:\Users\1\Downloads\宏驱动 webui 2.5\engine\coordinate.py',
    r'c:\Users\1\Downloads\宏驱动 webui 2.5\bridge\automation_api.py',
    r'c:\Users\1\Downloads\宏驱动 webui 2.5\webui\modules\auto\tools.js',
]

for path in files:
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    new_lines = []
    removed = 0
    for line in lines:
        if re.search(r"print\(.*\[DEBUG|console\.log\(.*\[DEBUG", line):
            removed += 1
            continue
        new_lines.append(line)
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print(f'{path}: removed {removed} debug lines')
