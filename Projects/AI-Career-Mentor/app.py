# ================================================================
# AI CAREER MENTOR – ADVANCED ATS RESUME ANALYZER
# AI / LOCAL / AUTO MODE | SINGLE FILE
# ================================================================

import streamlit as st
import pypdf
import io
import time
import re

# ================================================================
# 🔑 API KEY (OPTIONAL)
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
# TRY GEMINI
# ================================================================

ONLINE_AVAILABLE = False
try:
    if AI_API_KEY and AI_API_KEY != "PASTE_YOUR_GEMINI_API_KEY_HERE":
        import google.generativeai as genai
        genai.configure(api_key=AI_API_KEY)
        ONLINE_AVAILABLE = True
except Exception:
    ONLINE_AVAILABLE = False

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
# OFFLINE ATS ENGINE
# ================================================================

def offline_analysis(resume, job):
    r = set(tokenize(resume))
    j = set(tokenize(job))
    common = r & j

    keyword_score = int((len(common) / max(len(j), 1)) * 100)
    skills = min(100, keyword_score + 10)
    experience = min(100, keyword_score + 5)
    format_score = 75

    ats = int(
        keyword_score * 0.35 +
        skills * 0.30 +
        experience * 0.20 +
        format_score * 0.15
    )

    missing = list(j - r)[:12]

    return {
        "mode": "🟡 Local Analysis (Offline)",
        "ats": ats,
        "breakdown": {
            "Keyword Match": keyword_score,
            "Skills Alignment": skills,
            "Experience Relevance": experience,
            "Format & Structure": format_score
        },
        "missing": missing,
        "recommendations": [
            "Add missing job-specific keywords naturally.",
            "Quantify achievements using numbers.",
            "Use strong action verbs.",
            "Align resume language with job description.",
            "Remove irrelevant or outdated content."
        ]
    }

# ================================================================
# ONLINE GEMINI ENGINE
# ================================================================

def online_analysis(resume, job):
    prompt = f"""
You are an ATS resume expert.

START EXACTLY WITH:
ATS Score: [NUMBER]%

Resume:
{resume[:4000]}

Job Description:
{job[:2500]}

Provide:
- ATS Score
- Score Breakdown
- Missing Keywords
- Resume Improvement Recommendations
"""

    for model_name in ["gemini-2.5-flash", "gemini-2.5-pro"]:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            if "quota" in str(e).lower() or "resource" in str(e).lower():
                raise RuntimeError("QUOTA")
            continue

    raise RuntimeError("FAILED")

# ================================================================
# SESSION STATE
# ================================================================

if "page" not in st.session_state:
    st.session_state.page = "upload"
    st.session_state.resume = None
    st.session_state.job = None
    st.session_state.mode = "auto"
    st.session_state.result = None
    st.session_state.offline = None
    st.session_state.used_mode = None

# ================================================================
# UPLOAD PAGE
# ================================================================

def upload_page():
    st.markdown("## 🤖 AI Career Mentor")
    st.markdown("### Optimize your resume for ATS & recruiters")

    resume = st.file_uploader("📄 Upload Resume (PDF)", type=["pdf"])
    job = st.text_area("📋 Paste Job Description", height=200)

    st.markdown("### 🧠 Choose Analysis Mode")

    mode = st.radio(
        "Select how you want to analyze:",
        ["Auto (Recommended)", "AI Model (Online)", "Local Analysis (Offline)"]
    )

    mode_map = {
        "Auto (Recommended)": "auto",
        "AI Model (Online)": "online",
        "Local Analysis (Offline)": "offline"
    }

    if st.button("🚀 Analyze Resume", use_container_width=True):
        if not resume or len(job.strip()) < 50:
            st.error("Upload resume and provide valid job description.")
            return

        resume_text = extract_pdf_text(resume)
        if not resume_text:
            st.error("Unable to read resume.")
            return

        st.session_state.resume = resume_text
        st.session_state.job = job
        st.session_state.mode = mode_map[mode]
        st.session_state.page = "analyzing"
        st.rerun()

# ================================================================
# ANALYZING PAGE
# ================================================================

def analyzing_page():
    st.markdown("## 🔍 Analyzing Resume")
    bar = st.progress(0)

    for i in [20, 40, 60, 80]:
        time.sleep(0.3)
        bar.progress(i)

    mode = st.session_state.mode

    # ONLINE ONLY
    if mode == "online":
        if not ONLINE_AVAILABLE:
            st.error("Online AI not available.")
            st.session_state.page = "upload"
            return
        try:
            st.session_state.result = online_analysis(
                st.session_state.resume,
                st.session_state.job
            )
            st.session_state.used_mode = "🟢 AI Model (Gemini)"
            st.session_state.page = "result"
            st.rerun()
        except RuntimeError:
            st.error("Gemini quota exceeded.")
            st.session_state.page = "upload"
            return

    # AUTO MODE
    if mode == "auto" and ONLINE_AVAILABLE:
        try:
            st.session_state.result = online_analysis(
                st.session_state.resume,
                st.session_state.job
            )
            st.session_state.used_mode = "🟢 AI Model (Gemini)"
            st.session_state.page = "result"
            st.rerun()
        except RuntimeError:
            pass

    # OFFLINE
    offline = offline_analysis(
        st.session_state.resume,
        st.session_state.job
    )
    st.session_state.offline = offline
    st.session_state.used_mode = offline["mode"]
    st.session_state.page = "result"
    st.rerun()

# ================================================================
# RESULT PAGE
# ================================================================

def result_page():
    st.markdown("## ✅ ATS Analysis Report")
    st.caption(f"Mode Used: {st.session_state.used_mode}")

    if st.session_state.offline:
        data = st.session_state.offline

        st.metric("ATS Score", f"{data['ats']}%")
        st.progress(data["ats"] / 100)

        cols = st.columns(4)
        for i, (k, v) in enumerate(data["breakdown"].items()):
            cols[i].metric(k, f"{v}%")

        st.markdown("### ❌ Missing Keywords")
        st.write(", ".join(data["missing"]))

        st.markdown("### ✅ Resume Optimization Recommendations")
        for r in data["recommendations"]:
            st.write("•", r)

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
