import os
import time
from datetime import date, datetime

import requests

AIRTABLE_TOKEN = os.environ.get('AIRTABLE_TOKEN')
AIRTABLE_BASE_ID = os.environ.get('AIRTABLE_BASE_ID')
AIRTABLE_TABLE_NAME = os.environ.get('AIRTABLE_TABLE_NAME', 'LEADS')

OUTLOOK_SEND_ENABLED = os.environ.get('OUTLOOK_SEND_ENABLED', 'false').lower() == 'true'
MS_GRAPH_TOKEN = os.environ.get('MS_GRAPH_TOKEN')

CALL_E_ENABLED = os.environ.get('CALL_E_ENABLED', 'false').lower() == 'true'
CALL_E_API_URL = os.environ.get('CALL_E_API_URL')
CALL_E_API_KEY = os.environ.get('CALL_E_API_KEY')

AIRTABLE_URL = f'https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}'
ACTIVE_STATUSES = ('Pendente', 'Contatado', 'Follow-up 1', 'Follow-up 2')

EMAIL_TEMPLATES = {
    'email_1': {
        'subject': 'Uma ideia rápida para o {nome}',
        'body': (
            'Olá,\n\n'
            'Meu nome é David. Encontrei o {nome} pesquisando negócios em São Paulo '
            'e percebi que vocês têm uma presença real — avaliações e clientes — '
            'mas ainda poderiam se beneficiar de um site simples e profissional.\n\n'
            'Hoje, muita gente pesquisa no Google antes de escolher onde ir ou agendar. '
            'Uma página com fotos, serviços, horários, localização e botão de WhatsApp '
            'deixa o negócio mais fácil de encontrar e mais confiável.\n\n'
            'Posso preparar uma prévia visual gratuita de como ficaria um site para o {nome}. '
            'Sem compromisso — é só para vocês verem a ideia.\n\n'
            'Atenciosamente,\nDavid Waisenberg Ribas'
        ),
    },
    'email_2': {
        'subject': 'Re: Uma ideia rápida para o {nome}',
        'body': (
            'Olá,\n\n'
            'Passando apenas para saber se minha mensagem anterior chegou bem.\n\n'
            'A proposta é simples: mostrar como o {nome} poderia aparecer com uma página '
            'profissional — informações claras, fotos, localização e botão direto para WhatsApp.\n\n'
            'Posso enviar uma prévia visual sem custo, se quiserem ver.\n\n'
            'Atenciosamente,\nDavid Waisenberg Ribas'
        ),
    },
    'email_3': {
        'subject': 'Re: {nome}',
        'body': (
            'Olá,\n\n'
            'Não quero tomar mais o seu tempo, então esta será minha última mensagem.\n\n'
            'Caso em algum momento queiram ver uma ideia de site para o {nome}, '
            'é só responder este e-mail.\n\n'
            'Muito sucesso ao negócio de vocês.\n\n'
            'Atenciosamente,\nDavid Waisenberg Ribas'
        ),
    },
}

CALL_SCRIPT = (
    'Olá, boa tarde. Poderia falar com o responsável pelo {nome}?\n\n'
    'Meu nome é David. Estou entrando em contato porque vi o {nome} '
    'e acredito que vocês poderiam se beneficiar de uma página profissional simples — '
    'com fotos, informações principais, localização e botão direto para WhatsApp.\n\n'
    'Posso enviar uma prévia visual sem compromisso. '
    'Qual seria o melhor contato para eu mandar?'
)


def require_env():
    missing = [key for key in ('AIRTABLE_TOKEN', 'AIRTABLE_BASE_ID') if not os.environ.get(key)]
    if missing:
        raise RuntimeError('Missing required environment variables: ' + ', '.join(missing))


def headers():
    return {'Authorization': f'Bearer {AIRTABLE_TOKEN}', 'Content-Type': 'application/json'}


def today_iso():
    return date.today().isoformat()


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], '%Y-%m-%d').date()
    except ValueError:
        return None


def airtable_request(method, url, **kwargs):
    for attempt in range(3):
        response = getattr(requests, method)(url, headers=headers(), timeout=30, **kwargs)
        if response.status_code == 429:
            time.sleep(2 ** (attempt + 1))
            continue
        response.raise_for_status()
        return response
    raise RuntimeError(f'Airtable {method.upper()} failed after retries: {url}')


def list_active_records():
    formula = 'OR(' + ','.join([f"{{Status}}='{status}'" for status in ACTIVE_STATUSES]) + ')'
    records = []
    params = {
        'pageSize': 100,
        'filterByFormula': formula,
        'sort[0][field]': 'Score Lead',
        'sort[0][direction]': 'desc',
    }
    while True:
        data = airtable_request('get', AIRTABLE_URL, params=params).json()
        records.extend(data.get('records', []))
        offset = data.get('offset')
        if not offset:
            break
        params = dict(params, offset=offset)
        time.sleep(0.25)
    return records


def update_record(record_id, fields):
    airtable_request('patch', f'{AIRTABLE_URL}/{record_id}', json={'fields': fields, 'typecast': True})


