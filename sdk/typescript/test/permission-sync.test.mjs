import assert from 'node:assert/strict'
import test from 'node:test'
import { IamAdminClient, syncPermissionManifest } from '../src/permission-sync.ts'

const MANIFEST = [
  { code: 'demo.document.read', resource_type: 'document', scope: 'read', description: '读取文档' },
  { code: 'demo.document.create', resource_type: 'document', scope: 'write' },
]

function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } })
}

/** 顺序 mock：每次 fetch 弹出队列中的一个结果（Response 或 Error）。 */
function fetchQueue(results, calls = []) {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async (_url, init) => {
    calls.push(init)
    const next = results.shift()
    if (next instanceof Error) throw next
    return next
  }
  return () => { globalThis.fetch = originalFetch }
}

test('listPermissions sends bearer token and normalizes trailing slash', async () => {
  const calls = []
  const restore = fetchQueue([jsonResponse([{ id: 'p1', code: 'demo.a' }])], calls)
  try {
    const client = new IamAdminClient('https://iam.example/')
    const items = await client.listPermissions('mgmt-token')
    assert.equal(calls[0].method, 'GET')
    assert.equal(calls[0].headers.Authorization, 'Bearer mgmt-token')
    assert.deepEqual(items.map((item) => item.code), ['demo.a'])
  } finally { restore() }
})

test('createPermission posts full payload', async () => {
  const calls = []
  const restore = fetchQueue([jsonResponse({ id: 'p2' })], calls)
  try {
    const client = new IamAdminClient('https://iam.example')
    await client.createPermission('mgmt-token', {
      code: 'demo.b', resource_type: 'doc', scope: 'write', description: '创建',
    })
    assert.equal(calls[0].method, 'POST')
    assert.deepEqual(JSON.parse(calls[0].body), {
      code: 'demo.b', resource_type: 'doc', scope: 'write', description: '创建',
    })
  } finally { restore() }
})

test('http rejection keeps status code', async () => {
  const restore = fetchQueue([new Response('', { status: 409 })])
  try {
    const client = new IamAdminClient('https://iam.example')
    await assert.rejects(
      client.createPermission('mgmt-token', { code: 'demo.x', resource_type: 'doc', scope: 'read' }),
      (error) => error.name === 'IamAdminError' && error.statusCode === 409,
    )
  } finally { restore() }
})

test('network failure maps to 503', async () => {
  const restore = fetchQueue([new Error('offline')])
  try {
    const client = new IamAdminClient('https://iam.example')
    await assert.rejects(client.listPermissions('mgmt-token'), (error) => error.statusCode === 503)
  } finally { restore() }
})

test('non-list catalog is contract error', async () => {
  const restore = fetchQueue([jsonResponse({ permissions: [] })])
  try {
    const client = new IamAdminClient('https://iam.example')
    await assert.rejects(client.listPermissions('mgmt-token'), (error) => error.statusCode === 502)
  } finally { restore() }
})

test('empty catalog creates every entry', async () => {
  const calls = []
  const restore = fetchQueue([jsonResponse([]), jsonResponse({ id: 'p1' }), jsonResponse({ id: 'p2' })], calls)
  try {
    const client = new IamAdminClient('https://iam.example')
    const report = await syncPermissionManifest(MANIFEST, { client, managementToken: 'mgmt-token' })
    assert.deepEqual(report.created, ['demo.document.read', 'demo.document.create'])
    assert.deepEqual(report.skipped, [])
    assert.deepEqual(report.failed, [])
    assert.equal(calls.length, 3)
  } finally { restore() }
})

test('existing codes are skipped without create', async () => {
  const calls = []
  const restore = fetchQueue([jsonResponse([
    { id: 'p1', code: 'demo.document.read' },
    { id: 'p2', code: 'demo.document.create' },
  ])], calls)
  try {
    const client = new IamAdminClient('https://iam.example')
    const report = await syncPermissionManifest(MANIFEST, { client, managementToken: 'mgmt-token' })
    assert.deepEqual(report.skipped, ['demo.document.read', 'demo.document.create'])
    assert.deepEqual(report.created, [])
    // 只发生了一次目录读取，零次创建——重跑完全幂等。
    assert.equal(calls.length, 1)
  } finally { restore() }
})

test('conflict recheck confirms existing as skipped', async () => {
  const restore = fetchQueue([
    jsonResponse([]),
    new Response('', { status: 409 }),
    jsonResponse([{ id: 'p1', code: 'demo.document.read' }]),
    jsonResponse({ id: 'p2' }),
  ])
  try {
    const client = new IamAdminClient('https://iam.example')
    const report = await syncPermissionManifest(MANIFEST, { client, managementToken: 'mgmt-token' })
    assert.deepEqual(report.skipped, ['demo.document.read'])
    assert.deepEqual(report.created, ['demo.document.create'])
    assert.deepEqual(report.failed, [])
  } finally { restore() }
})

test('conflict with missing code fails closed', async () => {
  const restore = fetchQueue([
    jsonResponse([]),
    new Response('', { status: 409 }),
    jsonResponse([]),
    jsonResponse({ id: 'p1' }),
  ])
  try {
    const client = new IamAdminClient('https://iam.example')
    const report = await syncPermissionManifest(MANIFEST, { client, managementToken: 'mgmt-token' })
    assert.deepEqual(report.failed, [{ code: 'demo.document.read', reason: 'conflict but code missing from catalog' }])
    assert.deepEqual(report.created, ['demo.document.create'])
  } finally { restore() }
})

test('single entry failure does not abort batch', async () => {
  const restore = fetchQueue([
    jsonResponse([]),
    new Response('', { status: 403 }),
    jsonResponse({ id: 'p2' }),
  ])
  try {
    const client = new IamAdminClient('https://iam.example')
    const report = await syncPermissionManifest(MANIFEST, { client, managementToken: 'mgmt-token' })
    assert.deepEqual(report.failed, [{ code: 'demo.document.read', reason: 'iam error 403' }])
    assert.deepEqual(report.created, ['demo.document.create'])
  } finally { restore() }
})

test('catalog unreachable aborts before any create', async () => {
  const calls = []
  const restore = fetchQueue([new Error('offline')], calls)
  try {
    const client = new IamAdminClient('https://iam.example')
    await assert.rejects(
      syncPermissionManifest(MANIFEST, { client, managementToken: 'mgmt-token' }),
      (error) => error.statusCode === 503,
    )
    assert.equal(calls.length, 1)
  } finally { restore() }
})

test('invalid manifest rejected before any network call', async () => {
  const calls = []
  const restore = fetchQueue([jsonResponse([])], calls)
  try {
    const client = new IamAdminClient('https://iam.example')
    const invalidManifests = [
      [],
      [{ code: 'ab', resource_type: 'doc', scope: 'read' }],
      [{ code: 'demo.ok', resource_type: '', scope: 'read' }],
      [{ code: 'demo.ok', resource_type: 'doc' }],
      [
        { code: 'demo.dup', resource_type: 'doc', scope: 'read' },
        { code: 'demo.dup', resource_type: 'doc', scope: 'read' },
      ],
      'not-a-list',
    ]
    for (const manifest of invalidManifests) {
      await assert.rejects(
        syncPermissionManifest(manifest, { client, managementToken: 'mgmt-token' }),
        { name: 'Error' },
      )
    }
    assert.equal(calls.length, 0)
  } finally { restore() }
})

test('missing management token rejected locally', async () => {
  const client = new IamAdminClient('https://iam.example')
  await assert.rejects(client.listPermissions(''), { name: 'Error' })
})
