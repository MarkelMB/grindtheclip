import re
raw = open(r'C:\Users\marke\AppData\Roaming\YeahMaybe\ChoicerVoicer\game\packs_voice\American psycho tarjetas\01_Timothy Brace.txt', 'r', encoding='utf-8', errors='ignore').read().strip()
print(repr(raw))
match = re.search(r'caption\s*=\s*"([^"]+)"', raw)
print(match.group(1) if match else 'None')
