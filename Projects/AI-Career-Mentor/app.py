# ================================================================
# GEMINI
# ================================================================

import streamlit as st
import pypdf
import pymupdf
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import io
import json
import time
import re

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

    ats = int(keyword_score * 0.35 + skills * 0.30 + experience * 0.20 + format_score * 0.15)
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
            "Use strong action verbs."
        ]
    }

# ================================================================
# ONLINE GEMINI ENGINE
# ================================================================
def online_analysis(resume, job):
    prompt = f"You are an ATS resume expert.\nSTART EXACTLY WITH:\nATS Score: [NUMBER]%\n\nResume:\n{resume[:4000]}\n\nJob Description:\n{job[:2500]}\n\nProvide:\n- ATS Score\n- Score Breakdown\n- Missing Keywords\n- Resume Improvement Recommendations"
    for model_name in ["gemini-2.5-flash", "gemini-2.5-pro"]:
        try:
            model = genai.GenerativeModel(model_name)
            return model.generate_content(prompt).text
        except Exception as e:
            if "quota" in str(e).lower() or "resource" in str(e).lower(): raise RuntimeError("QUOTA")
            continue
    raise RuntimeError("FAILED")

def generate_fix_pairs_online(resume, job, missing, extra_info=""):
    missing_str = ", ".join(missing[:10]) if missing else "(none)"
    
    prompt = f"""
You are an ATS resume editor. Propose small, targeted text replacements within the EXACT resume text below.
Rules:
- "find" must be an EXACT substring from the resume (long enough to be unique).
- "replace" must be roughly the same LENGTH as "find".
- Integrate these missing keywords naturally: {missing_str}
- Do NOT invent experience unless it's supported by the User Context below.
- Output ONLY valid JSON: [{{"find": "...", "replace": "..."}}]

User's Additional Context (use this to add truthful experience): 
{extra_info if extra_info else "None provided."}

Resume text:
{resume[:4000]}

Job description:
{job[:2000]}
"""
    for model_name in ["gemini-2.5-flash", "gemini-2.5-pro"]:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            raw = re.sub(r"^```(json)?", "", (response.text or "").strip())
            raw = re.sub(r"```$", "", raw.strip()).strip()
            pairs = json.loads(raw)
            return [p for p in pairs if isinstance(p, dict) and p.get("find") and p.get("replace")]
        except Exception:
            continue
    return []

# ================================================================
# IN-PLACE PDF TEXT EDITOR & HIGHLIGHTER
# ================================================================
def _int_color_to_rgb(color_int):
    return (((color_int >> 16) & 255) / 255, ((color_int >> 8) & 255) / 255, (color_int & 255) / 255)

def _find_span_info(page, needle):
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if needle in span.get("text", ""):
                    return {"size": span.get("size", 11), "color": _int_color_to_rgb(span.get("color", 0))}
    return {"size": 11, "color": (0, 0, 0)}

def apply_fixes_to_pdf(pdf_bytes, fix_pairs):
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    applied = []

    for pair in fix_pairs:
        find, replace = (pair.get("find") or "").strip(), (pair.get("replace") or "").strip()
        if not find or not replace or find == replace: continue

        found_any = False
        for page in doc:
            rects = page.search_for(find)
            if not rects: continue
            found_any = True
            info = _find_span_info(page, find)

            for rect in rects: page.add_redact_annot(rect, fill=(1, 1, 1))
            page.apply_redactions()

            for rect in rects:
                # MARKER HIGHLIGHT ADDED HERE
                annot = page.add_highlight_annot(rect)
                annot.update()

                baseline_y = rect.y1 - (rect.height * 0.22)
                page.insert_text((rect.x0, baseline_y), replace, fontsize=info["size"], fontname="helv", color=info["color"])
        
        if found_any: applied.append({"find": find, "replace": replace})

    return doc.tobytes(), applied

# ================================================================
# ITERATIVE FIX-TO-TARGET LOOP
# ================================================================
def fix_resume_to_target(pdf_bytes, resume_text, job, target_score, mode, extra_info="", max_rounds=3):
    current_pdf_bytes, current_text = pdf_bytes, resume_text
    all_applied = []
    rounds_used = 0

    if ONLINE_AVAILABLE and mode in ("online", "auto"):
        for _ in range(max_rounds):
            score_data = offline_analysis(current_text, job)
            if score_data["ats"] >= target_score: break
            
            fix_pairs = generate_fix_pairs_online(current_text, job, score_data["missing"], extra_info)
            if not fix_pairs: break
            
            new_pdf_bytes, applied = apply_fixes_to_pdf(current_pdf_bytes, fix_pairs)
            if not applied: break

            current_pdf_bytes = new_pdf_bytes
            current_text = extract_pdf_text_from_bytes(new_pdf_bytes) or current_text
            all_applied.extend(applied)
            rounds_used += 1

    return current_pdf_bytes, all_applied, offline_analysis(current_text, job), rounds_used

# ================================================================
# SESSION STATE INIT
# ================================================================
if "page" not in st.session_state:
    st.session_state.update({
        "page": "upload", "resume": None, "resume_pdf_bytes": None, "job": None, 
        "mode": "auto", "extra_info": "", "target_score": 90, "applied_fixes": []
    })

