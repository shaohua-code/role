from pathlib import Path
nav=Path(r'D:\project\role\frontend\src\router\navigation.ts').read_text(encoding='utf-8-sig')
print(nav[:4000])
