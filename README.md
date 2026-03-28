# UFL Fox Sports PBP App

Public app for turning a Fox Sports UFL game URL into:

- a play-by-play CSV
- an ambiguity report CSV

## Local Run

```powershell
pip install -r requirements.txt
streamlit run app.py
```

## Deploy Publicly

The easiest path is Streamlit Community Cloud.

1. Push this folder to GitHub.
2. Create a new Streamlit app pointed at `app.py`.
3. Make sure `requirements.txt`, `roster_info.csv`, and `Sample CSV.csv` are included in the repo.

Users will then be able to:

1. paste a Fox Sports UFL game URL
2. click `Generate CSVs`
3. download the play-by-play CSV and ambiguity report
