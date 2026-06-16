import os
import json
import time
from datetime import datetime, timezone

import requests

GOOGLE_PLACES_API_KEY = os.environ.get('GOOGLE_PLACES_API_KEY')
AIRTABLE_TOKEN = os.environ.get('AIRTABLE_TOKEN')
AIRTABLE_BASE_ID = os.environ.get('AIRTABLE_BASE_ID')
AIRTABLE_TABLE_NAME = os.environ.get('AIRTABLE_TABLE_NAME', 'LEADS')
MAX_NEW_LEADS = int(os.environ.get('MAX_NEW_LEADS', '5'))

AIRTABLE_URL = f'https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}'

NICHES = {
    'doctor': 'Clínica',
    'hair_salon': 'Salão',
    'gym': 'Academia',
    'restaurant': 'Restaurante',
    'store': 'Loja',
}

SEARCH_PLAN = [
    ('doctor', 'Itaim Bibi, São Paulo'),
    ('doctor', 'Jardins, São Paulo'),
    ('hair_salon', 'Pinheiros, São Paulo'),
    ('hair_salon', 'Moema, São Paulo'),
    ('gym', 'Higienópolis, São Paulo'),
    ('restaurant', 'Vila Olímpia, São Paulo'),
    ('restaurant', 'Brooklin, São Paulo'),
    ('store', 'Perdizes, São Paulo'),
]


def require_env():
    missing = [
        key for key in ('GOOGLE_PLACES_API_KEY', 'AIRTABLE_TOKEN', 'AIRTABLE_BASE_ID')
        if not os.environ.get(key)
    ]
    if missing:
        raise RuntimeError('Missing required environment variables: ' + ', '.join(missing))


def airtable_headers():
    return {
        'Authorization': f'Bearer {AIRTABLE_TOKEN}',
        'Content-Type': 'application/json',
    }


def airtable_escape(value):
    return (value or '').replace("'", "''")


def airtable_get(params, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.get(AIRTABLE_URL, headers=airtable_headers(), params=params, timeout=30)
            if response.status_code == 429:
                time.sleep(2 ** (attempt + 1))
                continue
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** (attempt + 1))
    return {'records': []}


def lead_exists(name, phone, place_id):
    if place_id:
        formula = "{Place ID Google}='" + airtable_escape(place_id) + "'"
        data = airtable_get({'filterByFormula': formula, 'maxRecords': 1})
        if data.get('records'):
            return True
    if phone:
        formula = "{Telefone}='" + airtable_escape(phone) + "'"
        data = airtable_get({'filterByFormula': formula, 'maxRecords': 1})
        if data.get('records'):
            return True
    if name:
        formula = "LOWER({Nome do Negócio})=LOWER('" + airtable_escape(name) + "')"
        data = airtable_get({'filterByFormula': formula, 'maxRecords': 1})
        if data.get('records'):
            return True
    return False


def search_places(place_type, area):
    url = 'https://places.googleapis.com/v1/places:searchText'
    headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': GOOGLE_PLACES_API_KEY,
        'X-Goog-FieldMask': (
            'places.id,'
            'places.displayName,'
            'places.formattedAddress,'
            'places.rating,'
            'places.userRatingCount,'
            'places.nationalPhoneNumber,'
            'places.websiteUri,'
            'places.primaryType'
        ),
    }
    body = {
        'textQuery': f'{place_type} em {area}',
        'includedType': place_type,
        'languageCode': 'pt-BR',
        'regionCode': 'BR',
        'pageSize': 20,
    }
    for attempt in range(3):
        try:
            response = requests.post(url, headers=headers, json=body, timeout=30)
            if response.status_code == 429:
                time.sleep(2 ** (attempt + 1))
                continue
            response.raise_for_status()
            return response.json().get('places', [])
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(2 ** (attempt + 1))
    return []


def score_place(place, place_type, area):
    rating = float(place.get('rating') or 0)
    reviews = int(place.get('userRatingCount') or 0)
    phone = place.get('nationalPhoneNumber') or ''
    score = 0

    if rating >= 4.6:
        score += 30
    elif rating >= 4.2:
        score += 24
    elif rating >= 3.8:
        score += 16
    elif rating >= 3.5:
        score += 8

    if reviews >= 200:
        score += 30
    elif reviews >= 100:
        score += 24
    elif reviews >= 40:
        score += 16
    elif reviews >= 10:
        score += 8

    if phone:
        score += 15
    if not place.get('websiteUri'):
        score += 15
    if place_type in ('doctor', 'hair_salon', 'gym'):
        score += 5
    if any(x in area for x in ('Jardins', 'Itaim', 'Moema', 'Vila Olímpia', 'Higienópolis')):
        score += 5
    return min(score, 100)


def priority_from_score(score):
    if score >= 80:
        return 'Alta'
    if score >= 60:
        return 'Media'
    return 'Baixa'


def channel_for_record(phone, email):
    if email:
        return 'Email'
    if phone:
        return 'Telefone'
    return 'Revisar manualmente'


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

    score = score_place(place, place_type, area)
    email = ''
    notes = (
        f'Lead capturado automaticamente em {datetime.now(timezone.utc).strftime("%Y-%m-%d")}. '
        f'Nota Google: {rating}. Avaliações: {reviews}. '
        f'Sem site identificado. Score: {score}/100. Área: {area}. '
        'Não mencionar ferramentas internas ao cliente.'
    )

    return {
        'Nome do Negócio': name,
        'Telefone': phone,
        'Email': email,
        'Nicho': NICHES[place_type],
        'Cidade/Bairro': place.get('formattedAddress') or area,
        'Status': 'Pendente',
        'Notas': notes,
        'Place ID Google': place_id,
        'Score Lead': score,
        'Prioridade': priority_from_score(score),
        'Canal Recomendado': channel_for_record(phone, email),
    }


def insert_record(fields):
    for attempt in range(3):
        try:
            response = requests.post(
                AIRTABLE_URL,
                headers=airtable_headers(),
                json={'records': [{'fields': fields}], 'typecast': True},
                timeout=30,
            )
            if response.status_code == 429:
                time.sleep(2 ** (attempt + 1))
                continue
            response.raise_for_status()
            return response.json()['records'][0]['id']
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError('Failed to insert record after retries')


def main():
    require_env()
    inserted = 0
    duplicates = 0
    scanned = 0
    rejected = 0
    created = []
    errors = []

    for place_type, area in SEARCH_PLAN:
        if inserted >= MAX_NEW_LEADS:
            break
        try:
            places = search_places(place_type, area)
        except Exception as exc:
            errors.append(f'SEARCH FAIL area={area} type={place_type}: {exc}')
            continue

        places.sort(key=lambda p: score_place(p, place_type, area), reverse=True)

        for place in places:
            if inserted >= MAX_NEW_LEADS:
                break
            scanned += 1
            record = to_airtable_record(place, place_type, area)
            if not record:
                rejected += 1
                continue
            try:
                if lead_exists(record['Nome do Negócio'], record.get('Telefone', ''), record['Place ID Google']):
                    duplicates += 1
                    continue
                record_id = insert_record(record)
                inserted += 1
                created.append(f"{record_id} | {record['Nome do Negócio']} | {record['Nicho']} | score {record['Score Lead']}")
                time.sleep(0.25)
            except Exception as exc:
                errors.append(f'INSERT FAIL {record["Nome do Negócio"]}: {exc}')
        time.sleep(0.5)

    report = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'scanned': scanned,
        'inserted': inserted,
        'duplicates': duplicates,
        'rejected': rejected,
        'created': created,
    }
    if errors:
        report['errors'] = errors
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
