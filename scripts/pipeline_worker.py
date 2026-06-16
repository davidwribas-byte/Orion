import os
from datetime import date, datetime

import requests

AIRTABLE_TOKEN = os.environ.get('AIRTABLE_TOKEN')
AIRTABLE_BASE_ID = os.environ.get('AIRTABLE_BASE_ID', 'appRuCvTIYcE91U8P')
AIRTABLE_TABLE_NAME = os.environ.get('AIRTABLE_TABLE_NAME', 'LEADS')
OUTLOOK_SEND_ENABLED = os.environ.get('OUTLOOK_SEND_ENABLED', 'false').lower() == 'true'
MS_GRAPH_TOKEN = os.environ.get('MS_GRAPH_TOKEN')
CALL_E_ENABLED = os.environ.get('CALL_E_ENABLED', 'false').lower() == 'true'
CALL_E_API_URL = os.environ.get('CALL_E_API_URL')
CALL_E_API_KEY = os.environ.get('CALL_E_API_KEY')

AIRTABLE_URL = f'https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}'

EMAIL_1_SUBJECT = 'Uma ideia rápida para o {nome_negocio}'
EMAIL_1_BODY = '''Olá,

Meu nome é David. Encontrei o {nome_negocio} procurando negócios em São Paulo e percebi que vocês já têm uma presença real, avaliações e clientes, mas ainda poderiam se beneficiar de um site simples e profissional.

Hoje, muita gente pesquisa no Google antes de escolher onde ir, comprar ou agendar. Quando o cliente encontra uma página clara com fotos, serviços, horários, localização e botão de WhatsApp, fica muito mais fácil confiar e entrar em contato.

Posso preparar uma prévia visual gratuita de como poderia ficar um site para o {nome_negocio}. Não tem compromisso nenhum — é só para vocês verem a ideia.

Atenciosamente,
David Waisenberg Ribas.
'''

EMAIL_2_SUBJECT = 'Re: Uma ideia rápida para o {nome_negocio}'
EMAIL_2_BODY = '''Olá,

Passando só para ver se minha mensagem anterior chegou bem.

A ideia é simples: mostrar como o {nome_negocio} poderia aparecer com uma página profissional, com informações claras, fotos, localização e botão direto para WhatsApp.

Se quiserem, posso enviar uma primeira prévia visual sem custo.

Atenciosamente,
David Waisenberg Ribas.
'''

EMAIL_3_SUBJECT = 'Re: {nome_negocio}'
EMAIL_3_BODY = '''Olá,

Não quero tomar mais o seu tempo, então esta será minha última mensagem.

Caso em algum momento vocês queiram ver uma ideia visual de site para o {nome_negocio}, é só responder este e-mail.

Desejo muito sucesso ao negócio de vocês.

Atenciosamente,
David Waisenberg Ribas.
'''

CALL_SCRIPT = '''Olá, boa tarde. Poderia falar com o responsável pelo {nome_negocio}?

Meu nome é David. Estou entrando em contato porque vi o {nome_negocio} e achei que vocês poderiam se beneficiar de uma página profissional simples, com fotos, informações principais, localização e botão direto para WhatsApp.

A ideia é deixar o negócio mais fácil de encontrar e mais confiável para quem pesquisa antes de escolher.

Eu posso enviar uma prévia visual sem compromisso para vocês verem como ficaria. Qual seria o melhor contato para mandar?'''


def require_env():
    missing = []
    for key in ['AIRTABLE_TOKEN']:
        if not os.environ.get(key):
            missing.append(key)
    if missing:
        raise RuntimeError('Missing required environment variables: ' + ', '.join(missing))


def headers():
    return {'Authorization': f'Bearer {AIRTABLE_TOKEN}', 'Content-Type': 'application/json'}


def today_iso():
    return date.today().isoformat()


def parse_date(value):
    if not value:
        return None
    return datetime.strptime(value[:10], '%Y-%m-%d').date()


