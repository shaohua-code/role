import fs from 'node:fs'
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
