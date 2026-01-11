# Portfolio-case: Grundskoleförvaltning Göteborg (syntetisk data)

**Syfte:** Träna Power BI, statistik och ML på ett realistiskt kommunalt scenario.  
All data är **syntetisk** (inte verklig) men konstruerad för att *likna* verkliga mönster.

## Dataset (CSV)
1) skollokaler_facilities.csv – lokaler/fastigheter per skola  
2) elever_students.csv – elever per skola och år (stadier, andelar, avstånd, merit)  
3) personal_staff.csv – personal per skola och år (FTE, pendling, sjukfrånvaro, omsättning)  
4) ekonomi_economy.csv – ekonomi per skola och år (drift, personal, kostnad/elev)  
5) prognosbarn_0_5_forecast.csv – barn 0–5 per stadsdel och år (prognos)  
6) prognos_forvantade_entrants_F.csv – förväntade nya elever (F) per stadsdel och år  
7) scenarios_skolstruktur.csv – nedläggning/sammanslagning (scenario A/B + baseline)  
8) ml_ready_school_year.csv – ML-tabell med features + targets (nästa år)

## Rekommenderad Power BI-modell
- Dimensioner: School (från facilities), District, Year (datumtabell)
- Fakta: elever_students, personal_staff, ekonomi_economy
- Prognos: prognosbarn_0_5_forecast, prognos_forvantade_entrants_F
- Scenarier: scenarios_skolstruktur (använd som slicer/filter)

## Power BI-övningar (förslag)
- Beläggningsgrad = Enrolled_Students / Max_Capacity_Students
- Kostnad per elev (trend + jämförelse mellan skolor/stadsdelar)
- Merit vs personalomsättning/sjukfrånvaro
- Underhållsskuld per kvm vs byggår
- Scenarioanalys: visa kapacitet efter sammanslagning (what-if via scenario-tabell)

## ML-övningar (förslag)
- Regression: Target_Operating_Cost_MSEK_NextYear
- Regression: Target_Merit_Score_Grade9_NextYear
- Klassificering: Target_Teacher_Shortage_Flag_NextYear (eller sannolikhet)

## Praktik/Jobb-berättelse (case-ram)
1) **Problem:** Elevkullar ändras → över/underkapacitet, budgetpress, personalbrist i vissa områden.  
2) **Mål:** Förbättra planering för lokaler och personal med datadrivna scenarier och prognoser.  
3) **Leverans:** Power BI-rapport + scenarioverktyg + ML-prototyp för tidig varning.  
4) **Resultat (syntetiskt):** Identifiera skolor med risk för överkapacitet och sannolik lärarbrist.

> Not: Alla samband är konstruerade för övning och ska inte tolkas som verkliga kausala effekter.
