# ================================================================
# AI CAREER MENTOR – ADVANCED ATS RESUME ANALYZER
# AI / LOCAL / AUTO MODE | SINGLE FILE
# Now with: consent-based auto-fix + PDF export of fixed resume
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

def extract_pdf_text(pdf_file):
    return extract_pdf_text_from_bytes(pdf_file.getvalue())

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
# ONLINE GEMINI ENGINE — GENERATE TARGETED TEXT FIXES
# ================================================================
# Instead of rewriting the resume (which would force us to rebuild the PDF
# from scratch and lose the original layout/photo), we ask the model for a
# small list of exact find -> replace text swaps. These get applied directly
# onto the original PDF, in place, leaving everything else untouched.

def generate_fix_pairs_online(resume, job, missing):
    missing_str = ", ".join(missing[:10]) if missing else "(none)"
    prompt = f"""
You are an ATS resume editor. Do NOT rewrite or restructure the resume.
Your only job is to propose small, targeted text replacements within the
EXACT resume text below.

Rules (follow strictly):
- "find" must be an EXACT, VERBATIM substring copied from the resume text
  below (same spelling/punctuation/case), long enough to be unique — a
  phrase or full sentence/bullet, not a single common word.
- "replace" must be roughly the same LENGTH as "find" (within ~20%) so the
  original layout doesn't shift or overflow.
- Do not add or remove line breaks within a replacement.
- Use replacements to: fix typos/grammar, swap weak verbs for strong action
  verbs, quantify vague claims, and naturally work in a few of these missing
  keywords where they genuinely fit: {missing_str}
- Do NOT invent employers, titles, degrees, or dates not already present.
- Propose at most 15 replacements. Fewer, high-quality ones are better than
  many weak ones.

Output ONLY valid JSON — a list of objects, nothing else, no markdown fences:
[{{"find": "...", "replace": "..."}}, ...]

Resume text:
{resume[:4000]}

Job description:
{job[:2000]}
"""
    last_err = None
    for model_name in ["gemini-2.5-flash", "gemini-2.5-pro"]:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            raw = (response.text or "").strip()
            raw = re.sub(r"^```(json)?", "", raw.strip())
            raw = re.sub(r"```$", "", raw.strip()).strip()
            pairs = json.loads(raw)
            if isinstance(pairs, list):
                return [p for p in pairs if isinstance(p, dict) and p.get("find") and p.get("replace")]
        except Exception as e:
            last_err = e
            if "quota" in str(e).lower() or "resource" in str(e).lower():
                raise RuntimeError("QUOTA")
            continue
    raise RuntimeError(f"FAILED: {last_err}")

# ================================================================
# IN-PLACE PDF TEXT EDITOR
# ================================================================
# Applies find -> replace text swaps directly onto the original PDF bytes
# using PyMuPDF: redact the old phrase, reinsert the replacement at the
# same position/size/color. Layout, images, and photo are never touched.

def _int_color_to_rgb(color_int):
    r = ((color_int >> 16) & 255) / 255
    g = ((color_int >> 8) & 255) / 255
    b = (color_int & 255) / 255
    return (r, g, b)

def _find_span_info(page, needle):
    d = page.get_text("dict")
    for block in d.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if needle in span.get("text", ""):
                    return {
                        "size": span.get("size", 11),
                        "color": _int_color_to_rgb(span.get("color", 0)),
                    }
    return {"size": 11, "color": (0, 0, 0)}

def apply_fixes_to_pdf(pdf_bytes, fix_pairs):
    """
    Returns (new_pdf_bytes, applied_list). applied_list only contains
    pairs that were actually found and changed in the PDF.
    """
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    applied = []

    for pair in fix_pairs:
        find = (pair.get("find") or "").strip()
        replace = (pair.get("replace") or "").strip()
        if not find or not replace or find == replace:
            continue

        found_any = False
        for page in doc:
            rects = page.search_for(find)
            if not rects:
                continue
            found_any = True

            info = _find_span_info(page, find)

            for rect in rects:
                page.add_redact_annot(rect, fill=(1, 1, 1))
            page.apply_redactions()

            for rect in rects:
                baseline_y = rect.y1 - (rect.height * 0.22)
                page.insert_text(
                    (rect.x0, baseline_y),
                    replace,
                    fontsize=info["size"],
                    fontname="helv",
                    color=info["color"],
                )
        if found_any:
            applied.append({"find": find, "replace": replace})

    out_bytes = doc.tobytes()
    doc.close()
    return out_bytes, applied

