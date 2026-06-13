# Platforma — Railway'ga joylash

## Environment variables (Railway > Variables):
- BOT_TOKEN      : BotFather bergan token
- BASE_URL       : Railway bergan domen (masalan https://platforma-production.up.railway.app)
- WEBHOOK_SECRET : ixtiyoriy maxfiy so'z (masalan o'zingiz o'ylab topgan uzun matn)
- DB_PATH        : /data/platforma.db   (Volume ulangach)

## Start buyrug'i (Procfile'da bor):
uvicorn main:app --host 0.0.0.0 --port $PORT
