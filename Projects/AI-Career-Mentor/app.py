# ================================================================
# AI CAREER MENTOR – ADVANCED ATS RESUME ANALYZER
# FULL REWRITE MODE: Generates brand new single-column ATS PDF 
# Extracts & includes original user photo if present.
# ================================================================

import streamlit as st
import pypdf
import pymupdf
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from PIL import Image
import io
import time
import re
import random

# ================================================================
# 🔑 API KEY (OPTIONAL)
# ================================================================
AI_API_KEY = st.secrets.get("GEMINI_API_KEY", "AIzaSyCr5dU330YZd6zCC4g2fvHXleAqHGXni9U") if hasattr(st, "secrets") else "AIzaSyCr5dU330YZd6zCC4g2fvHXleAqHGXni9U"

# ================================================================
# PAGE CONFIG
# ================================================================
st.set_page_config(page_title="AI Career Mentor", page_icon="🤖", layout="wide")

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
def extract_pdf_text_from_bytes(pdf_bytes):
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            if page.extract_text():
                text += page.extract_text() + "\n"
        return text.strip()
    except Exception:
        return None

def extract_profile_image(pdf_bytes):
    """Scans the PDF for the first image (usually a profile photo) and extracts it."""
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        for page in doc:
            images = page.get_images(full=True)
            if images:
                xref = images[0][0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                
                # Convert to standard PNG using PIL to ensure compatibility with FPDF
                img = Image.open(io.BytesIO(image_bytes))
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='PNG')
                return img_byte_arr.getvalue()
    except Exception:
        pass
    return None

def tokenize(text):
    return re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())

def sanitize_for_fpdf(text):
    """Replaces smart quotes and removes characters FPDF (latin-1) cannot handle."""
    text = text.replace('”', '"').replace('“', '"').replace('’', "'").replace('‘', "'").replace('–', '-')
    return text.encode('latin-1', 'ignore').decode('latin-1')

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

    ats = int(keyword_score * 0.35 + skills * 0.30 + experience * 0.20 + format_score * 0.15)
    missing = list(j - r)[:12]

    return {
        "mode": "🟡 Local Analysis (Offline)",
        "ats": ats,
        "missing": missing,
        "recommendations": [
            "Use standard headings: 'Work Experience', 'Education', 'Skills'.",
            "Spell out acronyms next to short forms.",
            "Start each bullet point with a strong action verb.",
            "Use a single-column layout."
        ]
    }

# ================================================================
# ONLINE GEMINI ENGINE - FULL REWRITE
# ================================================================
def rewrite_resume_online(resume_text, job_desc, missing_keywords, extra_info=""):
    missing_str = ", ".join(missing_keywords[:10]) if missing_keywords else "(none)"
    
    prompt = f"""
You are an expert ATS Resume Writer. Your task is to rewrite the entire resume provided below from scratch.

STRICT ATS RULES:
1. Format: Output clean, plain text. Use Markdown `##` for main sections, and `*` for bullet points. Do NOT create tables, columns, or charts.
2. Headings: You MUST use exactly these standard headings: "Work Experience", "Education", "Skills", "Summary".
3. Acronyms: Write out acronyms next to short forms (e.g., Search Engine Optimization (SEO)).
4. Verbs: Start every bullet point under Work Experience with a strong action verb.
5. Quantify: Add numbers and results to show success IF supported by the context.
6. Keywords: Naturally integrate these missing keywords from the job post: {missing_str}
7. Integrity: Do NOT invent fake experience. Only use the original resume and the user's extra context.

User's Additional Context (Integrate this into the new resume): 
{extra_info if extra_info else "None provided."}

Original Resume:
{resume_text[:4000]}

Job Description:
{job_desc[:2000]}

Begin the rewritten resume now:
"""
    for model_name in ["gemini-2.5-flash", "gemini-2.5-pro"]:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception:
            continue
    raise RuntimeError("Failed to generate text online.")