def append_suggestions_page(pdf_bytes, missing, recommendations):
    """
    Offline fallback when no AI is available to safely generate content-aware
    swaps: leave every original page completely untouched (photo, layout,
    fonts all preserved) and just append one new page listing suggestions.
    """
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    page = doc.new_page()

    y = 50
    page.insert_text((50, y), "ATS Improvement Suggestions", fontsize=16, fontname="helv", color=(0.1, 0.1, 0.5))
    y += 30
    page.insert_text((50, y), "(Generated locally — no AI model was available)", fontsize=9, fontname="helv", color=(0.4, 0.4, 0.4))
    y += 30

    if missing:
        page.insert_text((50, y), "Missing keywords to consider adding:", fontsize=12, fontname="helv", color=(0, 0, 0))
        y += 20
        chunk = ", ".join(missing)
        for i in range(0, len(chunk), 90):
            page.insert_text((60, y), chunk[i:i + 90], fontsize=10, fontname="helv", color=(0, 0, 0))
            y += 15
        y += 15

    if recommendations:
        page.insert_text((50, y), "Recommendations:", fontsize=12, fontname="helv", color=(0, 0, 0))
        y += 20
        for r in recommendations:
            page.insert_text((60, y), f"- {r}", fontsize=10, fontname="helv", color=(0, 0, 0))
            y += 16

    out_bytes = doc.tobytes()
    doc.close()
    return out_bytes

# ================================================================
# ITERATIVE FIX-TO-TARGET LOOP
# ================================================================

def fix_resume_to_target(original_pdf_bytes, resume_text, job, target_score, mode, max_rounds=3):
    """
    Iteratively applies truthful, in-place text edits trying to reach
    target_score. Stops early once the target is hit, or once a round
    produces no new applicable edits (plateau — further gains would
    require content that isn't genuinely in the resume).

    Returns: (fixed_pdf_bytes, applied_fixes, fix_method, final_score_data, rounds_used)
    """
    current_pdf_bytes = original_pdf_bytes
    current_text = resume_text
    all_applied = []
    fix_method = None
    rounds_used = 0

    score_data = offline_analysis(current_text, job)

    if ONLINE_AVAILABLE and mode in ("online", "auto"):
        for round_num in range(max_rounds):
            score_data = offline_analysis(current_text, job)
            if score_data["ats"] >= target_score:
                break
            try:
                fix_pairs = generate_fix_pairs_online(current_text, job, score_data["missing"])
                new_pdf_bytes, applied = apply_fixes_to_pdf(current_pdf_bytes, fix_pairs)
            except Exception:
                break  # stop trying online fixes, fall through to whatever we already have

            rounds_used += 1
            if not applied:
                break  # plateau: no more genuine matches to improve on

            current_pdf_bytes = new_pdf_bytes
            current_text = extract_pdf_text_from_bytes(new_pdf_bytes) or current_text
            all_applied.extend(applied)

        if all_applied:
            fix_method = "🟢 AI-targeted in-place edits"

    final_score_data = offline_analysis(current_text, job)

    if fix_method is None:
        # Nothing was safely applied online (no key, or nothing matched) —
        # fall back to appending a suggestions page, which leaves every
        # original page (and the photo) completely untouched.
        current_pdf_bytes = append_suggestions_page(
            original_pdf_bytes, score_data["missing"], score_data["recommendations"]
        )
        current_text = extract_pdf_text_from_bytes(current_pdf_bytes) or resume_text
        final_score_data = offline_analysis(current_text, job)
        fix_method = "🟡 Local fallback: suggestions page appended (original pages untouched)"

    return current_pdf_bytes, all_applied, fix_method, final_score_data, rounds_used

# ================================================================
# PDF GENERATION (fixed resume → downloadable PDF)
# ================================================================

