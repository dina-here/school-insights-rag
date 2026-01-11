# SkolAnalys - School Data Analysis Platform

SkolAnalys är en AI-driven plattform för analys av skoldata. Den använder RAG (Retrieval Augmented Generation) med PostgreSQL + pgvector för vektor-sökning och Gemini/OpenAI AI för att ge insikter baserade på faktiska skoldata.

## Projektöversikt

Projektet transformerar skoldata (CSV-filer) till användbara insikter genom:
- **Data Ingest**: Laddar upp CSV-data till PostgreSQL med pgvector-embeddings
- **Semantic Search**: Hämtar relevant data baserat på användarfrågor via pgvector
- **AI Analysis**: Använder Gemini/OpenAI för att analysera och presentera insikter
- **Web Interface**: Användarvänligt gränssnitt för att interagera med analysen
- **SQL Aggregation**: Direkt SQL för distriktsnivå-analyser (genomsnitt, trender)

### Vad är pgvector?

**pgvector** är en PostgreSQL-extension som lagrar och söker vektorer (embeddings) effektivt. När data ingestas:
1. CSV-rader delas in i **chunks** (små textblock, default 10 rader per chunk)
2. Varje chunk embeddas via Gemini API → blir en vektor (768-dimensionell vektor)
3. Vektorn lagras i PostgreSQL med pgvector
4. Vid sökning: användarfrågan embeddas → söks mot alla vektorer via cosine distance
5. De mest relevanta chunks returneras för AI-analys

**Fördelarna:**
- ✅ Gratis PostgreSQL på Render (ingen Pinecone-kostnad)
- ✅ Vektorer lagras lokalt, ingen extern tjänst
- ✅ Möjliggör hybrid-sökning: vektorer + SQL-aggregation
- ✅ Bättre kontroll över chunking-strategi

## Installationssteg

### 1. Förutsättningar
- Python 3.10+
- PostgreSQL (lokalt eller Render)
- Google Gemini API-nyckel
- OpenAI API-nyckel (valfritt, som fallback)

### 2. Installera beroenden

```bash
pip install -r requirements.txt
```

Detta installerar:
- `fastapi` & `uvicorn` - Web server
- `google-genai` - Gemini embeddings
- `psycopg2-binary` - PostgreSQL driver
- `python-dotenv` - Environment variables

### 3. Ställ in miljövariabler

Skapa en `.env`-fil i projektrotmappen:

```env
GEMINI_API_KEY=din-gemini-api-nyckel
OPENAI_API_KEY=din-openai-api-nyckel (optional)
DATABASE_URL=postgresql://user:password@localhost/skolanalys_db
SYSTEM_PROMPT_PATH=system_prompt.txt
EMBED_DIM=768
```

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
├── prognosbarn_0_5_forecast.csv          # Prognos för barn 0-5 år
├── skollokaler_facilities.csv            # Skolanläggningar och kapacitet
├── elever_students.csv                   # Elevdata per skola
├── personal_staff.csv                    # Personaldata
├── ekonomi_economy.csv                   # Ekonomiska nyckeltal
├── scenarios_skolstruktur.csv            # Konsolideringsscenarier
├── prognos_forvantade_entrants_F.csv    # Förväntade entrants
└── grundskoleforvaltning_goteborg_syntetisk_data.csv  # Göteborg skoldata
```

Ladda upp data till PostgreSQL:

```bash
# Ladda upp alla filer
python ingest_school_data_postgres.py data/

# Eller en specifik fil
python ingest_school_data_postgres.py "data/elever_students.csv"
```

**Vad ingestionen gör:**
1. Läser CSV-fil
2. Delar upp i chunks (10 rader per chunk)
3. Embeddar varje chunk med Gemini
4. Lagrar i PostgreSQL med vektor-index

**Verifiera ingestningen:**
```bash
python check_db_file_presence.py elever_students.csv
```

## Köra applikationen

### Lokal utveckling
```bash
# Terminal 1: Starta PostgreSQL (om lokalt)
# (redan igång på Render)

# Terminal 2: Starta FastAPI
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
├── check_db_file_presence.py           # Verifiera vilka filer är ingestade
├── sql_aggregator.py                   # SQL-aggregation för distriktsnivå-frågor
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

1. **Göteborg skoldata**: `grundskoleforvaltning_goteborg_syntetisk_data.csv`
   - 30 skolor × 4 år (2022-2025)
   - Kolumner: elevantal, inskriving, lärar-ratio, underhål, kostnader, etc.
   - Stöder district-nivå aggregation (Hisingen, Sydväst, Centrum, Västra)

