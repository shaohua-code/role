from pathlib import Path
t=Path(r'D:\project\role\frontend\src\App.vue').read_text(encoding='utf-8-sig')
# find keep-alive or v-show block
for key in ['keep-alive','v-show="page ===','visitedPages.has','admin-content','page-host']:
 print(key, t.find(key))
i=t.find('v-show="page ===')
print(t[i-200:i+1200])