def append_note(record, text):
    current = record.get('fields', {}).get('Notas', '') or ''
    stamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    new_note = (current + '\n' if current else '') + f'[{stamp}] {text}'
    update_record(record['id'], {'Notas': new_note})


def send_email(to_email, subject, body):
    if not to_email:
        return False, 'sem email cadastrado'
    if not OUTLOOK_SEND_ENABLED:
        return False, '[SIMULADO] email não enviado — OUTLOOK_SEND_ENABLED=false'
    if not MS_GRAPH_TOKEN:
        return False, 'MS_GRAPH_TOKEN ausente'
    payload = {
        'message': {
            'subject': subject,
            'body': {'contentType': 'Text', 'content': body},
            'toRecipients': [{'emailAddress': {'address': to_email}}],
        },
        'saveToSentItems': True,
    }
    response = requests.post(
        'https://graph.microsoft.com/v1.0/me/sendMail',
        headers={'Authorization': f'Bearer {MS_GRAPH_TOKEN}', 'Content-Type': 'application/json'},
        json=payload,
        timeout=30,
    )
    if response.status_code in (200, 202):
        return True, 'email enviado'
    return False, f'erro Outlook {response.status_code}: {response.text[:300]}'


def run_call(phone, nome):
    if not phone:
        return False, 'sem telefone cadastrado'
    if not CALL_E_ENABLED:
        return False, '[SIMULADO] ligação não realizada — CALL_E_ENABLED=false'
    if not (CALL_E_API_URL and CALL_E_API_KEY):
        return False, 'CALL-E não configurado'
    response = requests.post(
        CALL_E_API_URL,
        headers={'Authorization': f'Bearer {CALL_E_API_KEY}', 'Content-Type': 'application/json'},
        json={'phone': phone, 'script': CALL_SCRIPT.format(nome=nome)},
        timeout=30,
    )
    if 200 <= response.status_code < 300:
        return True, f'ligação disparada: {response.text[:200]}'
    return False, f'erro CALL-E {response.status_code}: {response.text[:300]}'


def render_email(template_key, nome):
    template = EMAIL_TEMPLATES[template_key]
    return template['subject'].format(nome=nome), template['body'].format(nome=nome)


def process():
    require_env()
    now = date.today()
    stats = {'pendente': 0, 'contatado': 0, 'followup1': 0, 'followup2': 0, 'skipped': 0, 'errors': 0}

    for record in list_active_records():
        fields = record.get('fields', {})
        status = fields.get('Status')
        nome = fields.get('Nome do Negócio') or 'seu negócio'
        email = fields.get('Email') or ''
        phone = fields.get('Telefone') or ''

        try:
            if status == 'Pendente':
                if not email and not phone:
                    append_note(record, 'Sem canal de contato. Aguardando enriquecimento manual.')
                    stats['skipped'] += 1
                    continue
                subject, body = render_email('email_1', nome)
                ok, msg = send_email(email, subject, body)
                update_record(record['id'], {
                    'Status': 'Contatado',
                    'Data Primeiro Contato': today_iso(),
                    'Data Último Contato': today_iso(),
                })
                append_note(record, f'Primeiro contato: {msg}')
                stats['pendente'] += 1

            elif status == 'Contatado':
                first_contact = parse_date(fields.get('Data Primeiro Contato'))
                if not first_contact or (now - first_contact).days < 3:
                    stats['skipped'] += 1
                    continue
                subject, body = render_email('email_2', nome)
                ok, msg = send_email(email, subject, body)
                update_record(record['id'], {'Status': 'Follow-up 1', 'Data Último Contato': today_iso()})
                append_note(record, f'Follow-up 1: {msg}')
                stats['contatado'] += 1

            elif status == 'Follow-up 1':
                last_contact = parse_date(fields.get('Data Último Contato'))
                if not last_contact or (now - last_contact).days < 3:
                    stats['skipped'] += 1
                    continue
                ok, msg = run_call(phone, nome)
                update_record(record['id'], {'Status': 'Follow-up 2', 'Data Último Contato': today_iso()})
                append_note(record, f'Follow-up 2 ligação: {msg}')
                stats['followup1'] += 1

            elif status == 'Follow-up 2':
                last_contact = parse_date(fields.get('Data Último Contato'))
                if not last_contact or (now - last_contact).days < 2:
                    stats['skipped'] += 1
                    continue
                subject, body = render_email('email_3', nome)
                ok, msg = send_email(email, subject, body)
                update_record(record['id'], {'Status': 'Perdido', 'Data Último Contato': today_iso()})
                append_note(record, f'Contato final: {msg}')
                stats['followup2'] += 1

        except Exception as exc:
            stats['errors'] += 1
            append_note(record, f'ERRO no worker: {exc}')

        time.sleep(0.25)

    print(f'[{datetime.now().isoformat()}] Worker concluído: {stats}')
    if stats['errors'] > 0:
        raise SystemExit(1)


if __name__ == '__main__':
    process()