2. **Prognos för barn (0-5)**: `prognosbarn_0_5_forecast.csv`
   - Befolkningsprognoser per distrikt och år

3. **Skolanläggningar**: `skollokaler_facilities.csv`
   - Byggnad, område, kapacitet, underhållsbehov, energi

4. **Elevdata**: `elever_students.csv`
   - Inskriving, betyg, särskilda behov, bakgrund

5. **Personal**: `personal_staff.csv`
   - Lärare, support, sjukfrånvaro, turnover

6. **Ekonomi**: `ekonomi_economy.csv`
   - Kostnader, budget per elev, driftskostnader

7. **Scenarier**: `scenarios_skolstruktur.csv`
   - Konsolideringsplaner och alternativ

8. **Prognoser**: `prognos_forvantade_entrants_F.csv`
   - Förväntade nya elever

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
| `GEMINI_API_KEY` | Google Gemini API-nyckel | Ja |
| `OPENAI_API_KEY` | OpenAI API-nyckel (fallback) | Nej |
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
- Säkerställ att data är inladdat: `python check_db_file_presence.py elever_students.csv`
- Kontrollera chunking-resultatet
- Prova en enklare söksträng

### Gemini API-fel (quota slut)
- Free tier har daglig begränsning
- OpenAI används som fallback om konfigurerad
- Vänta till nästa dag eller uppgradera till Gemini paid

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

### Lägg till ny distrikt-aggregation
Lägg till i `sql_aggregator.py`:
```python
districts = ["Hisingen", "Sydväst", "Centrum", "Västra", "NY_DISTRIKT"]
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

1. **Prognos för barn (0-5)**: Befolkningsprognoser per distrikt och år
2. **Skolanläggningar**: Byggnad, område, kapacitet, underhållsbehov
3. **Elevdata**: Inskriving, betyg, särskilda behov, background
4. **Personal**: Lärare, support, sjukfrånvaro, turnover
5. **Ekonomi**: Kostnader, budget per elev
6. **Scenarier**: Konsolideringsplaner och alternativ
7. **Prognoser**: Förväntade nya elever

### Exempel på analysfrågor

- "Vad är enrollmenttrendet i Centrum-distriktet?"
- "Vilka skolor har högst underhållsbehov?"
- "Hur är kapacitetsanvändningen på skolorna?"
- "Vilka är de ekonomiska trenderna per elev?"
- "Vad förväntas för elevantal 2030?"

## Environment-variabler

| Variabel | Beskrivning | Obligatorisk |
|----------|-------------|------------|
| `GEMINI_API_KEY` | Google Gemini API-nyckel | Ja |
| `OPENAI_API_KEY` | OpenAI API-nyckel (fallback) | Nej |
| `PINECONE_API_KEY` | Pinecone API-nyckel | Ja |
| `PINECONE_INDEX_HOST` | Pinecone index host | Ja |
| `PINECONE_NAMESPACE` | Namespace i Pinecone | Nej (default: skolanalys) |
| `EMBED_DIM` | Embedding dimension | Nej (default: 768) |
| `SYSTEM_PROMPT_PATH` | Path till system prompt | Nej (default: system_prompt.txt) |

## Felsökning

### Data läds inte in
- Kontrollera att CSV-filer är i `data/`-mappen
- Verifiera Pinecone API-nyckeln
- Kontrollera loggarna för embedding-fel

### Gemini API-fel
- Verifiera GEMINI_API_KEY
- OpenAI fungerar som fallback om konfigurerad
- Kontrollera API-quotor

### Inga resultat från sökning
- Säkerställ att data är inladdat i Pinecone
- Kontrollera namespace setting (`skolanalys`)
- Prova en enklare söksträng

## Utveckling

### Lägg till nya CSV-filer
1. Placera CSV-fil i `data/`-mappen
2. Lägg till filnamn i `csv_files`-listan i `ingest_school_data.py`
3. Kör `python ingest_school_data.py data/`

### Anpassa systemprompten
Redigera `system_prompt.txt` för att ändra AI:s beteende och fokusarea.

### Lägg till ny analys-typ
Se `rag_backend.py` och `app.py` för hur sökning och AI-analys integreras.

## Support & Kontakt

Se `system_prompt.txt` för mer information om systemets instruktioner och fokusområden.

## Licens

Internt projekt för skolanalys
