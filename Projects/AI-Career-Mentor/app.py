# ================================================================
# AI CAREER MENTOR – ADVANCED ATS RESUME ANALYZER
# AI / LOCAL / AUTO MODE | SINGLE FILE
# Now with: consent-based auto-fix + PDF export of fixed resume
# ================================================================

import streamlit as st
import pypdf
from fpdf import FPDF
import io
import time
import re

# ================================================================
# 🔑 API KEY (OPTIONAL)
# ================================================================
# ⚠️ Don't hardcode real keys in source. Use st.secrets instead:
#   AI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
# and add a .streamlit/secrets.toml (gitignored) with:
#   GEMINI_API_KEY = "your-key-here"

AI_API_KEY = st.secrets.get("GEMINI_API_KEY", "AIzaSyCr5dU330YZd6zCC4g2fvHXleAqHGXni9U") if hasattr(st, "secrets") else "AIzaSyCr5dU330YZd6zCC4g2fvHXleAqHGXni9U"

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
    except Exception:
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
# ONLINE GEMINI ENGINE — ANALYSIS
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
# ONLINE GEMINI ENGINE — FIX
# ================================================================

def fix_resume_online(resume, job):
    prompt = f"""
You are an expert resume writer helping optimize a resume for ATS systems.

Rewrite the resume below so that it:
- Naturally incorporates relevant keywords from the job description
- Uses strong action verbs and clear, concise phrasing
- Quantifies achievements with numbers/percentages where plausible
- Keeps consistent, ATS-friendly formatting (plain section headers, no tables/columns)
- Does NOT invent employers, job titles, degrees, or dates that aren't in the original

Return ONLY the rewritten resume text. No preamble, no commentary,
no markdown code fences, no "Here is your resume" type text.

Original Resume:
{resume[:4000]}

Job Description:
{job[:2500]}
"""
    for model_name in ["gemini-2.5-flash", "gemini-2.5-pro"]:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            text = (response.text or "").strip()
            if text:
                return text
        except Exception as e:
            if "quota" in str(e).lower() or "resource" in str(e).lower():
                raise RuntimeError("QUOTA")
            continue
    raise RuntimeError("FAILED")

# ================================================================
# OFFLINE FIX (fallback when no AI available)
# ================================================================

def fix_resume_offline(resume, job, missing):
    additions = ""
    if missing:
        additions = "\n\nAdditional Relevant Skills & Keywords:\n" + ", ".join(missing)

    note = (
        "\n\n---\n"
        "Note: This is a locally-generated draft (no AI model was available). "
        "For best results, manually weave the keywords above into your Experience "
        "and Skills sections, and add quantifiable achievements (numbers, %, $) "
        "using strong action verbs like 'led', 'built', 'improved', 'launched'."
    )
    return resume.strip() + additions + note

# ================================================================
# PDF GENERATION (fixed resume → downloadable PDF)
# ================================================================

def generate_pdf(text: str) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)

    for line in text.split("\n"):
        # Basic bold detection for common section headers, keeps things simple
        stripped = line.strip()
        is_heading = stripped.isupper() and 2 < len(stripped) < 60

        safe_line = stripped.encode("latin-1", "replace").decode("latin-1")

        if is_heading:
            pdf.set_font("Helvetica", style="B", size=12)
            pdf.ln(2)
            pdf.multi_cell(0, 7, safe_line)
            pdf.set_font("Helvetica", size=11)
        else:
            pdf.multi_cell(0, 6, safe_line if safe_line else " ")

    output = pdf.output(dest="S")
    # fpdf2 returns a bytearray
    return bytes(output)

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
    st.session_state.fixed_text = None
    st.session_state.fixed_score = None

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

    # OFFLINE (also always computed so we have a numeric score to fix/compare against)
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
        st.write(", ".join(data["missing"]) if data["missing"] else "None found 🎉")

        st.markdown("### ✅ Resume Optimization Recommendations")
        for r in data["recommendations"]:
            st.write("•", r)

    else:
        st.markdown(st.session_state.result)

    st.divider()

    # ---------------- CONSENT STEP ----------------
    st.markdown("### 🛠️ Want us to fix these issues automatically?")
    st.caption("We'll rewrite your resume to close keyword gaps and improve ATS readability, then give you a PDF to download.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Yes, fix my resume", type="primary", use_container_width=True):
            st.session_state.page = "fixing"
            st.rerun()
    with col2:
        if st.button("❌ No, I'll fix it myself", use_container_width=True):
            st.info("No problem — your analysis above is ready. You can start a new analysis anytime below.")

    st.divider()
    if st.button("🔄 Analyze Another Resume"):
        st.session_state.clear()
        st.rerun()

# ================================================================
# FIXING PAGE
# ================================================================

def fixing_page():
    st.markdown("## 🛠️ Fixing Your Resume")
    bar = st.progress(0)
    for i in [20, 40, 60, 80]:
        time.sleep(0.3)
        bar.progress(i)

    resume = st.session_state.resume
    job = st.session_state.job
    mode = st.session_state.mode

    fixed_text = None

    if ONLINE_AVAILABLE and mode in ("online", "auto"):
        try:
            fixed_text = fix_resume_online(resume, job)
        except Exception:
            fixed_text = None  # fall through to offline fix

    if not fixed_text:
        missing = st.session_state.offline["missing"] if st.session_state.offline else []
        fixed_text = fix_resume_offline(resume, job, missing)

    st.session_state.fixed_text = fixed_text

    # Re-score the fixed resume with the offline engine so before/after is
    # comparable on the same scale regardless of which engine did the analysis.
    st.session_state.fixed_score = offline_analysis(fixed_text, job)

    st.session_state.page = "fixed_result"
    st.rerun()

# ================================================================
# FIXED RESULT PAGE
# ================================================================

def fixed_result_page():
    st.markdown("## ✅ Resume Fixed")

    old_score = st.session_state.offline["ats"] if st.session_state.offline else None
    new_score = st.session_state.fixed_score["ats"]

    col1, col2 = st.columns(2)
    if old_score is not None:
        col1.metric("Before", f"{old_score}%")
        col2.metric("After", f"{new_score}%", delta=f"{new_score - old_score:+d}%")
    else:
        col1.metric("New ATS Score", f"{new_score}%")

    st.markdown("### 📄 Improved Resume Preview")
    st.text_area("Preview (editable before download)", key="fixed_text", height=400)

    pdf_bytes = generate_pdf(st.session_state.fixed_text)

    st.download_button(
        "⬇️ Download Improved Resume (PDF)",
        data=pdf_bytes,
        file_name="Improved_Resume.pdf",
        mime="application/pdf",
        use_container_width=True,
        type="primary"
    )

    st.divider()
    if st.button("🔄 Analyze Another Resume"):
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
elif st.session_state.page == "fixing":
    fixing_page()
elif st.session_state.page == "fixed_result":
    fixed_result_page()
