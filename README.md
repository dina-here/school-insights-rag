# SkolAnalys - School Data Analysis Platform

SkolAnalys är en AI-driven plattform för analys av skoldata. Den använder RAG (Retrieval Augmented Generation) med PostgreSQL + pgvector för vektor-sökning och OpenAI/Gemini för att ge insikter baserade på faktiska skoldata. Gemini styrs via feature flaggen `ENABLE_GEMINI` och är avstängd som standard.

🚀 **Live Demo:** https://school-insights-rag.onrender.com/

## Projektöversikt

 Projektet transformerar skoldata (CSV-filer) till användbara insikter genom:
- **Data Ingest**: Laddar upp CSV-data till PostgreSQL med pgvector-embeddings. CSV-struktur/kolumnnamn kan bytas ut mot verkliga data så länge filerna ligger i `data/` och har header-rad; innehållet chunktas som fri text, så modellen kan hantera andra kolumner utan schemaändring.
- **Semantic Search**: Hämtar relevant data baserat på användarfrågor via pgvector
- **AI Analysis**: Använder OpenAI som standard och Gemini när `ENABLE_GEMINI=true`
- **Web Interface**: Användarvänligt gränssnitt för att interagera med analysen
- **SQL Aggregation**: Direkt SQL för distriktsnivå-analyser (genomsnitt, trender)

### Vad är pgvector?

**pgvector** är en PostgreSQL-extension som lagrar och söker vektorer (embeddings) effektivt. När data ingestas:
1. CSV-rader delas in i **chunks** (små textblock, default 10 rader per chunk)
2. Varje chunk embeddas via OpenAI som standard, eller Gemini om `ENABLE_GEMINI=true` → blir en vektor som normaliseras till projektets pgvector-dimension (default 768)
3. Vektorn lagras i PostgreSQL med pgvector
4. Vid sökning: användarfrågan embeddas → söks mot alla vektorer via cosine distance
5. De mest relevanta chunks returneras för AI-analys

**Fördelarna:**
- ✅ Gratis PostgreSQL på Render
- ✅ Vektorer lagras lokalt, ingen extern tjänst
- ✅ Möjliggör hybrid-sökning: vektorer + SQL-aggregation
- ✅ Bättre kontroll över chunking-strategi

## Installationssteg

### 1. Förutsättningar
- Python 3.10+
- PostgreSQL (lokalt eller Render)
- OpenAI API-nyckel
- Google Gemini API-nyckel (valfritt, endast om `ENABLE_GEMINI=true`)

### 2. Installera beroenden

```bash
pip install -r requirements.txt
```

Detta installerar:
- `fastapi` & `uvicorn` - Web server
- `google-genai` - Gemini chat och embeddings när feature flaggen är på
- `openai` - Chat och embeddings
- `psycopg2-binary` - PostgreSQL driver
- `python-dotenv` - Environment variables

### 3. Ställ in miljövariabler

Skapa en `.env`-fil i projektrotmappen:

```env
ENABLE_GEMINI=false
GEMINI_API_KEY=din-gemini-api-nyckel
OPENAI_API_KEY=din-openai-api-nyckel
DATABASE_URL=postgresql://user:password@localhost/skolanalys_db
SYSTEM_PROMPT_PATH=system_prompt.txt
EMBED_DIM=768
```

Använd `ENABLE_GEMINI=false` för OpenAI-only. Sätt `ENABLE_GEMINI=true` för att aktivera Gemini igen.

**Lokalt PostgreSQL-setup:**
```bash
# Windows (med PostgreSQL installerat)
createdb skolanalys_db
createuser skolanalys_user
# Uppdatera .env med: DATABASE_URL=postgresql://skolanalys_user:password@localhost/skolanalys_db
```

### 4. Förbered PostgreSQL-databas

```bash
python setup_postgres.py
```

Detta skapar:
- `vector` extension (pgvector)
- `school_embeddings` tabell med vektor-index

### 5. Förbered och ladda upp CSV-data

CSV-filerna ska ligga i `data/`-mappen:

```
data/
├── prognos.csv    # förväntade entrants
└── grundskoleforvaltning_goteborg_syntetisk_data.csv  # samlad skoldata
```

Ladda upp data till PostgreSQL:

```bash
# Ladda upp alla filer
python ingest_school_data_postgres.py data/

```

**Vad ingestionen gör:**
1. Läser CSV-fil
2. Delar upp i chunks (5 rader per chunk)
3. Embeddar varje chunk med OpenAI eller Gemini beroende på `ENABLE_GEMINI`
4. Lagrar i PostgreSQL med vektor-index


## Köra applikationen

### Lokal utveckling
```bash
uvicorn app:app --reload --port 8000
```

Öppna då: http://localhost:8000

### Render/Produktion
Se `RENDER_DEPLOY.md` för deployment-instruktioner.

Kort sammanfattning:
1. Skapa PostgreSQL-databas på Render
2. Push kod till GitHub
3. Skapa Web Service på Render
4. Länka till GitHub repo
5. Ange environment variables

## API Endpoints

- `GET /` - Webbgränssnitt (chat UI)
- `POST /chat` - Chat API
  - Input: `{"message": "Din fråga", "history": []}`
  - Output: `{"reply": "AI-svar med kilder"}`