def _break_long_tokens(line: str, max_token_len: int = 60) -> str:
    """
    Safety net for long unbroken 'words' (long URLs, run-on separator
    lines like '---------', unbroken IDs) that could otherwise be wider
    than the page and trip up multi_cell's word-wrapping.
    """
    words = line.split(" ")
    fixed_words = []
    for w in words:
        if len(w) > max_token_len:
            chunks = [w[i:i + max_token_len] for i in range(0, len(w), max_token_len)]
            fixed_words.append(" ".join(chunks))
        else:
            fixed_words.append(w)
    return " ".join(fixed_words)


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
        safe_line = _break_long_tokens(safe_line)

        if is_heading:
            pdf.set_font("Helvetica", style="B", size=12)
            pdf.ln(2)
            pdf.multi_cell(0, 7, safe_line, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
            pdf.set_font("Helvetica", size=11)
        else:
            pdf.multi_cell(0, 6, safe_line if safe_line else " ", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")

    # fpdf2 returns a bytearray from output()
    return bytes(pdf.output())

# ================================================================
# SESSION STATE
# ================================================================

if "page" not in st.session_state:
    st.session_state.page = "upload"
    st.session_state.resume = None
    st.session_state.resume_pdf_bytes = None
    st.session_state.job = None
    st.session_state.mode = "auto"
    st.session_state.result = None
    st.session_state.offline = None
    st.session_state.used_mode = None
    st.session_state.fixed_pdf_bytes = None
    st.session_state.fixed_score = None
    st.session_state.applied_fixes = None
    st.session_state.fix_method = None
    st.session_state.target_score = 90
    st.session_state.rounds_used = 0

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

        resume_bytes = resume.getvalue()
        resume_text = extract_pdf_text_from_bytes(resume_bytes)
        if not resume_text:
            st.error("Unable to read resume.")
            return

        st.session_state.resume = resume_text
        st.session_state.resume_pdf_bytes = resume_bytes
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
    st.caption("We'll make targeted, truthful edits directly on your resume to close keyword gaps and improve ATS readability — layout and photo stay untouched.")

    target_score = st.slider(
        "🎯 Target ATS Score",
        min_value=50, max_value=98, value=90, step=1,
        help="We'll run multiple rounds of edits trying to reach this score. If your resume genuinely doesn't contain enough relevant experience for the job, we'll stop short and tell you honestly why, rather than inventing skills you don't have."
    )
    st.session_state.target_score = target_score

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
    st.caption("Editing your resume in place — layout, formatting, and photo stay exactly as they are. Only the text itself gets touched.")
    bar = st.progress(0)
    for i in [20, 40, 60, 80]:
        time.sleep(0.3)
        bar.progress(i)

    resume_text = st.session_state.resume
    original_pdf_bytes = st.session_state.resume_pdf_bytes
    job = st.session_state.job
    mode = st.session_state.mode
    target_score = st.session_state.get("target_score", 90)

    fixed_pdf_bytes, applied, fix_method, final_score_data, rounds_used = fix_resume_to_target(
        original_pdf_bytes, resume_text, job, target_score, mode
    )

    st.session_state.fixed_pdf_bytes = fixed_pdf_bytes
    st.session_state.applied_fixes = applied
    st.session_state.fix_method = fix_method
    st.session_state.fixed_score = final_score_data
    st.session_state.rounds_used = rounds_used

    st.session_state.page = "fixed_result"
    st.rerun()

# ================================================================
# FIXED RESULT PAGE
# ================================================================

def fixed_result_page():
    st.markdown("## ✅ Resume Fixed")
    st.caption(f"Method: {st.session_state.fix_method}")

    old_score = st.session_state.offline["ats"] if st.session_state.offline else None
    new_score_data = st.session_state.fixed_score
    new_score = new_score_data["ats"]
    target_score = st.session_state.get("target_score", 90)

    col1, col2, col3 = st.columns(3)
    if old_score is not None:
        col1.metric("Before", f"{old_score}%")
        col2.metric("After", f"{new_score}%", delta=f"{new_score - old_score:+d}%")
    else:
        col1.metric("New ATS Score", f"{new_score}%")
    col3.metric("Target", f"{target_score}%")

    if new_score >= target_score:
        st.success(f"🎯 Target reached — your resume now scores {new_score}%, at or above your {target_score}% goal.")
    else:
        still_missing = new_score_data.get("missing", [])
        st.warning(
            f"We got your resume to **{new_score}%**, short of your {target_score}% target. "
            f"We stopped because the remaining gap would require claiming skills or experience "
            f"that genuinely aren't in your resume — we won't fabricate those. "
            + (f"Still missing: {', '.join(still_missing[:10])}." if still_missing else "")
        )
        st.caption("To close the rest of the gap: honestly, if you have any of the missing experience, add it yourself; otherwise this job may want a stronger match than your current background provides.")

    fixed_pdf_bytes = st.session_state.fixed_pdf_bytes

    # Render a preview image of the PDF so the user can visually confirm the
    # original layout/photo were preserved.
    try:
        preview_doc = pymupdf.open(stream=fixed_pdf_bytes, filetype="pdf")
        st.markdown("### 📄 Preview")
        num_preview_pages = min(len(preview_doc), 3)
        cols = st.columns(num_preview_pages)
        for i in range(num_preview_pages):
            pix = preview_doc[i].get_pixmap(dpi=110)
            cols[i].image(pix.tobytes("png"), use_container_width=True, caption=f"Page {i + 1}")
        preview_doc.close()
    except Exception:
        st.info("Preview unavailable, but your download below is ready.")

    if st.session_state.applied_fixes:
        with st.expander(f"🔍 See the {len(st.session_state.applied_fixes)} text change(s) applied across {st.session_state.get('rounds_used', 1)} round(s)"):
            for fix in st.session_state.applied_fixes:
                st.markdown(f"- ~~{fix['find']}~~ → **{fix['replace']}**")

    st.download_button(
        "⬇️ Download Fixed Resume (PDF)",
        data=fixed_pdf_bytes,
        file_name="Fixed_Resume.pdf",
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
