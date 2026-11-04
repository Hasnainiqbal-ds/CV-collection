import io
import json
import os
import re
import time

import streamlit as st
from docx import Document
from google import genai
from google.genai import types
from pypdf import PdfReader

# Main model first, backup second. Edit these if Google renames models.
MODELS = ["gemini-3.8-flash", "gemini-3.6-flash"]

st.set_page_config(page_title="ATS Resume Checker", page_icon="📄")


def read_resume(file) -> str:
    """Return the text of a PDF, DOCX or TXT file."""
    name = file.name.lower()
    data = file.getvalue()
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if name.endswith(".docx"):
        doc = Document(io.BytesIO(data))
        lines = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                lines += [cell.text for cell in row.cells]
        return "\n".join(line for line in lines if line.strip())
    return data.decode("utf-8", errors="ignore").strip()


def get_api_key() -> str:
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return os.environ.get("GEMINI_API_KEY", "")


def ask_gemini(client, prompt: str, config):
    """Call Gemini. If it is busy (503), retry, then try the backup model."""
    for model in MODELS:
        for attempt in range(3):
            try:
                return client.models.generate_content(
                    model=model, contents=prompt, config=config
                )
            except Exception as e:
                busy = any(w in str(e) for w in ("503", "UNAVAILABLE", "overloaded", "high demand"))
                if not busy:
                    raise
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
    raise RuntimeError("Gemini is very busy right now. Please wait a minute and try again.")


def analyze(resume: str, job: str, api_key: str) -> dict:
    if job:
        job_part = "Compare it with this job description:\n" + job[:8000]
    else:
        job_part = "No job description was given."

    prompt = f"""You are an ATS (Applicant Tracking System) expert. Review this resume honestly.
{job_part}

RESUME:
{resume[:20000]}

Reply with ONLY valid JSON in this exact shape:
{{
  "score": 0,
  "summary": "2 short sentences",
  "improvements": ["specific fix 1", "specific fix 2"],
  "missing_keywords": ["keyword"],
  "strengths": ["strength"]
}}
"score" is an integer from 0 to 100 (ATS-friendliness: keywords, formatting, clear sections, measurable results).
Give 5 to 8 improvements, most important first."""

    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        temperature=0.2, response_mime_type="application/json"
    )
    response = ask_gemini(client, prompt, config)
    text = re.sub(r"^```(?:json)?|```$", "", (response.text or "").strip()).strip()
    data = json.loads(text)

    try:
        score = max(0, min(100, round(float(data.get("score", 0)))))
    except (TypeError, ValueError):
        score = 0
    return {
        "score": score,
        "summary": str(data.get("summary", "")),
        "improvements": [str(x) for x in data.get("improvements", [])],
        "missing_keywords": [str(x) for x in data.get("missing_keywords", [])],
        "strengths": [str(x) for x in data.get("strengths", [])],
    }


def show(result: dict) -> None:
    score = result["score"]
    color = "green" if score >= 75 else "orange" if score >= 50 else "red"
    st.header("Your ATS Score")
    st.markdown(f"# :{color}[{score} / 100]")
    st.progress(score / 100)
    st.write(result["summary"])

    st.subheader("Improvements")
    for i, item in enumerate(result["improvements"], 1):
        st.write(f"{i}. {item}")

    if result["missing_keywords"]:
        st.subheader("Missing keywords")
        st.write(", ".join(result["missing_keywords"]))

    if result["strengths"]:
        st.subheader("Strengths")
        for item in result["strengths"]:
            st.write(f"- {item}")


st.title("📄 ATS Resume Checker")

api_key = get_api_key()
if not api_key:
    api_key = st.sidebar.text_input("Gemini API key", type="password")

file = st.file_uploader("Upload your resume", type=["pdf", "docx", "txt"])
job = st.text_area("Job description (optional)", height=120)

if st.button("Analyze", type="primary", disabled=file is None):
    if not api_key:
        st.error("Please enter your Gemini API key in the sidebar.")
    else:
        try:
            text = read_resume(file)
            if len(text) < 100:
                st.error("Not enough text found. Scanned or image PDFs can't be read - upload a text PDF or DOCX.")
            else:
                with st.spinner("Analyzing..."):
                    st.session_state["result"] = analyze(text, job.strip(), api_key)
        except Exception as e:
            st.session_state.pop("result", None)
            st.error(f"Something went wrong: {e}")

if "result" in st.session_state:
    show(st.session_state["result"])
