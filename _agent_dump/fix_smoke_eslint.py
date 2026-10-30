from pathlib import Path
ROOT=Path(r'D:\project\role\frontend')
write=lambda p,c: p.write_text(c if c.endswith('\n') else c+'\n', encoding='utf-8', newline='\n')
write(ROOT/'scripts'/'smoke-nav.mjs', r'''import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const nav = fs.readFileSync(path.join(root, 'src/router/navigation.ts'), 'utf8')
const app = fs.readFileSync(path.join(root, 'src/App.vue'), 'utf8')
const registry = fs.readFileSync(path.join(root, 'src/layout/page-registry.ts'), 'utf8')

const pageKeyMatch = nav.match(/export type PageKey = ([^\n]+)/)
if (!pageKeyMatch) {
  console.error('smoke: PageKey not found')
  process.exit(1)
}
const keys = [...pageKeyMatch[1].matchAll(/'([^']+)'/g)].map((m) => m[1])
const required = ['overview', 'application_workspace', 'organization_workspace', 'users', 'roles', 'permissions', 'audit']
for (const k of required) {
  if (!keys.includes(k)) {
    console.error('smoke: missing PageKey', k)
    process.exit(1)
  }
  if (!app.includes("'" + k + "'") && !app.includes('"' + k + '"')) {
    console.error('smoke: App.vue missing page ref', k)
    process.exit(1)
  }
}
if (!registry.includes('application_workspace') || !registry.includes('authorization_simulation')) {
  console.error('smoke: page-registry incomplete')
  process.exit(1)
}
for (const rel of [
  'src/composables/useReadinessPoll.ts',
  'src/composables/useTableFit.ts',
  'src/composables/useShellAppearance.ts',
  'src/layout/page-registry.ts',
]) {
  if (!fs.existsSync(path.join(root, rel))) {
    console.error('smoke: missing', rel)
    process.exit(1)
  }
}
console.log('smoke-nav ok', { pageKeys: keys.length })
''')
# simplify eslint config to avoid broken peer if needed
write(ROOT/'eslint.config.mjs', r'''import js from '@eslint/js'
import globals from 'globals'
import pluginVue from 'eslint-plugin-vue'
import tseslint from 'typescript-eslint'
import vueParser from 'vue-eslint-parser'

export default tseslint.config(
  { ignores: ['dist/**', 'node_modules/**', 'coverage/**'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...pluginVue.configs['flat/recommended'],
  {
    files: ['**/*.{ts,vue}'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: { ...globals.browser, ...globals.node },
      parser: vueParser,
      parserOptions: {
        parser: tseslint.parser,
        ecmaVersion: 2022,
        sourceType: 'module',
        extraFileExtensions: ['.vue'],
      },
    },
    rules: {
      'vue/multi-word-component-names': 'off',
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      'no-console': 'off',
      'vue/max-attributes-per-line': 'off',
      'vue/singleline-html-element-content-newline': 'off',
      'vue/html-self-closing': 'off',
      'vue/attributes-order': 'off',
    },
  },
)
''')
print('rewrote smoke+eslint')
