import os

fixes = [
    {
        'file': r'd:\Sai Kiran\projects\genzcampus\pms\templates\admin\students.html',
        'lines_del': (146, 189),
        'remove_str': ' desktop-only'
    },
    {
        'file': r'd:\Sai Kiran\projects\genzcampus\pms\templates\admin\faculty.html',
        'lines_del': (84, 137),
        'remove_str': ' desktop-only'
    },
    {
        'file': r'd:\Sai Kiran\projects\genzcampus\pms\templates\admin\departments.html',
        'lines_del': (67, 88),
        'remove_str': ' desktop-only'
    }
]

for fix in fixes:
    filepath = fix['file']
    s_del, e_del = fix['lines_del']
    
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        s_idx = s_del - 1
        e_idx = e_del
        
        # Safely remove lines by index
        new_lines = lines[:s_idx] + lines[e_idx:]
        content = "".join(new_lines)
        
        # Remove desktop-only class
        content = content.replace(fix['remove_str'], '')
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
            
print("Templates updated successfully.")