# ================================================================
# PAGES
# ================================================================
def upload_page():
    st.markdown("## 🤖 AI Career Mentor")
    resume = st.file_uploader("📄 Upload Resume (PDF)", type=["pdf"])
    job = st.text_area("📋 Paste Job Description", height=200)
    mode = st.radio("Analysis Mode:", ["Auto (Recommended)", "AI Model (Online)", "Local Analysis (Offline)"])

    if st.button("🚀 Analyze Resume", use_container_width=True):
        if resume and len(job.strip()) > 50:
            st.session_state.update({
                "resume": extract_pdf_text_from_bytes(resume.getvalue()),
                "resume_pdf_bytes": resume.getvalue(),
                "job": job,
                "mode": {"Auto (Recommended)": "auto", "AI Model (Online)": "online", "Local Analysis (Offline)": "offline"}[mode],
                "page": "analyzing"
            })
            st.rerun()

def analyzing_page():
    st.markdown("## 🔍 Analyzing Resume")
    bar = st.progress(0)
    for i in [30, 60, 100]: time.sleep(0.3); bar.progress(i)
    
    st.session_state.offline = offline_analysis(st.session_state.resume, st.session_state.job)
    st.session_state.page = "result"
    st.rerun()

def result_page():
    st.markdown("## ✅ ATS Analysis Report")
    st.metric("ATS Score", f"{st.session_state.offline['ats']}%")
    st.markdown("### ❌ Missing Keywords")
    st.write(", ".join(st.session_state.offline["missing"]))
    st.divider()

    st.markdown("### 🛠️ Auto-Fix Resume")
    st.session_state.target_score = st.slider("🎯 Target ATS Score", 50, 98, 90)
    extra_info = st.text_area("➕ Optional: Add extra context or experience so the AI can use it to reach your target:", help="E.g., 'I used Python at my last job.'")
    
    if st.button("✅ Yes, fix my resume", type="primary", use_container_width=True):
        st.session_state.extra_info = extra_info
        st.session_state.page = "fixing"
        st.rerun()

def fixing_page():
    st.markdown("## 🛠️ Editing & Highlighting Resume...")
    pdf, applied, score_data, rounds = fix_resume_to_target(
        st.session_state.resume_pdf_bytes, st.session_state.resume, 
        st.session_state.job, st.session_state.target_score, 
        st.session_state.mode, st.session_state.extra_info
    )
    
    # Save cumulative progress
    st.session_state.resume_pdf_bytes = pdf
    st.session_state.resume = extract_pdf_text_from_bytes(pdf)
    st.session_state.applied_fixes.extend(applied)
    st.session_state.fixed_score = score_data
    
    if score_data["ats"] < st.session_state.target_score and st.session_state.mode in ("auto", "online"):
        st.session_state.page = "need_more_info"
    else:
        st.session_state.page = "fixed_result"
    st.rerun()

def need_more_info_page():
    st.markdown("## ⚠️ Target Not Reached Yet")
    st.warning(f"We reached **{st.session_state.fixed_score['ats']}%**, but your target is **{st.session_state.target_score}%**.")
    st.write("We've run out of genuine experience to match against the job description. Still missing:")
    st.write("**" + ", ".join(st.session_state.fixed_score["missing"]) + "**")
    
    new_info = st.text_area("Do you have experience with any of the missing keywords above? Add it here:")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Use Info & Try Fixing Again", type="primary", use_container_width=True):
            st.session_state.extra_info += "\n" + new_info
            st.session_state.page = "fixing"
            st.rerun()
    with col2:
        if st.button("⏹️ Stop & Get My Resume Now", use_container_width=True):
            st.session_state.page = "fixed_result"
            st.rerun()

def fixed_result_page():
    st.markdown("## ✅ Resume Fixed")
    new_score = st.session_state.fixed_score["ats"]
    st.metric("New ATS Score", f"{new_score}%", delta=f"{new_score - st.session_state.offline['ats']}%")
    
    pdf_bytes = st.session_state.resume_pdf_bytes
    
    # PREVIEW ALL PAGES
    try:
        preview_doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        st.markdown("### 📄 Visual Preview (All Pages)")
        num_pages = len(preview_doc)
        cols = st.columns(min(num_pages, 3)) # Max 3 columns wide per row
        for i in range(num_pages):
            pix = preview_doc[i].get_pixmap(dpi=110)
            cols[i % 3].image(pix.tobytes("png"), use_container_width=True, caption=f"Page {i + 1}")
        preview_doc.close()
    except Exception:
        pass

    if st.session_state.applied_fixes:
        with st.expander("🔍 View Text Replaced & Highlighted"):
            for fix in st.session_state.applied_fixes:
                st.markdown(f"- ~~{fix['find']}~~ → **{fix['replace']}**")

    st.download_button("⬇️ Download Fixed Resume", data=pdf_bytes, file_name="Fixed_Resume.pdf", mime="application/pdf", use_container_width=True, type="primary")
    if st.button("🔄 Start Over"):
        st.session_state.clear()
        st.rerun()

# ================================================================
# ROUTER
# ================================================================
pages = {"upload": upload_page, "analyzing": analyzing_page, "result": result_page, 
         "fixing": fixing_page, "need_more_info": need_more_info_page, "fixed_result": fixed_result_page}
pages[st.session_state.page]()
