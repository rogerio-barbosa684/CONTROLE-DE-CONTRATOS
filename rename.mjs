import { spawnSync } from 'child_process'

const result = spawnSync('netlify', [
  'api', 'updateSite',
  '-d', JSON.stringify({
    site_id: 'c2b7c494-7aa7-4ee9-9c2a-f7b23577128b',
    name: 'contratos-ideal-alimentacao'
  }),
  '--auth', 'nfp_2xhzyXDZ2injiTQE2ki8dYNMZEMrKaCa9c91'
], {
  cwd: 'C:\\Users\\Rogerio Barbosa\\Desktop\\CONTROLE-CONTRATOS',
  shell: true,
  encoding: 'utf8'
})

console.log('status:', result.status)
console.log('stdout:', result.stdout)
console.log('stderr:', result.stderr)
