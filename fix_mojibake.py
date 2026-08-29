import os
import glob

packs_dir = r'C:\Users\marke\AppData\Roaming\YeahMaybe\ChoicerVoicer\game\packs_voice'

replacements = {
    'â€œ': '"',
    'â€': '"',
    'â€"': '-',
    'â€™': "'",
    'â€¦': '...',
    'Â¡': '¡',
    'Â¿': '¿',
    'Ã¡': 'á',
    'Ã©': 'é',
    'Ã\xad': 'í',
    'Ã³': 'ó',
    'Ãº': 'ú',
    'Ã±': 'ñ',
    'Ã\x81': 'Á',
    'Ã\x89': 'É',
    'Ã\x8d': 'Í',
    'Ã\x93': 'Ó',
    'Ã\x9a': 'Ú',
    'Ã\x91': 'Ñ',
    'â\x8f\x93': '⏳',
    'ð\x9f\x8e\xa4': '🎤'
}

for root, dirs, files in os.walk(packs_dir):
    for file in files:
        if file.endswith('.txt') or file.endswith('.json'):
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                changed = False
                for bad, good in replacements.items():
                    if bad in content:
                        content = content.replace(bad, good)
                        changed = True
                
                if changed:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"Fixed mojibake in {file}")
            except Exception as e:
                pass
