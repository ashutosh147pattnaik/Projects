# ================================================================
# AI CAREER MENTOR – NEXT LEVEL ATS RESUME ANALYZER
# Gemini (Online) + Offline Fallback | Single File
# ================================================================

import streamlit as st
import pypdf
import io
import time
import re
from collections import Counter

# ================================================================
# 🔑 API KEY (OPTIONAL – USED ONLY FOR ONLINE MODE)
# ================================================================

AI_API_KEY = "AIzaSyCyeyB_AsdFYBC1TG8Iqs21GXD1sksLWUc"

# ================================================================
# PAGE CONFIG
# ================================================================

st.set_page_config(
    page_title="AI Career Mentor",
    page_icon="🤖",
    layout="wide"
)

# ================================================================
# TRY GEMINI SETUP
# ================================================================

ONLINE_MODE_AVAILABLE = False

try:
    if AI_API_KEY and AI_API_KEY != "PASTE_YOUR_GEMINI_API_KEY_HERE":
        import google.generativeai as genai
        genai.configure(api_key=AI_API_KEY)
        ONLINE_MODE_AVAILABLE = True
except Exception:
    ONLINE_MODE_AVAILABLE = False

# ================================================================
# UTILITIES
# ================================================================

def extract_pdf_text(pdf_file):
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_file.getvalue()))
        text = ""
        for page in reader.pages:
            if page.extract_text():
                text += page.extract_text() + "\n"
        return text.strip()
    except:
        return None

def tokenize(text):
    return re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())

# ================================================================
# OFFLINE ATS ENGINE (NO API)
# ================================================================

def offline_ats_analysis(resume_text, job_text):
    resume_tokens = tokenize(resume_text)
    job_tokens = tokenize(job_text)

    resume_set = set(resume_tokens)
    job_set = set(job_tokens)

    common = resume_set.intersection(job_set)

    keyword_score = int((len(common) / max(len(job_set), 1)) * 100)
    skills_score = min(100, keyword_score + 10)
    experience_score = min(100, keyword_score + 5)
    format_score = 75

    ats_score = int(
        (keyword_score * 0.35)
        + (skills_score * 0.30)
        + (experience_score * 0.20)
        + (format_score * 0.15)
    )

    missing_keywords = list(job_set - resume_set)[:12]

    recommendations = [
        "Add missing job-specific keywords naturally into experience sections.",
        "Quantify achievements using numbers (%, $, time saved).",
        "Use strong action verbs at the start of bullet points.",
        "Align resume titles and skills with job description wording.",
        "Remove irrelevant or outdated skills."
    ]

    return {
        "mode": "Offline AI Mode",
        "ats_score": ats_score,
        "breakdown": {
            "Keyword Match": keyword_score,
            "Skills Alignment": skills_score,
            "Experience Relevance": experience_score,
            "Format & Structure": format_score
        },
        "missing_keywords": missing_keywords,
        "recommendations": recommendations
    }

# ================================================================
# ONLINE GEMINI ENGINE
# ================================================================

def online_gemini_analysis(resume_text, job_text):
    models = [
        "gemini-2.5-flash",
        "gemini-2.5-pro"
    ]

    prompt = f"""
You are an expert ATS resume analyst.

Start response EXACTLY with:
ATS Score: [NUMBER]%

Resume:
{resume_text[:4000]}

Job Description:
{job_text[:2500]}

Provide:
- ATS Score
- Score Breakdown
- Missing Keywords
- Resume Improvement Recommendations
"""

    for model_name in models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            if "quota" in str(e).lower() or "resource" in str(e).lower():
                raise RuntimeError("QUOTA_EXCEEDED")
            continue

    raise RuntimeError("GEMINI_FAILED")

# ================================================================
# SESSION STATE
# ================================================================

if "page" not in st.session_state:
    st.session_state.page = "upload"
    st.session_state.resume = None
    st.session_state.job = None
    st.session_state.result = None
    st.session_state.offline_data = None
    st.session_state.mode = None

# ================================================================
# UI PAGES
# ================================================================

def upload_page():
    st.markdown("## 🤖 AI Career Mentor")
    st.markdown("### Optimize your resume for ATS & recruiters")

    st.info(
        "🟢 Online AI Mode available"
        if ONLINE_MODE_AVAILABLE
        else "🟡 Offline AI Mode will be used automatically"
    )

    resume = st.file_uploader("📄 Upload Resume (PDF)", type=["pdf"])
    job = st.text_area("📋 Paste Job Description", height=200)

    if st.button("🚀 Analyze Resume", use_container_width=True):
        if not resume or len(job.strip()) < 50:
            st.error("Upload resume and provide valid job description.")
            return

        resume_text = extract_pdf_text(resume)
        if not resume_text:
            st.error("Could not read resume.")
            return

        st.session_state.resume = resume_text
        st.session_state.job = job
        st.session_state.page = "analyzing"
        st.rerun()

def analyzing_page():
    st.markdown("## 🔍 Analyzing Your Resume")

    progress = st.progress(0)
    for i in [20, 40, 60, 80]:
        time.sleep(0.3)
        progress.progress(i)

    # Try online first
    if ONLINE_MODE_AVAILABLE:
        try:
            result = online_gemini_analysis(
                st.session_state.resume,
                st.session_state.job
            )
            st.session_state.result = result
            st.session_state.mode = "Online AI Mode"
            st.session_state.page = "result"
            st.rerun()
        except RuntimeError:
            pass

    # Fallback to offline
    offline_data = offline_ats_analysis(
        st.session_state.resume,
        st.session_state.job
    )
    st.session_state.offline_data = offline_data
    st.session_state.mode = offline_data["mode"]
    st.session_state.page = "result"
    st.rerun()

def result_page():
    st.markdown("## ✅ ATS Analysis Report")
    st.caption(f"Mode: {st.session_state.mode}")

    if st.session_state.offline_data:
        data = st.session_state.offline_data

        st.metric("ATS Score", f"{data['ats_score']}%")
        st.progress(data["ats_score"] / 100)

        cols = st.columns(4)
        for i, (k, v) in enumerate(data["breakdown"].items()):
            cols[i].metric(k, f"{v}%")

        st.markdown("### ❌ Missing Keywords")
        st.write(", ".join(data["missing_keywords"]))

        st.markdown("### ✅ Resume Optimization Recommendations")
        for rec in data["recommendations"]:
            st.write("•", rec)

    else:
        st.markdown(st.session_state.result)

    if st.button("🔄 Analyze Another Resume", type="primary"):
        st.session_state.clear()
        st.rerun()

# ================================================================
# ROUTER
# ================================================================

if st.session_state.page == "upload":
    upload_page()
elif st.session_state.page == "analyzing":
    analyzing_page()
elif st.session_state.page == "result":
    result_page()
