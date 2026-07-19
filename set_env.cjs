const { execSync } = require('child_process')
const data = JSON.stringify({
  site_id: '8930c62d-7385-40be-951b-2ba562156485',
  env_vars: [
    { key: 'JWT_SECRET', values: [{ value: '5a95f5625a874bca9da932f536f477e8c39c28f5f2c14e0d9501f75a199401a9', context: 'all' }] },
    { key: 'SUPABASE_URL', values: [{ value: 'https://pgehubucomamrmdgpvhn.supabase.co', context: 'all' }] },
    { key: 'SUPABASE_SERVICE_ROLE_KEY', values: [{ value: 'sb_secret_HRHEyYIEUW0BK7-ZOAS9rA_OQiyyfLm', context: 'all' }] }
  ]
})
const cmd = `netlify api createEnvVars -d '${data}' --auth nfp_2xhzyXDZ2injiTQE2ki8dYNMZEMrKaCa9c91`
console.log(execSync(cmd, { cwd: 'C:\\Users\\Rogerio Barbosa\\Desktop\\CONTROLE-CONTRATOS', encoding: 'utf8', shell: true }))
