import re

file_path = 'app.py'
with open(file_path, 'r') as f:
    content = f.read()

# Pattern to find @app.route('...') or @app.route("...")
# We want to catch routes that don't already have <college_slug>
pattern = r"@app\.route\((['\"])(/(?!<college_slug>|static|super-admin|login$|/$).*?)\1"

def replacement(match):
    quote = match.group(1)
    path = match.group(2)
    return f"@app.route({quote}/<college_slug>{path}{quote}"

new_content = re.sub(pattern, replacement, content)

# Also fix static routes if any (though usually handled by flask)
# And handle internal blueprint routes if needed.

with open(file_path, 'w') as f:
    f.write(new_content)

print("Bulk route refactoring complete.")
