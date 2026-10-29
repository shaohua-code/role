from pathlib import Path
p=Path(r'D:\project\role\frontend\src\router\loaders.ts')
print(p.read_text(encoding='utf-8-sig')[:3500])
