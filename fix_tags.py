import os
import re

dir_path = r'd:\kalpavrix\PTH\super_admin\templates\super_admin'
for root, _, files in os.walk(dir_path):
    for filename in files:
        if not filename.endswith('.html'): continue
        filepath = os.path.join(root, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # fix multi-line {{ ... }} tags
        def fix_tag(match):
            # Replace all whitespaces (including newlines) with a single space inside the tag
            inner = match.group(0)
            inner = re.sub(r'\s+', ' ', inner)
            return inner
            
        new_content = re.sub(r'\{\{[^}]+\}\}', fix_tag, content)
        new_content = re.sub(r'\{%[^%]+%\}', fix_tag, new_content)
        
        # also fix the commented out </td> if present
        new_content = new_content.replace('<!-- </td> -->', '</td>')
        
        if content != new_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
print('Fixed template tags!')
