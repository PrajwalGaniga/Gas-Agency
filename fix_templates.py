import os
import re

files_to_fix = ['admin.py', 'customer.py', 'driver.py']
for filepath in files_to_fix:
    if not os.path.exists(filepath):
        continue
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content = re.sub(
        r'templates\.TemplateResponse\(\s*(["\'][a-zA-Z0-9_\-\.]+["\'])\s*,',
        r'templates.TemplateResponse(request, \1,',
        content
    )
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f'Fixed {filepath}')
