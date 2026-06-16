# Quality Control — SiteSprint BR

## Objetivo

Criar uma operacao comercial enxuta, profissional e segura para prospeccao de pequenos negocios locais sem site.

## Regra principal

O cliente nunca deve ver bastidores tecnicos. Toda comunicacao deve focar em:

- confianca
- presenca profissional
- facilidade de encontrar informacoes
- WhatsApp
- localizacao
- fotos
- previa visual sem compromisso

## Modo seguro atual

O sistema esta configurado para:

- buscar leads automaticamente
- inserir leads no Airtable
- preparar follow-ups
- manter envio automatico de email desligado ate revisao final
- manter ligacoes automaticas desligadas ate configuracao final

## Por que email e ligacao comecam desligados

Para evitar disparos acidentais antes de:

- validar API keys
- validar qualidade dos leads
- validar linguagem comercial
- validar que nao ha mensagens tecnicas indo para clientes

## Criterios de lead bom

Priorizar leads com:

- nota Google igual ou acima de 4.0
- pelo menos 10 avaliacoes
- telefone disponivel
- sem site detectado
- bairro bom
- nicho com ticket medio razoavel

## Nichos prioritarios

1. Clinicas
2. Saloes e barbearias premium
3. Restaurantes bem avaliados
4. Academias boutique
5. Lojas locais com boa aparencia

## Checklist antes de ativar envio automatico

- Confirmar que leads estao entrando corretamente no Airtable
- Revisar 10 leads capturados
- Confirmar que os textos estao cliente-facing
- Confirmar identidade de remetente
- Confirmar limites de envio do Outlook
- Ativar OUTLOOK_SEND_ENABLED somente quando aprovado

## Checklist antes de ativar ligacoes

- Confirmar que telefone esta no formato correto
- Testar uma chamada interna
- Confirmar script de voz
- Confirmar registro de resultado no Airtable
- Ativar CALL_E_ENABLED somente quando aprovado
