import re

def extrair_resumo_contrato(texto):
    dados = {
        'numero': '',
        'objeto': '',
        'contratada': '',
        'contratante': '',
        'valor': '',
        'vigencia_inicio': '',
        'vigencia_fim': '',
        'pagamento': '',
        'garantia': '',
        'vigencia': ''
    }
    if not texto:
        return dados

    patterns = {
        'numero': r'(?:Contrato|Contrato\s+N[ºo°]|n[ºo°]\s*[:.]?\s*)(\d[\d\-/\.]+)',
        'objeto': r'(?:OBJETO|objeto)[:\s]+(.+?)(?:\n|$)',
        'contratada': r'(?:Contratada|CONTRATADA|empresa|fornecedor)[:\s]+(.+?)(?:\n|$)',
        'contratante': r'(?:Contratante|CONTRATANTE|contratante)[:\s]+(.+?)(?:\n|$)',
        'valor': r'(?:valor|VALOR|pre[çc]o|total)[:\s]*(?:R\$?\s*)?([\d\.,]+)',
        'vigencia_inicio': r'(?:in[íi]cio|vig[êe]ncia.*?in[íi]cio|a partir de)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        'vigencia_fim': r'(?:fim|t[êe]rmino|vig[êe]ncia.*?(?:fim|t[êe]rmino|at[ée])[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        'pagamento': r'(?:pagamento|PAGAMENTO|forma de pag)[:\s]+(.+?)(?:\n|$)',
        'garantia': r'(?:garantia|GARANTIA|seguro)[:\s]+(.+?)(?:\n|$)',
        'vigencia': r'(?:vig[êe]ncia|VIG[ÊE]NCIA)[:\s]+(.+?)(?:\n|$)'
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, texto, re.IGNORECASE)
        if match:
            dados[key] = match.group(1).strip()

    return dados


def formatar_resumo(dados):
    if not dados:
        return 'Dados nao disponiveis.'

    linhas = []
    campos = [
        ('numero', 'Contrato'),
        ('objeto', 'Objeto'),
        ('contratada', 'Contratada'),
        ('contratante', 'Contratante'),
        ('valor', 'Valor'),
        ('vigencia', 'Vigencia'),
        ('pagamento', 'Pagamento'),
        ('garantia', 'Garantia')
    ]

    for key, label in campos:
        valor = dados.get(key, '').strip()
        if valor:
            linhas.append(f'{label}: {valor}')

    return '\n'.join(linhas) if linhas else 'Resumo nao disponivel.'