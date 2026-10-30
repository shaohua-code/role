from pathlib import Path
t=Path(r'D:\project\role\frontend\src\App.vue').read_text(encoding='utf-8-sig')
idx=0
while True:
 i=t.find('新项目接入', idx)
 if i<0: break
 print(repr(t[max(0,i-80):i+80]))
 idx=i+1
# also overview
for p in Path(r'D:\project\role\frontend\src').rglob('*.vue'):
 tt=p.read_text(encoding='utf-8-sig', errors='ignore')
 if '新项目接入' in tt or 'project-integration' in tt:
  print('HIT', p.relative_to(Path(r'D:\project\role')))
