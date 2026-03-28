# UFL Fox Sports PBP App

Public app for turning a Fox Sports UFL game URL into:

- a play-by-play CSV
- an ambiguity report CSV

## Local Run

```powershell
pip install -r requirements.txt
streamlit run app.py
```

For fresh roster pulls on every run, set a Google service-account credential before launching the app.

Example local environment variable:

```powershell
$env:GOOGLE_SERVICE_ACCOUNT_JSON = Get-Content 'C:\path\to\service-account.json' -Raw
streamlit run app.py
```

## Deploy Publicly

The easiest path is Streamlit Community Cloud.

1. Push this folder to GitHub.
2. Create a new Streamlit app pointed at `app.py`.
3. Add a Streamlit secret named `google_service_account` with the full service-account JSON fields.
4. Make sure `requirements.txt` and `Sample CSV.csv` are included in the repo.

Users will then be able to:

1. paste a Fox Sports UFL game URL
2. click `Generate CSVs`
3. download the play-by-play CSV and ambiguity report
