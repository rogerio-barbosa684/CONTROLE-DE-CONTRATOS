import { spawnSync } from 'child_process'
import { readFileSync } from 'fs'

const token = 'nfp_2xhzyXDZ2injiTQE2ki8dYNMZEMrKaCa9c91'
const site = '8930c62d-7385-40be-951b-2ba562156485'

const vars = [
  { key: 'JWT_SECRET', values: [{ value: '5a95f5625a874bca9da932f536f477e8c39c28f5f2c14e0d9501f75a199401a9', context: 'all' }] },
  { key: 'SUPABASE_URL', values: [{ value: 'https://pgehubucomamrmdgpvhn.supabase.co', context: 'all' }] },
  { key: 'SUPABASE_SERVICE_ROLE_KEY', values: [{ value: 'sb_secret_HRHEyYIEUW0BK7-ZOAS9rA_OQiyyfLm', context: 'all' }] }
]

for (const v of vars) {
  const data = JSON.stringify({ site_id: site, env_vars: [v] })
  const result = spawnSync('netlify', ['api', 'createEnvVars', '-d', data, '--auth', token], {
    cwd: 'C:\\Users\\Rogerio Barbosa\\Desktop\\CONTROLE-CONTRATOS',
    shell: true,
    encoding: 'utf8'
  })
  console.log(`${v.key}: ${result.status} ${result.stdout} ${result.stderr}`)
}
