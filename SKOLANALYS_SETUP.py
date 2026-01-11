#!/usr/bin/env python3
"""
Instruktioner för att sätta upp och köra SkolAnalys-projektet
"""

SETUP_STEPS = """
📚 SKOLANALYS - SETUP INSTRUKTIONER
====================================

DU ÄR INTE KLAR! Följ dessa steg för att aktivera projektet:

1. KOPIERA CSV-FILER TIL DATA-MAPPEN
   - Skapa mapp: data/
   - Kopiera dessa CSV-filer dit:
     * prognosbarn_0_5_forecast.csv
     * skollokaler_facilities.csv
     * elever_students.csv
     * personal_staff.csv
     * ekonomi_economy.csv
     * scenarios_skolstruktur.csv
     * prognos_forvantade_entrants_F.csv

2. INSTALLERA DEPENDENCIES
   pip install -r requirements.txt

3. LADDA UPP DATA TILL PINECONE
   python ingest_school_data.py data/
   
   Detta kommer att:
   - Läsa alla CSV-filer från data/-mappen
   - Generera embeddings med Google Gemini
   - Ladda upp till Pinecone under namespace "skolanalys"
   
4. STARTA APPLIKATIONEN
   uvicorn app:app --reload --host 0.0.0.0 --port 8000
   
5. ÖPPNA I WEBBROWSER
   http://localhost:8000

MILJÖVARIABLER (.env filen)
===========================

Säkerställ att dessa är konfigurerade:

GEMINI_API_KEY=<din-gemini-api-key>
OPENAI_API_KEY=<din-openai-api-key>  # Valfritt
PINECONE_API_KEY=<din-pinecone-api-key>
PINECONE_INDEX_HOST=<din-pinecone-host>
PINECONE_NAMESPACE=skolanalys
SYSTEM_PROMPT_PATH=system_prompt.txt
EMBED_DIM=768

VAD HAR ÄNDRATS FÖN HR → SKOLANALYS?
=======================================

✅ Kodändringar:
   - rag_backend.py: get_hr_policy() → get_school_analysis()
   - app.py: "HR Policy Assistant API" → "School Analysis API"
   - Pinecone namespace: "hr" → "skolanalys"
   
✅ Ny ingestfil:
   - ingest_school_data.py (ersätter ingest_hr_docs.py)
   - Läser CSV-filer istället för PDF-dokument
   
✅ Webb-gränssnitt (index.html):
   - Färgschema: Blå/grön skolaffär (cyan: #0ea5e9)
   - Titel: "📚 SkolAnalys - School Data Analysis and Insights"
   - Avatar: "SA" istället för "HR"
   - Exempel-frågor fokuserade på skolanalys
   
✅ Systemprompt:
   - Ny fokus: Skolanalys istället för HR-policy
   - Nya analysområden: Enrollment, kapacitet, personal, ekonomi
   - Nya fallback-svar anpassade för skolkontext

✅ Dependencies:
   - pandas 2.0.3 tillagd (ersätter pypdf)
   - För effektiv CSV-bearbetning

TESTFRÅGOR DU KAN STÄLLA
==========================

- "Vad är enrollmenttrendet i Centrum-distriktet?"
- "Vilka skolor har högst underhållsbehov?"
- "Hur många elever förväntas 2030?"
- "Vilka skolor är överbelastade?"
- "Vad är kostnaden per elev?"
- "Vilka distrikts växer snabbast?"

NÄSTA STEG
===========

1. Skapa data/-mappen och kopiera CSV-filerna
2. Kör: python ingest_school_data.py data/
3. Verifiera att data laddades till Pinecone
4. Starta app: uvicorn app:app --reload
5. Testa webgränssnittet på http://localhost:8000

Se README_SKOLANALYS.md för mer detaljerad information!
"""

if __name__ == "__main__":
    print(SETUP_STEPS)