- `GET /health` - Health check
- `GET /metrics.json` - JSON-statistik
- `GET /metrics.txt` - Plaintext-statistik

## Projektstruktur

```
SkolAnalys/
├── app.py                              # FastAPI-applikation
├── rag_backend_postgres.py             # RAG-logik med PostgreSQL + pgvector
├── ingest_school_data_postgres.py      # CSV-ingestscript för PostgreSQL
├── setup_postgres.py                   # Initialisera PostgreSQL (pgvector extension)
├── reset_and_ingest.py                 # Reset databas och ladda om data
├── system_prompt.txt                   # AI:s instruktioner och fokusområden
├── requirements.txt                    # Python-beroenden
├── render.yaml                         # Render deployment-config
├── RENDER_DEPLOY.md                    # Detaljerad Render deployment-guide
├── static/
│   └── index.html                      # Web UI (chat-gränssnitt)
├── data/                               # CSV-datafiler
└── README.md                           # Du är här
```

## Funktionalitet

### CSV-data som stöds

1. **Samlad skoldata**: `grundskoleforvaltning_goteborg_syntetisk_data.csv`
   - 30 skolor × 4 år (2022-2025)
   - Kolumner: elevantal, inskriving, lärar-ratio, underhål, kostnader, etc.
   - Stöder district-nivå aggregation (Hisingen, Sydväst, Centrum, Västra)

2. **Prognoser**: `prognos.csv`
   - Förväntade nya elever (2026-2033)

### Exempel på analysfrågor

- "Vad är enrollmenttrendet i Centrum-distriktet?"
- "Vilka skolor har högst underhållsbehov?"
- "Genomsnitt elever med invandrare bakgrund bland Hisingen skolorna?"
- "Vilka är de ekonomiska trenderna per elev?"
- "Vad förväntas för elevantal 2030?"
- "Vilka skolor är överbelastade?"

### RAG + SQL Aggregation

System använder två strategier:

1. **Vector RAG** (standard):
   - Läser användarfråga
   - Embeddar frågan
   - Söker mot pgvector-index
   - Returnerar topN relevanta chunks

2. **SQL Aggregation** (distrikt-frågor):
   - Detekterar om fråga handlar om specifik distrikt + "genomsnitt"/"ratio"
   - Kör direct SQL på grundskoleforvaltning_data
   - Aggregerar över alla skolor + år
   - Returnerar exakta genomsnitt utan vector-approximation

## Environment-variabler

| Variabel | Beskrivning | Obligatorisk |
|----------|-------------|------------|
| `ENABLE_GEMINI` | Slår på/av Gemini (`true`/`false`) | Nej (default: `false`) |
| `GEMINI_API_KEY` | Google Gemini API-nyckel | Nej, men krävs om `ENABLE_GEMINI=true` |
| `OPENAI_API_KEY` | OpenAI API-nyckel för chat och embeddings | Ja för standardläget och som fallback |
| `DATABASE_URL` | PostgreSQL connection string | Ja |
| `EMBED_DIM` | Embedding dimension (pgvector) | Nej (default: 768) |
| `SYSTEM_PROMPT_PATH` | Path till system prompt | Nej (default: system_prompt.txt) |

## Felsökning

### "DATABASE_URL not found"
- Kontrollera att `DATABASE_URL` är satt i `.env`
- Format: `postgresql://user:password@host/dbname`

### "pgvector extension not found"
- Kör `python setup_postgres.py` för att skapa extension

### Inga resultat från sökning
- Säkerställ att data är inladdat genom att kontrollera databasen
- Kontrollera chunking-resultatet
- Prova en enklare söksträng

### OpenAI API-fel
- Kontrollera att `OPENAI_API_KEY` är korrekt satt
- Verifiera quota/billing i OpenAI-kontot
- Kör om ingestion eller chat när nyckeln fungerar igen

### Gemini API-fel
- Kontrollera att `ENABLE_GEMINI=true`
- Kontrollera att `GEMINI_API_KEY` är korrekt satt
- Om Gemini fallerar används OpenAI som fallback när `OPENAI_API_KEY` finns

### Chunking-problem (få resultat)
- Standard: `chunk_size=10` rader per chunk
- För fler chunks: sänk chunk_size i `ingest_school_data_postgres.py`
- Re-ingestning krävs: delete data + re-ingest

## Utveckling

### Lägg till nya CSV-filer
1. Placera CSV-fil i `data/`-mappen
2. Kör: `python ingest_school_data_postgres.py "data/min_fil.csv"`

### Anpassa chunking
I `ingest_school_data_postgres.py`, ändra:
```python
chunks = create_chunks_from_csv(filepath, filename, chunk_size=5)  # fler chunks
```



## Deployment

### Lokal + Render samtidigt
- **Lokal**: `uvicorn app:app --port 8000` → http://localhost:8000
- **Render**: Se `RENDER_DEPLOY.md` → https://skolanalys-api.onrender.com

Båda använder samma PostgreSQL-databas på Render, så data är synkroniserad.

## Support & Kontakt

Se `system_prompt.txt` för mer information om systemets instruktioner och fokusområden.

## Licens

Internt projekt för skolanalys

### CSV-data som stöds


