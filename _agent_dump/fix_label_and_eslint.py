from pathlib import Path

p = Path(r"D:\project\role\frontend\src\views\permissions\PermissionCatalog.vue")
t = p.read_text(encoding="utf-8")
old = "const invalid = fields.find(([label, value, max]) => !value || value.length > max)"
new = "const invalid = fields.find(([_label, value, max]) => !value || value.length > max)"
if old in t:
    p.write_text(t.replace(old, new, 1), encoding="utf-8", newline="\n")
    print("fixed label")
else:
    print("label line missing")
    for ln in t.splitlines():
        if "fields.find" in ln:
            print(repr(ln))

cfg = r'''import js from '@eslint/js'
import globals from 'globals'
import pluginVue from 'eslint-plugin-vue'
import tseslint from 'typescript-eslint'
import vueParser from 'vue-eslint-parser'

/**
 * 可维护基线：关掉大规模格式类规则，保留真实问题。
 * 归档页不参与 lint。
 */
export default tseslint.config(
  {
    ignores: [
      'dist/**',
      'node_modules/**',
      'coverage/**',
      'src/views/_archive/**',
    ],
  },
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
      'vue/multiline-html-element-content-newline': 'off',
      'vue/html-self-closing': 'off',
      'vue/attributes-order': 'off',
      'vue/html-indent': 'off',
      'vue/first-attribute-linebreak': 'off',
      'vue/html-closing-bracket-newline': 'off',
      'vue/html-closing-bracket-spacing': 'off',
      'vue/html-quotes': 'off',
      'vue/require-default-prop': 'off',
      'vue/v-on-event-hyphenation': 'off',
      'vue/attribute-hyphenation': 'off',
    },
  },
)
'''
Path(r"D:\project\role\frontend\eslint.config.mjs").write_text(cfg, encoding="utf-8", newline="\n")
print("eslint.config.mjs rewritten")

# verify ResourceIcon still parses
ri = Path(r"D:\project\role\frontend\src\views\application-workspace\components\ResourceIcon.vue").read_text(encoding="utf-8")
print("ResourceIcon import block:")
print("\n".join(ri.splitlines()[:25]))
