from pathlib import Path
t=Path(r'D:\project\role\frontend\src\App.vue').read_text(encoding='utf-8-sig')
print('pageComponents usage', t.count('pageComponents'))
print('v-show page', t.count('v-show="page ==='))
# show a snippet of template keep-alive area
i=t.find('visitedPages')
print(t[i:i+400] if i>=0 else 'no visited')
j=t.find('<template v-if="authed">')
print('---')
print(t[j:j+200] if j>=0 else 'no')
# find main content
k=t.find('admin-main')
print(t[k:k+500] if k>=0 else 'no main')
