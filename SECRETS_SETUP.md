# GitHub Secrets
Create these in Settings > Secrets and variables > Actions:

- `GMAIL_SENDER`
- `GMAIL_RECIPIENT`
- `GMAIL_PASSWORD` (Gmail App Password)
- `WHATSAPP_NUMBER` = `+393474510671`
- `CALLMEBOT_APIKEY` = key obtained from CallMeBot activation
- `PORTFOLIO_POSITIONS_JSON` (optional but recommended for Portfolio Heat)

Create repository variable `TRADING_CAPITAL` when you want risk-based sizing.
Do not commit phone number or API keys into Python/YAML files.

## Fineco -> WhatsApp bridge

The temporary `fineco_alert_bridge` module reuses these existing secrets:

- `GMAIL_SENDER`
- `GMAIL_PASSWORD`
- `WHATSAPP_NUMBER`
- `CALLMEBOT_APIKEY`

No additional secrets are required if these values are already configured and valid.
