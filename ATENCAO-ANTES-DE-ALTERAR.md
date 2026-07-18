# ATENÇÃO — LEIA ANTES DE ALTERAR O SISTEMA

Este arquivo contém todas as regras e dependências críticas do sistema.
**Sempre leia este arquivo antes de fazer qualquer modificação.**

---

## 1. ARQUIVOS DO SISTEMA

| Arquivo | Função | Crítico |
|---------|--------|---------|
| `index.html` | Versão standalone (localStorage) | SIM |
| `update_index.py` | Gera nova versão do index.html (IndexedDB) | SIM |
| `app.py` | Versão Flask (SQLite) | SIM |
| `requirements.txt` | Dependências Flask | NÃO |
| `.gitignore` | Arquivos ignorados no git | NÃO |

---

## 2. ARMAZENAMENTO — ESTRUTURA DOS DADOS

### localStorage / IndexedDB — `contratos`

```
{
  id: string,
  numero: string,
  tipo: string,
  objeto: string,
  parte: string,
  doc: string,
  valor: number,
  inicio: string (YYYY-MM-DD),
  fim: string (YYYY-MM-DD),
  responsavel: string,
  setor: string,
  obs: string,
  arquivo: { data: base64, name: string, type: string } | null,
  temParcelas: boolean,
  pgtoConfig: {
    forma: 'mensal' | 'unico' | 'parcelado' | 'avulso',
    qtdParcelas: number | null,
    diaVenc: number | null,
    valorParcela: number | null
  },
  aditivos: array,
  criadoEm: string
}
```

### localStorage / IndexedDB — `pagamentos`

```
{
  id: string,
  contratoId: string,
  contratoNum: string,
  descricao: string,
  valor: number,
  vencimento: string (YYYY-MM-DD),
  dataPagamento: string | null,
  valorPago: number | null,
  formaPgto: string | null,
  obs: string,
  comprovante: { data: base64, name: string } | null,
  status: 'pendente' | 'pago',
  renegociado: boolean
}
```

### SQLite (app.py) — contracts / payments / additives / users / audit_log

---

## 3. FUNÇÕES CRÍTICAS — NÃO ALTERAR SEM ENTENDER O IMPACTO

### `salvarContrato()` — CORAÇÃO DO SISTEMA
- Cria e edita contratos
- Contém lógica de regeneração de parcelas na edição:
  - Preserva parcelas pagas (com comprovantes)
  - Remove parcelas não pagas
  - Gera novas parcelas com saldo restante
  - Se alterar `qtdParcelas` na edição, divide o saldo automaticamente

### `gerarParcelasAuto()`
- Gera parcelas automaticamente ao criar contrato
- Respeita a forma de pagamento (mensal, único, parcelado)

### `abrirDetalhe()` — MODAL DE INFORMAÇÕES
- Exibe dados do contrato, aditivos, pagamentos e comprovantes
- Qualquer alteração aqui pode esconder informações do usuário

### `abrirBaixa()` / `confirmarBaixa()` — BAIXA DE PAGAMENTO
- Se pagar valor menor que o original, cria parcela complementar
- Preserva comprovante anexado

### `salvarAditivo()` / `abrirAditivo()`
- Atualiza data fim e/ou valor total do contrato
- Mantém histórico no array `aditivos`

---

## 4. IDS DOS ELEMENTOS HTML — NÃO RENOMEAR

```
f-numero, f-tipo, f-objeto, f-parte, f-doc, f-doc-tipo
f-valor, f-inicio, f-fim, f-responsavel, f-setor, f-obs
f-arquivo, f-arquivo-info, f-arquivo-nome
f-tem-parcelas, secao-parcelas
f-forma-pgto, f-qtd-parcelas, f-dia-venc, f-valor-parcela
filtro-contrato, filtro-status, filtro-parte
tb-contratos, tb-pagamentos, tb-vencimentos
summary-cards, detalhe-content, detalhe-btns
modal-detalhe, modal-aditivo, modal-pagamento, modal-baixar, modal-parcelar
mp-contrato, mp-desc, mp-valor, mp-vencimento, mp-datapgto, mp-forma, mp-obs
bx-data, bx-valor, bx-forma, bx-obs, bx-arquivo, bx-comprovante, diff-aviso
ad-numero, ad-data, ad-tipo, ad-nova-data, ad-novo-valor, ad-objeto
aditivo-info, ad-grp-nova-data, ad-grp-novo-valor
pk-qtd, pk-inicio, pk-dia, pk-valor-total, pk-preview, pk-confirmar, parcelar-info
```

---

## 5. FUNÇÕES AUXILIARES — DEPENDÊNCIAS

| Função | Usada por |
|--------|-----------|
| `uid()` | Geração de ID único — usada em TODO cadastro |
| `fileToBase64()` | Upload de arquivos (contrato e comprovante) |
| `downloadBase64()` | Download de anexos e comprovantes |
| `fmtMoeda()` | Formatação de valores em reais — usada em TODAS as telas |
| `fmtData()` | Formatação de datas (YYYY-MM-DD → DD/MM/YYYY) |
| `calcStatusPgto()` | Define badge (pago/pendente/atrasado) |
| `gerarDatas()` | Geração de datas para parcelamento |
| `formatarDoc()` | Máscara de CNPJ/CPF |
| `onDocInput()` / `onDocBlur()` | Formatação automática no input |
| `toUpper()` | Maiúsculas automáticas em campos de texto |
| `onArquivoChange()` / `removerArquivoContrato()` | Upload de arquivo com feedback visual |
| `popularFiltroContrato()` | Popula select de filtro por contrato |
| `toggleParcelas()` / `atualizarCamposParcela()` | Exibe/esconde seção de parcelas |
| `verificarDiferenca()` | Aviso de valor pago diferente do original |

---

## 6. REGRAS PARA QUALQUER ALTERAÇÃO

1. **Nunca quebrar a estrutura dos dados** no localStorage/IndexedDB — contratos antigos deixariam de funcionar
2. **Nunca remover campos** do objeto `contrato` ou `pagamento` — dados já salvos seriam corrompidos
3. **Apenas adicionar campos novos**, nunca renomear ou excluir existentes
4. **Testar sempre o ciclo completo**: criar contrato → gerar parcelas → pagar uma → editar → verificar regeneração
5. **Manter o layout original**: cores, tamanhos, posição dos botões não devem mudar
6. **Sempre dar Ctrl+Shift+R** (hard refresh) antes de testar no navegador
7. **Fazer backup** (pasta `script3/` ou similar) antes de alterações grandes
8. **Alterar `update_index.py` e `index.html` juntos** quando a mudança for nas funções JS — um é gerador do outro
