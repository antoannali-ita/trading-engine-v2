# Fineco Alert -> WhatsApp

Modulo temporaneo e isolato dentro `trading-engine-v2`. Legge le email Fineco non lette da Gmail e inoltra su WhatsApp solo i dati essenziali tramite CallMeBot.

## Flusso

Fineco -> Gmail -> IMAP -> parser -> CallMeBot -> WhatsApp

## Filtri

- mittente default: `service@finecobank.com`
- oggetto contenente: `Alert da FinecoBank`
- vengono considerate solo email `UNSEEN`
- la mail viene marcata come letta solo dopo un invio WhatsApp riuscito

## Secrets riutilizzati dal repository

Il modulo usa i secrets già documentati nel repository:

- `GMAIL_SENDER`
- `GMAIL_PASSWORD` (Gmail App Password)
- `WHATSAPP_NUMBER`
- `CALLMEBOT_APIKEY`

Non sono necessarie nuove credenziali se questi quattro secrets sono già presenti e validi.

## Output WhatsApp

Esempio:

```
🚨 FINECO ALERT

SPGI | NYSE
💵 Prezzo: 432
🕐 27/08/2026 22:48:01

Alert Fineco scattato. Verificare il titolo prima di operare.
```

## Esecuzione

Workflow: `.github/workflows/fineco_whatsapp_alerts.yml`

- manuale con `workflow_dispatch`
- automatica ogni 5 minuti tramite GitHub Actions

Il modulo non contiene logica BUY/SELL e non modifica il motore di trading. In futuro può essere spostato in un repository dedicato copiando la cartella e il workflow.