def list_records():
    records = []
    offset = None
    while True:
        params = {'pageSize': 100}
        if offset:
            params['offset'] = offset
        r = requests.get(AIRTABLE_URL, headers=headers(), params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        records.extend(data.get('records', []))
        offset = data.get('offset')
        if not offset:
            return records


def update_record(record_id, fields):
    r = requests.patch(f'{AIRTABLE_URL}/{record_id}', headers=headers(), json={'fields': fields, 'typecast': True}, timeout=30)
    r.raise_for_status()
    return r.json()


def append_note(record, text):
    current = record.get('fields', {}).get('Notas', '')
    stamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    new_note = (current + '\n' if current else '') + f'[{stamp}] {text}'
    update_record(record['id'], {'Notas': new_note})


def send_email(to_email, subject, body):
    if not to_email:
        return False, 'sem email no registro; usar telefone/CALL-E ou WhatsApp manual'
    if not OUTLOOK_SEND_ENABLED:
        return False, 'envio desativado por segurança; OUTLOOK_SEND_ENABLED=false'
    if not MS_GRAPH_TOKEN:
        return False, 'token Outlook ausente'
    payload = {
        'message': {
            'subject': subject,
            'body': {'contentType': 'Text', 'content': body},
            'toRecipients': [{'emailAddress': {'address': to_email}}],
        },
        'saveToSentItems': True,
    }
    r = requests.post('https://graph.microsoft.com/v1.0/me/sendMail', headers={'Authorization': f'Bearer {MS_GRAPH_TOKEN}', 'Content-Type': 'application/json'}, json=payload, timeout=30)
    if r.status_code in (200, 202):
        return True, 'email enviado'
    return False, f'erro Outlook {r.status_code}: {r.text[:300]}'


def run_call(phone, nome):
    if not phone:
        return False, 'sem telefone'
    if not CALL_E_ENABLED:
        return False, 'CALL-E desativado por segurança; CALL_E_ENABLED=false'
    if not CALL_E_API_URL or not CALL_E_API_KEY:
        return False, 'CALL-E não configurado'
    payload = {'phone': phone, 'script': CALL_SCRIPT.format(nome_negocio=nome)}
    r = requests.post(CALL_E_API_URL, headers={'Authorization': f'Bearer {CALL_E_API_KEY}', 'Content-Type': 'application/json'}, json=payload, timeout=30)
    if 200 <= r.status_code < 300:
        return True, r.text[:300]
    return False, f'erro CALL-E {r.status_code}: {r.text[:300]}'


def process():
    require_env()
    now = date.today()
    for record in list_records():
        fields = record.get('fields', {})
        status = fields.get('Status')
        nome = fields.get('Nome do Negócio', 'seu negócio')
        email = fields.get('Email', '')
        phone = fields.get('Telefone', '')

        if status == 'Pendente':
            ok, msg = send_email(email, EMAIL_1_SUBJECT.format(nome_negocio=nome), EMAIL_1_BODY.format(nome_negocio=nome))
            update_record(record['id'], {'Status': 'Contatado', 'Data Primeiro Contato': today_iso(), 'Data Último Contato': today_iso()})
            append_note(record, 'Primeiro contato preparado. ' + msg)

        elif status == 'Contatado':
            first = parse_date(fields.get('Data Primeiro Contato'))
            if first and (now - first).days >= 3:
                ok, msg = send_email(email, EMAIL_2_SUBJECT.format(nome_negocio=nome), EMAIL_2_BODY.format(nome_negocio=nome))
                update_record(record['id'], {'Status': 'Follow-up 1', 'Data Último Contato': today_iso()})
                append_note(record, 'Follow-up 1 preparado. ' + msg)

        elif status == 'Follow-up 1':
            last = parse_date(fields.get('Data Último Contato'))
            if last and (now - last).days >= 2:
                ok, msg = run_call(phone, nome)
                update_record(record['id'], {'Status': 'Follow-up 2', 'Data Último Contato': today_iso()})
                append_note(record, 'Ligação/follow-up telefônico preparado. ' + msg)

        elif status == 'Follow-up 2':
            last = parse_date(fields.get('Data Último Contato'))
            if last and (now - last).days >= 2:
                ok, msg = send_email(email, EMAIL_3_SUBJECT.format(nome_negocio=nome), EMAIL_3_BODY.format(nome_negocio=nome))
                update_record(record['id'], {'Status': 'Perdido', 'Data Último Contato': today_iso()})
                append_note(record, 'Contato final preparado. ' + msg)


if __name__ == '__main__':
    process()
