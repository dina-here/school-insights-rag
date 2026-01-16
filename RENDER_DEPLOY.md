# Render Deployment Guide - SkolAnalys

Denna guide visar hur man deployar SkolAnalys på Render med PostgreSQL + pgvector.

## Förutsättningar

1. GitHub-konto med din repo pushad
2. Render-konto (https://render.com)
3. Din lokala miljö är helt konfigurerad och fungerande

## Steg 1: Förbered GitHub

Se till att din kod är pushad till GitHub:

```bash
git add .
git commit -m "Add PostgreSQL + pgvector backend"
git push origin main
```

## Steg 2: Skapa PostgreSQL-databas på Render

1. Gå till https://dashboard.render.com
2. Klicka **"New"** → **"PostgreSQL"**
3. Fyll i:
   - **Name**: `education_department_data`
   - **Database**: `education_department_data` (eller auto-generated)
   - **Region**: **Frankfurt (EU Central)**
   - **PostgreSQL Version**: 18
   - **Storage**: 1 GB
4. Klicka **"Create Database"**
5. Vänta tills status är **"Available"** (2-3 minuter)
6. Gå till **"Info"-fliken** och kopiera **"Internal Database URL"**
7. Spara den, du behöver den senare

## Steg 3: Aktivera pgvector på databasen

Lokal terminal (från ditt projekt):

```bash
# Uppdatera .env med Render connection string
# DATABASE_URL=postgresql://user:pass@host.render.com/dbname

python setup_postgres.py
```

Detta skapar pgvector extension och `school_embeddings`-tabellen.

## Steg 4: Ladda upp data lokalt

```bash
python ingest_school_data_postgres.py data/
```

Om du bara vill testa kan du ladda en fil:
```bash
python ingest_school_data_postgres.py "data/elever_students.csv"
```

## Steg 5: Skapa Web Service på Render

1. Gå till https://dashboard.render.com
2. Klicka **"New"** → **"Web Service"**
3. Koppla till ditt GitHub-repo
4. Fyll i:
   - **Name**: `skolanalys-api`
   - **Branch**: `main`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app:app --host 0.0.0.0 --port 10000`
   - **Plan**: **Starter** (gratis)
5. Klicka **"Create Web Service"**

## Steg 6: Konfigurera Environment Variables

I Render Web Service dashboard:

1. Gå till **"Environment"** → **"Environment Variables"**
2. Lägg till följande (säkra) variabler:

```
GEMINI_API_KEY=din-gemini-api-key
OPENAI_API_KEY=din-openai-api-key
DATABASE_URL=postgresql://user:pass@host.render.com/dbname
SYSTEM_PROMPT_PATH=system_prompt.txt
EMBED_DIM=768
```

3. Klicka **"Save"**

Render kommer automatiskt att installera dependencies från `requirements.txt`.

## Steg 7: Verifiera Deployment

1. Vänta på att Web Service är deployed (2-3 minuter)
2. Du får en URL som: `https://school-insights-rag.onrender.com`
3. Testa health check: `https://school-insights-rag.onrender.com/health`
4. Öppna UI: `https://school-insights-rag.onrender.com/`

## Lokal Development

För att köra lokalt medan Render körs:

```bash
# Terminal 1: Starta uvicorn lokalt
uvicorn app:app --reload --port 8000

# Öppna http://localhost:8000
```

## Tips

- **Gemini quota**: Free tier har daglig begränsning. Vid quota slut, vänta till nästa dag eller betala för Gemini API
- **PostgreSQL gratis tier**: Expires efter 90 dagar. Uppgradera vid behov
- **Logs**: Se deployment logs i Render dashboard under "Logs"-fliken
- **Miljövariabler**: Aldrig commita `.env` till Git (redan i `.gitignore`)

## Troubleshooting

**"DATABASE_URL not found"**
- Kontrollera att `DATABASE_URL` är satt i Environment Variables på Render

**"psycopg2 import error"**
- `requirements.txt` bör innehålla `psycopg2-binary`, redan gjort

**"pgvector extension not found"**
- Kör `setup_postgres.py` lokalt för att skapa extension på din Render-databas

**504 Gateway Timeout**
- Kan bero på långsamma embeddings. Öka timeout i Render settings

## Nästa steg: Ladda upp befintlig data

Om du redan har data i PostgreSQL lokalt och vill kopiera den till Render:

```bash
# Exportera data från lokal PostgreSQL
pg_dump -Fc local_dbname > backup.dump

# Importera till Render (kräver psql)
pg_restore -h render-host -U postgres -d dbname backup.dump
```

---

**Lycka till med deployment! 🚀**

### Service Starts but 500 Errors
- Verify all environment variables are set
- Check `PINECONE_INDEX_HOST` format (no `https://`)
- Ensure Pinecone index dimension = `EMBED_DIM`

### Gemini Quota Errors
- Check API key is valid
- Monitor usage at https://ai.dev/usage
- Free tier has strict limits (0 requests/tokens when exhausted)
- **Solution**: Enable billing in [Google Cloud Console](https://console.cloud.google.com) or rely on OpenAI fallback
- With `OPENAI_API_KEY` set, system automatically switches to OpenAI when Gemini quota exceeded

### Token Costs
- App enforces limits to control costs:
  - Max 200 chars input per message
  - Max 2000 chars context from documents
  - Max 400 tokens output per response
  - Top 3 documents retrieved per query
- Monitor token usage at `/metrics.json` endpoint
- Typical cost with OpenAI fallback: ~$0.003-0.005 per query

### Slow First Request
- **Free tier issue**: Render free plan spins down after 15min inactivity
- First request "wakes" the service (~30-60s delay)
- **Solution**: Upgrade to **Starter plan or higher** to keep service always-on
- Update `plan: starter` in `render.yaml` before deploying, or change plan in Render dashboard → Settings → Plan

## Monitoring
- Render dashboard shows metrics, logs, events
- Add external monitoring (UptimeRobot, etc.)
- Set up email alerts in Render settings

## Custom Domain
1. Go to service settings → **Custom Domains**
2. Add your domain
3. Configure DNS (CNAME or A record)
4. SSL auto-configured by Render
