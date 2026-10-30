from pathlib import Path
t=Path(r'D:\project\role\frontend\src\App.vue').read_text(encoding='utf-8-sig')
start=t.find('<div v-if="visitedPages.has(\'overview\')"')
# find end of template v-else pages - look for closing of no_access / template
end=t.find('</template>\n          </template>', start)
if end<0:
  # try find authorization_simulator block end
  end=t.find("authorization_simulator")
  print('sim', end)
  print(t[end:end+400])
else:
  print('start', start, 'end', end)
print('total len', len(t))
# find last visitedPages.has
import re
hits=list(re.finditer(r"visitedPages\.has\('([^']+)'\)", t))
print('pages', [h.group(1) for h in hits])
if hits:
  last=hits[-1].start()
  # find closing divs after last page component
  print(t[last:last+600])