# ================================================================
# PDF GENERATOR
# ================================================================
def create_ats_pdf(text, image_bytes=None):
    """Generates a strict, single-column ATS-friendly PDF."""
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # 1. Add Profile Photo if extracted
    if image_bytes:
        try:
            pdf.image(io.BytesIO(image_bytes), x=10, y=10, w=30)
            pdf.ln(35) # Add space below the image
        except Exception:
            pass # Skip image if it fails to render

    # 2. Add Text
    for line in text.split("\n"):
        clean_line = sanitize_for_fpdf(line.strip())
        
        if clean_line.startswith("## "): # Section Heading
            pdf.set_font("Arial", style="B", size=12)
            pdf.ln(4)
            pdf.multi_cell(0, 6, clean_line.replace("## ", ""), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Arial", size=11)
            pdf.ln(1)
        elif clean_line.startswith("# "): # Name/Main Title
            pdf.set_font("Arial", style="B", size=14)
            pdf.multi_cell(0, 7, clean_line.replace("# ", ""), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Arial", size=11)
            pdf.ln(2)
        elif clean_line.startswith("* ") or clean_line.startswith("- "): # Bullet points
            pdf.set_font("Arial", size=11)
            # Indent bullets slightly
            pdf.set_x(15)
            pdf.multi_cell(0, 6, chr(149) + " " + clean_line[2:], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        elif clean_line: # Standard text
            pdf.set_font("Arial", size=11)
            pdf.multi_cell(0, 6, clean_line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        else:
            pdf.ln(3) # Empty lines

    return bytes(pdf.output())

# ================================================================
# SESSION STATE INIT
# ================================================================
if "page" not in st.session_state:
    st.session_state.update({
        "page": "upload", "original_resume_text": None, "original_pdf_bytes": None, 
        "profile_image": None, "job": None, "mode": "auto", "extra_info": "", 
        "target_score": 90, "rounds_used": 0, "generated_pdf_bytes": None, 
        "current_resume_text": None
    })

# ================================================================
# CALLBACKS
# ================================================================
def add_skill_to_draft(skill, widget_key):
    phrases = [
        f"Successfully implemented {skill} to streamline operations.",
        f"Leveraged {skill} to deliver high-quality project outcomes.",
        f"Proficient in using {skill} for complex problem-solving."
    ]
    phrase = random.choice(phrases)
    current_val = st.session_state.get(widget_key, "").strip()
    st.session_state[widget_key] = current_val + " " + phrase if current_val else phrase

# ================================================================
# PAGES
# ================================================================
def upload_page():
    st.markdown("## 🤖 AI Career Mentor")
    resume = st.file_uploader("📄 Upload Resume (PDF)", type=["pdf"])
    job = st.text_area("📋 Paste Job Description", height=200)

    if st.button("🚀 Analyze Resume", use_container_width=True):
        if resume and len(job.strip()) > 50:
            pdf_bytes = resume.getvalue()
            extracted_text = extract_pdf_text_from_bytes(pdf_bytes)
            extracted_image = extract_profile_image(pdf_bytes)
            
            st.session_state.update({
                "original_resume_text": extracted_text,
                "current_resume_text": extracted_text,
                "original_pdf_bytes": pdf_bytes,
                "profile_image": extracted_image,
                "job": job,
                "page": "analyzing"
            })
            st.rerun()

def analyzing_page():
    st.markdown("## 🔍 Analyzing Resume")
    bar = st.progress(0)
    for i in [30, 60, 100]: time.sleep(0.3); bar.progress(i)
    
    st.session_state.offline = offline_analysis(st.session_state.current_resume_text, st.session_state.job)
    st.session_state.page = "result"
    st.rerun()

def result_page():
    st.markdown("## ✅ ATS Analysis Report")
    st.metric("Current ATS Score", f"{st.session_state.offline['ats']}%")
    st.markdown("### ❌ Missing Keywords")
    st.write(", ".join(st.session_state.offline["missing"]))
    st.divider()

    st.markdown("### 🛠️ Completely Rebuild & Fix Resume")
    st.caption("We will extract your content (and photo) and generate a brand-new, strictly formatted, single-column ATS document.")
    st.session_state.target_score = st.slider("🎯 Target ATS Score", 50, 98, 90)
    
    if st.button("✅ Yes, rebuild my resume", type="primary", use_container_width=True):
        st.session_state.page = "fixing"
        st.rerun()

def fixing_page():
    st.markdown("## 🛠️ Rebuilding Resume from Scratch...")
    
    missing = st.session_state.offline["missing"]
    
    # AI Generation
    new_text = rewrite_resume_online(
        st.session_state.original_resume_text, 
        st.session_state.job, 
        missing, 
        st.session_state.extra_info
    )
    
    # PDF Creation
    new_pdf_bytes = create_ats_pdf(new_text, st.session_state.profile_image)
    
    # Re-analyze new text
    new_score_data = offline_analysis(new_text, st.session_state.job)
    
    st.session_state.generated_pdf_bytes = new_pdf_bytes
    st.session_state.current_resume_text = new_text
    st.session_state.fixed_score = new_score_data
    st.session_state.rounds_used += 1
    
    if new_score_data["ats"] < st.session_state.target_score:
        st.session_state.page = "need_more_info"
    else:
        st.session_state.page = "fixed_result"
    st.rerun()

def need_more_info_page():
    st.markdown("## ⚠️ Target Not Reached Yet")
    st.warning(f"We reached **{st.session_state.fixed_score['ats']}%**, but your target is **{st.session_state.target_score}%**.")
    st.write("We need more context from you to safely add the remaining missing keywords:")
    
    missing_skills = st.session_state.fixed_score["missing"]
    st.write("**" + ", ".join(missing_skills) + "**")
    
    st.divider()
    st.markdown("💡 **Click a missing skill to instantly add a professional bullet point:**")
    
    widget_key = f"draft_new_info_{st.session_state.rounds_used}"
    
    cols = st.columns(min(len(missing_skills), 6))
    for i, skill in enumerate(missing_skills[:6]):
        with cols[i]:
            st.button(f"➕ {skill}", key=f"btn_{skill}_{st.session_state.rounds_used}", 
                      on_click=add_skill_to_draft, args=(skill, widget_key))
                
    new_info = st.text_area(
        "Edit your added experience here (we will integrate this into the next rebuild):", 
        key=widget_key, 
        height=100
    )
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Use Info & Rebuild Again", type="primary", use_container_width=True):
            st.session_state.extra_info += "\n" + new_info
            st.session_state.page = "fixing"
            st.rerun()
    with col2:
        if st.button("⏹️ Stop & Get My Resume Now", use_container_width=True):
            st.session_state.page = "fixed_result"
            st.rerun()

def fixed_result_page():
    st.markdown("## ✅ Brand New ATS Resume Generated")
    new_score = st.session_state.fixed_score["ats"]
    st.metric("New ATS Score", f"{new_score}%", delta=f"{new_score - st.session_state.offline['ats']}%")
    
    pdf_bytes = st.session_state.generated_pdf_bytes
    
    try:
        preview_doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        st.markdown("### 📄 Visual Preview (All Pages)")
        num_pages = len(preview_doc)
        cols = st.columns(min(num_pages, 3)) 
        for i in range(num_pages):
            pix = preview_doc[i].get_pixmap(dpi=110)
            cols[i % 3].image(pix.tobytes("png"), use_container_width=True, caption=f"Page {i + 1}")
        preview_doc.close()
    except Exception:
        pass

    st.download_button("⬇️ Download ATS Resume", data=pdf_bytes, file_name="ATS_Optimized_Resume.pdf", mime="application/pdf", use_container_width=True, type="primary")
    if st.button("🔄 Start Over"):
        st.session_state.clear()
        st.rerun()

# ================================================================
# ROUTER
# ================================================================
pages = {"upload": upload_page, "analyzing": analyzing_page, "result": result_page, 
         "fixing": fixing_page, "need_more_info": need_more_info_page, "fixed_result": fixed_result_page}
pages[st.session_state.page]()
