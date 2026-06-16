# Activation Guide — SiteSprint BR

## Estado atual

A automacao ja foi instalada no repositorio.

Workflows:

- Daily Lead Finder: roda todos os dias as 08:00 de Sao Paulo
- CRM Pipeline Worker: roda todos os dias as 09:00 de Sao Paulo

## Variaveis necessarias no GitHub Actions

Para a busca de leads funcionar:

- GOOGLE_PLACES_API_KEY
- AIRTABLE_TOKEN

Para email automatico no futuro:

- MS_GRAPH_TOKEN
- OUTLOOK_SEND_ENABLED=true

Para ligacao automatica no futuro:

- CALL_E_API_URL
- CALL_E_API_KEY
- CALL_E_ENABLED=true

## Modo de ativacao recomendado

### Fase 1 — Captura segura

Ativar apenas:

- GOOGLE_PLACES_API_KEY
- AIRTABLE_TOKEN

Resultado esperado:

- leads entram no Airtable
- nenhum email automatico e enviado
- nenhuma ligacao automatica e feita

### Fase 2 — Follow-up controlado

Depois de revisar a qualidade dos leads:

- ativar envio manual ou semiautomatico
- testar com 1 lead seguro

### Fase 3 — Automacao total

Somente depois de validar linguagem e entregabilidade:

- OUTLOOK_SEND_ENABLED=true
- CALL_E_ENABLED=true

## Regra de qualidade

Antes de automatizar contato real, validar pelo menos 10 leads capturados.
