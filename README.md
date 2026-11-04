# 📄 ATS Resume Checker

Upload a resume (PDF, DOCX or TXT) and get an **ATS score out of 100** at the top, followed by improvements, missing keywords and strengths. Optionally paste a job description for a role-specific score. Built with Streamlit and Gemini Flash.

## Run locally
```bash
git clone https://github.com/<your-username>/ats-resume-checker.git
cd ats-resume-checker
pip install -r requirements.txt
```

Get a free API key from [Google AI Studio](https://aistudio.google.com/apikey), then either:

- set it: `export GEMINI_API_KEY="your-key"` (Windows PowerShell: `$env:GEMINI_API_KEY="your-key"`), or
- paste it into the app's sidebar when it opens.

```bash
streamlit run app.py
```

## Deploy on Streamlit Community Cloud
1. Push this repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **Create app**, pick your repo, branch `main`, main file `app.py`.
4. In **Advanced settings → Secrets**, add: `GEMINI_API_KEY = "your-key"`
5. Click **Deploy**.

## Notes
- Never commit your API key.
- To change the model, edit `MODEL` at the top of `app.py`.
- Scanned or image-only PDFs have no readable text; use a text-based PDF or DOCX.
- The score is an AI estimate. Real ATS systems differ.
- Resume text is sent to Google's Gemini API for analysis.# CV-collection
