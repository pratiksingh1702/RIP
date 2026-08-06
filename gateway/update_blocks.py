import os
import re

d = r'c:\Users\Dell\Downloads\RIP\gateway\gateway\core\blocks'
for f in os.listdir(d):
    if f.endswith('.py'):
        p = os.path.join(d, f)
        with open(p, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Replace occurrences of output_schema where config_schema is missing
        new_content = re.sub(
            r'("output_schema":\s*self\.output_schema)\s*\}',
            r'\1, "config_schema": self.config_schema}',
            content
        )
        if new_content != content:
            with open(p, 'w', encoding='utf-8') as file:
                file.write(new_content)
            print(f'Updated {f}')
