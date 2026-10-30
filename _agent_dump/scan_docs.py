from pathlib import Path
ROOT=Path(r'D:\project\role')
print('examples', [p.name for p in (ROOT/'examples').iterdir()] if (ROOT/'examples').exists() else None)
print('sdk', [p.name for p in (ROOT/'sdk').iterdir()] if (ROOT/'sdk').exists() else None)
print('docs', [p.name for p in (ROOT/'docs').iterdir()])
# grep deerflow / 接入 in docs
for p in (ROOT/'docs').rglob('*'):
  if p.is_file() and p.suffix.lower() in {'.md','.txt','.b64'}:
    try: t=p.read_text(encoding='utf-8-sig')
    except: continue
    if any(k in t for k in ['DeerFlow','deerflow','已落地','新项目接入','接入向导']):
      print('HIT', p.relative_to(ROOT), [k for k in ['DeerFlow','deerflow','已落地','新项目接入','接入向导'] if k in t])
# backend import sdk?
hits=[]
for p in (ROOT/'backend').rglob('*.py'):
  try: t=p.read_text(encoding='utf-8',errors='ignore')
  except: continue
  if 'sdk' in t.lower() and ('from sdk' in t or 'import sdk' in t or 'role.sdk' in t or '/sdk/' in t):
    hits.append(str(p.relative_to(ROOT)))
print('backend sdk hits', hits[:20])
# frontend import examples?
