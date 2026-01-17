# -----------------------------------------------------------------
# --- AI CAREER MENTOR - ATS RESUME ANALYZER ---
# --- SINGLE FILE | SINGLE API KEY VARIABLE ---
# -----------------------------------------------------------------

import streamlit as st
import pypdf
import io
import time
import re

# -----------------------------------------------------------------
# 🔑 API KEY (CHANGE ONLY THIS LINE)
# -----------------------------------------------------------------

AI_API_KEY = "AIzaSyCyeyB_AsdFYBC1TG8Iqs21GXD1sksLWUc"

# -----------------------------------------------------------------
# --- GOOGLE GEMINI SETUP ---
# -----------------------------------------------------------------

try:
    import google.generativeai as genai
    genai.configure(api_key=AI_API_KEY)
except ImportError:
    st.set_page_config(layout="centered")
    st.title("❌ Missing Dependency")
    st.error("google-generativeai is not installed")
    st.code("pip install google-generativeai", language="bash")
    st.stop()
except Exception as e:
    st.set_page_config(layout="centered")
    st.title("❌ API Key Error")
    st.error("Invalid or missing Gemini API key")
    st.caption(str(e))
    st.stop()

# -----------------------------------------------------------------
# --- PAGE CONFIG ---
# -----------------------------------------------------------------

st.set_page_config(
    page_title="AI Career Mentor - ATS Resume Analyzer",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -----------------------------------------------------------------
# --- PDF TEXT EXTRACTION ---
# -----------------------------------------------------------------

def get_pdf_text(pdf_file):
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_file.getvalue()))
        text = ""

        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

        if not text.strip():
            st.error("❌ PDF appears to be image-based or empty.")
            return None

        with st.expander("📄 Extracted Resume Preview"):
            st.text(text[:800] + "..." if len(text) > 800 else text)

        return text

    except Exception as e:
        st.error(f"PDF Error: {e}")
        return None

# -----------------------------------------------------------------
# --- GEMINI RESPONSE HANDLER ---
# -----------------------------------------------------------------

def get_gemini_response(prompt):
    models = [
        "gemini-2.5-pro",
        "gemini-2.5-pro-latest",
        "gemini-2.5-flash",
        "gemini-2.5-flash-latest",
    ]

    for model_name in models:
        try:
            with st.spinner(f"🤖 Using {model_name}..."):
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(
                    prompt,
                    generation_config={
                        "temperature": 0.7,
                        "top_p": 0.95,
                        "top_k": 40,
                        "max_output_tokens": 2048,
                    }
                )

                if response and response.text:
                    return response.text

        except Exception:
            continue

    st.error("❌ All Gemini models failed")
    return None

# -----------------------------------------------------------------
# --- PROMPT CREATION ---
# -----------------------------------------------------------------

def create_analysis_prompt(resume_text, job_description):
    return f"""
You are an expert ATS (Applicant Tracking System) analyzer.

CRITICAL:
Start your response EXACTLY with:
ATS Score: [NUMBER]%

RESUME:
{resume_text[:4000]}

JOB DESCRIPTION:
{job_description[:2500]}

Provide:
• ATS Score
• Score Breakdown
• Key Strengths
• Critical Gaps
• Resume Improvements
• Keywords to Add
• Overall Assessment
"""

# -----------------------------------------------------------------
# --- SESSION STATE INIT ---
# -----------------------------------------------------------------

if "page" not in st.session_state:
    st.session_state.page = "upload"
    st.session_state.resume = None
    st.session_state.job = None
    st.session_state.result = None
    st.session_state.score = None

# -----------------------------------------------------------------
# --- UPLOAD PAGE ---
# -----------------------------------------------------------------

def upload_page():
    st.title("🤖 AI Career Mentor")
    st.markdown("### 📊 ATS Resume Analyzer (Gemini Edition)")

    resume_file = st.file_uploader("📄 Upload Resume (PDF)", type=["pdf"])
    job_desc = st.text_area("📋 Paste Job Description", height=200)

    if st.button("🚀 Analyze My Resume", use_container_width=True):
        if not resume_file:
            st.error("Please upload a resume PDF")
            return
        if not job_desc or len(job_desc.strip()) < 50:
            st.error("Please paste a valid job description")
            return

        resume_text = get_pdf_text(resume_file)
        if not resume_text:
            return

        st.session_state.resume = resume_text
        st.session_state.job = job_desc
        st.session_state.page = "analyzing"
        st.rerun()

# -----------------------------------------------------------------
# --- ANALYZING PAGE ---
# -----------------------------------------------------------------

def analyzing_page():
    st.title("🔍 Analyzing Resume")

    progress = st.progress(0)
    for i in [20, 40, 60, 80]:
        time.sleep(0.2)
        progress.progress(i)

    prompt = create_analysis_prompt(
        st.session_state.resume,
        st.session_state.job
    )

    result = get_gemini_response(prompt)

    if result:
        st.session_state.result = result
        match = re.search(r"ATS Score:\s*(\d+)%", result)
        if match:
            st.session_state.score = int(match.group(1))

        st.session_state.page = "result"
        st.rerun()
    else:
        st.session_state.page = "upload"
        st.error("Analysis failed")

# -----------------------------------------------------------------
# --- RESULT PAGE ---
# -----------------------------------------------------------------

def result_page():
    st.title("✅ ATS Analysis Report")

    if st.session_state.score is not None:
        st.metric("ATS Score", f"{st.session_state.score}%")
        st.progress(st.session_state.score / 100)

    st.markdown("---")
    st.markdown(st.session_state.result)

    st.markdown("---")
    if st.button("🔄 Analyze Another Resume", type="primary"):
        st.session_state.clear()
        st.rerun()

# -----------------------------------------------------------------
# --- ROUTER ---
# -----------------------------------------------------------------

if st.session_state.page == "upload":
    upload_page()
elif st.session_state.page == "analyzing":
    analyzing_page()
elif st.session_state.page == "result":
    result_page()
