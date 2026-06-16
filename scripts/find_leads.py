import os
import json
import time
import base64
from datetime import datetime, timezone

import requests

GOOGLE_PLACES_API_KEY = os.environ.get('GOOGLE_PLACES_API_KEY')
AIRTABLE_TOKEN = os.environ.get('AIRTABLE_TOKEN')
AIRTABLE_BASE_ID = os.environ.get('AIRTABLE_BASE_ID', 'appRuCvTIYcE91U8P')
AIRTABLE_TABLE_NAME = os.environ.get('AIRTABLE_TABLE_NAME', 'LEADS')
MAX_NEW_LEADS = int(os.environ.get('MAX_NEW_LEADS', '5'))

AIRTABLE_URL = f'https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}'

NICHES = {
    'restaurant': 'Restaurante',
    'hair_salon': 'Salão',
    'doctor': 'Clínica',
    'gym': 'Academia',
    'store': 'Loja',
}

SP_AREAS = [
    'Jardins, São Paulo',
    'Itaim Bibi, São Paulo',
    'Moema, São Paulo',
    'Pinheiros, São Paulo',
    'Vila Olímpia, São Paulo',
    'Perdizes, São Paulo',
    'Higienópolis, São Paulo',
    'Brooklin, São Paulo',
]


def require_env():
    missing = []
    for key in ['GOOGLE_PLACES_API_KEY', 'AIRTABLE_TOKEN']:
        if not os.environ.get(key):
            missing.append(key)
    if missing:
        raise RuntimeError('Missing required environment variables: ' + ', '.join(missing))


def airtable_headers():
    return {
        'Authorization': f'Bearer {AIRTABLE_TOKEN}',
        'Content-Type': 'application/json',
    }


def normalize_text(value):
    return (value or '').strip().lower()


def lead_exists(name, phone, place_id):
    clauses = []
    if place_id:
        clauses.append("{Place ID Google}='" + place_id.replace("'", "\\'") + "'")
    if phone:
        clauses.append("{Telefone}='" + phone.replace("'", "\\'") + "'")
    if name:
        clauses.append("LOWER({Nome do Negócio})=LOWER('" + name.replace("'", "\\'") + "')")
    if not clauses:
        return False
    formula = 'OR(' + ','.join(clauses) + ')'
    r = requests.get(AIRTABLE_URL, headers=airtable_headers(), params={'filterByFormula': formula, 'maxRecords': 1}, timeout=30)
    r.raise_for_status()
    return bool(r.json().get('records'))


def search_places(place_type, area):
    url = 'https://places.googleapis.com/v1/places:searchText'
    headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': GOOGLE_PLACES_API_KEY,
        'X-Goog-FieldMask': 'places.id,places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.nationalPhoneNumber,places.websiteUri,places.primaryType',
    }
    body = {
        'textQuery': f'{place_type} in {area}, Brazil',
        'includedType': place_type,
        'languageCode': 'pt-BR',
        'regionCode': 'BR',
        'pageSize': 20,
    }
    r = requests.post(url, headers=headers, json=body, timeout=30)
    r.raise_for_status()
    return r.json().get('places', [])


def score_place(place):
    rating = float(place.get('rating') or 0)
    reviews = int(place.get('userRatingCount') or 0)
    phone = place.get('nationalPhoneNumber') or ''
    score = 0
    if rating >= 4.5:
        score += 30
    elif rating >= 4.0:
        score += 20
    elif rating >= 3.5:
        score += 10
    if reviews >= 150:
        score += 30
    elif reviews >= 50:
        score += 20
    elif reviews >= 10:
        score += 10
    if phone:
        score += 20
    if not place.get('websiteUri'):
        score += 20
    return min(score, 100)


def to_airtable_record(place, place_type, area):
    name = (place.get('displayName') or {}).get('text') or ''
    phone = place.get('nationalPhoneNumber') or ''
    rating = float(place.get('rating') or 0)
    reviews = int(place.get('userRatingCount') or 0)
    website = place.get('websiteUri')
    place_id = place.get('id') or ''
    if not name or not place_id:
        return None
    if website:
        return None
    if rating < 3.5 or reviews < 10:
        return None
    score = score_place(place)
    notes = (
        f'Lead capturado automaticamente. Nota Google: {rating}. Avaliações: {reviews}. '
        f'Sem site identificado no Google Places. Score: {score}/100. Área: {area}. '
        'Mensagem ao cliente deve falar apenas de presença profissional, confiança, WhatsApp, mapa e prévia visual.'
    )
    return {
        'Nome do Negócio': name,
        'Telefone': phone,
        'Email': '',
        'Nicho': NICHES[place_type],
        'Cidade/Bairro': place.get('formattedAddress') or area,
        'Status': 'Pendente',
        'Notas': notes,
        'Place ID Google': place_id,
    }


def insert_record(fields):
    payload = {'records': [{'fields': fields}], 'typecast': True}
    r = requests.post(AIRTABLE_URL, headers=airtable_headers(), json=payload, timeout=30)
    r.raise_for_status()
    return r.json()['records'][0]['id']


def main():
    require_env()
    inserted = 0
    duplicates = 0
    scanned = 0
    rejected = 0
    created = []
    for area in SP_AREAS:
        for place_type in NICHES:
            if inserted >= MAX_NEW_LEADS:
                break
            try:
                for place in search_places(place_type, area):
                    scanned += 1
                    if inserted >= MAX_NEW_LEADS:
                        break
                    record = to_airtable_record(place, place_type, area)
                    if not record:
                        rejected += 1
                        continue
                    if lead_exists(record['Nome do Negócio'], record.get('Telefone', ''), record['Place ID Google']):
                        duplicates += 1
                        continue
                    rec_id = insert_record(record)
                    inserted += 1
                    created.append(f"{rec_id} | {record['Nome do Negócio']} | {record['Nicho']}")
                    time.sleep(0.2)
            except Exception as exc:
                print(f'ERROR area={area} type={place_type}: {exc}')
            time.sleep(0.5)
        if inserted >= MAX_NEW_LEADS:
            break
    print(json.dumps({
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'scanned': scanned,
        'inserted': inserted,
        'duplicates': duplicates,
        'rejected': rejected,
        'created': created,
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
