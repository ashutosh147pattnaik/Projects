# -----------------------------------------------------------------
# --- AI CAREER MENTOR - OPTIMIZED FOR GOOGLE GEMINI ---
# --- (VERSION: 2.5 MODELS ONLY, NO SIDEBAR) ---
# -----------------------------------------------------------------

import streamlit as st
import pypdf
import io
import time
import re

# Try to import Google Gemini
try:
    import google.generativeai as genai
except ImportError:
    st.set_page_config(layout="centered")
    st.title("❌ Error")
    st.error("❌ google-generativeai library not found!")
    st.code("pip install google-generativeai", language="bash")
    st.stop()

# -----------------------------------------------------------------
# --- PAGE CONFIGURATION ---
# -----------------------------------------------------------------

st.set_page_config(
    page_title="AI Career Mentor - ATS Resume Analyzer",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"  # Sidebar is hidden
)

# -----------------------------------------------------------------
# --- HELPER FUNCTIONS ---
# -----------------------------------------------------------------

def get_pdf_text(pdf_file):
    """Extract text from PDF file."""
    try:
        pdf_bytes = pdf_file.getvalue()
        pdf_reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        
        text = ""
        for page_num, page in enumerate(pdf_reader.pages):
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        
        if not text.strip():
            st.error("❌ Could not extract text from PDF. The PDF might be image-based.")
            return None
        
        # Show preview
        with st.expander("📄 Preview of Extracted Resume Text", expanded=False):
            st.text(text[:800] + "..." if len(text) > 800 else text)
            st.caption(f"Total characters: {len(text)} | Words: {len(text.split())}")
        
        return text
        
    except Exception as e:
        st.error(f"❌ Error reading PDF: {e}")
        return None

def get_gemini_response(prompt):
    """Get response from Gemini (2.5 MODELS ONLY)."""
    
    models_to_try = [
        'gemini-2.5-pro',
        'gemini-2.5-pro-latest',
        'gemini-2.5-flash',
        'gemini-2.5-flash-latest',
    ]
    
    seen = set()
    models_to_try = [x for x in models_to_try if not (x in seen or seen.add(x))]
    
    last_error = None
    
    for model_name in models_to_try:
        try:
            with st.spinner(f"🤖 Using {model_name}..."):
                model = genai.GenerativeModel(model_name)
                
                generation_config = {
                    'temperature': 0.7,
                    'top_p': 0.95,
                    'top_k': 40,
                    'max_output_tokens': 2048,
                }
                
                response = model.generate_content(
                    prompt,
                    generation_config=generation_config
                )
                
                if response and hasattr(response, 'text') and response.text:
                    st.success(f"✅ Analysis completed using {model_name}")
                    return response.text
                
                if response and hasattr(response, 'candidates'):
                    for candidate in response.candidates:
                        if hasattr(candidate, 'content'):
                            parts = candidate.content.parts
                            text = ''.join([part.text for part in parts if hasattr(part, 'text')])
                            if text:
                                st.success(f"✅ Analysis completed using {model_name}")
                                return text
                
                st.warning(f"⚠️ {model_name} returned no text, trying next model...")
                
        except Exception as e:
            error_str = str(e)
            last_error = error_str
            
            if "quota" in error_str.lower():
                st.error(f"❌ API quota exceeded with {model_name}")
                st.error("Your free tier limit has been reached. Wait or upgrade your quota.")
                return None
            elif "invalid" in error_str.lower() and "api key" in error_str.lower():
                st.error(f"❌ Invalid API key")
                st.info("Please check your API key at https://aistudio.google.com/app/apikey")
                return None
            elif "404" in error_str or "not found" in error_str.lower():
                st.warning(f"⚠️ {model_name} not found or not available to your key.")
                continue
            else:
                st.warning(f"⚠️ {model_name} failed: {error_str[:100]}")
                continue
    
    st.error("❌ All 2.5 models failed to generate a response")
    if last_error:
        st.error(f"Last error: {last_error[:300]}")
    
    st.info("""
    **Troubleshooting:**
    1. Check your API key is valid and has 2.5 access.
    2. Verify you haven't exceeded quota.
    """)
    
    return None

def create_analysis_prompt(resume_text, job_description):
    """Create optimized prompt for resume analysis."""
    
    resume_excerpt = resume_text[:4000] if len(resume_text) > 4000 else resume_text
    job_excerpt = job_description[:2500] if len(job_description) > 2500 else job_description
    
    prompt = f"""You are an expert ATS (Applicant Tracking System) analyzer and career counselor with 10+ years of experience.

**CRITICAL INSTRUCTION:** Your response MUST start with this exact line:
**ATS Score: [NUMBER]%**

Replace [NUMBER] with a score between 0-100.

---

**RESUME:**
{resume_excerpt}

---

**JOB DESCRIPTION:**
{job_excerpt}

---

**YOUR TASK:**
Analyze how well this resume matches the job description and provide a comprehensive ATS report.

**FORMAT YOUR RESPONSE EXACTLY AS FOLLOWS:**

**ATS Score: [0-100]%**

**Score Breakdown:**
• Keyword Match: [0-100]%
• Skills Alignment: [0-100]%
• Experience Relevance: [0-100]%
• Format & Structure: [0-100]%

**Key Strengths:**
List 3-5 specific strengths where the resume strongly matches the job requirements.

**Critical Gaps:**
List 3-5 important skills, experiences, or keywords from the job description that are missing or weak in the resume.

**Recommended Improvements:**
Provide 5 specific, actionable bullet points the candidate should add to their resume. Make these concrete and tailored to this job.

**Keywords to Add:**
List 10-12 important keywords from the job description that should be incorporated into the resume.

**Overall Assessment:**
Write a 3-4 sentence summary with honest feedback and next steps.

Remember: START with **ATS Score: [NUMBER]%**"""

    return prompt

# -----------------------------------------------------------------
# --- SESSION STATE ---
# -----------------------------------------------------------------

if "app_state" not in st.session_state:
    st.session_state.app_state = "upload"
if "resume_text" not in st.session_state:
    st.session_state.resume_text = None
if "job_description" not in st.session_state:
    st.session_state.job_description = None
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "ats_score" not in st.session_state:
    st.session_state.ats_score = None
if "score_breakdown" not in st.session_state:
    st.session_state.score_breakdown = {}

# --- NEW: API Key state moved from sidebar ---
if "api_key" not in st.session_state:
    try:
        # Try to get from secrets first
        st.session_state.api_key = st.secrets.get("GOOGLE_API_KEY")
    except:
        st.session_state.api_key = None

if "api_configured" not in st.session_state:
    st.session_state.api_configured = False

# -----------------------------------------------------------------
# --- PAGE: API KEY INPUT ---
# -----------------------------------------------------------------

def show_api_key_page():
    """Display the page to get the user's API key."""
    st.title("🔑 Google Gemini API Setup")
    st.markdown("Please enter your Google API key to use the AI Career Mentor. This app is configured to use Gemini 2.5 models.")
    
    st.info("""
    **Get Your FREE API Key:**
    1. Go to: https://aistudio.google.com/app/apikey
    2. Click **"Create API Key"**
    3. Copy and paste below
    """)
    
    api_key = st.text_input(
        "Enter your Google API Key:", 
        type="password",
        help="Get it from https://aistudio.google.com/app/apikey"
    )
    
    if st.button("Submit API Key", use_container_width=True, type="primary"):
        if not api_key:
            st.error("Please enter a valid API key.")
        else:
            try:
                genai.configure(api_key=api_key)
                st.session_state.api_key = api_key
                st.session_state.api_configured = True
                st.success("✅ API Key configured successfully!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error configuring API key: {e}")
                st.error("Please check your key and try again.")

# -----------------------------------------------------------------
# --- PAGE: UPLOAD ---
# -----------------------------------------------------------------

def show_upload_page():
    """Display the upload and input page."""
    
    st.title("🤖 AI Career Mentor")
    st.markdown("### 📊 ATS Resume Analyzer (Gemini 2.5 Edition)")
    st.markdown("Upload your resume and job description to receive detailed ATS scoring and personalized improvement suggestions.")
    
    st.markdown("---")
    
    col1, col2 = st.columns([1, 1], gap="large")
    
    with col1:
        st.markdown("#### 📄 Step 1: Upload Your Resume")
        uploaded_file = st.file_uploader(
            "Choose a PDF file",
            type=['pdf'],
            help="Upload your resume in PDF format (text-based, not scanned image)"
        )
        
        if uploaded_file:
            st.success(f"✅ File uploaded: {uploaded_file.name}")
            file_size = len(uploaded_file.getvalue()) / 1024  # KB
            st.caption(f"File size: {file_size:.1f} KB")
    
    with col2:
        st.markdown("#### 📋 Step 2: Paste Job Description")
        job_description = st.text_area(
            "Paste the complete job posting here",
            height=200,
            placeholder="Include job title, requirements, responsibilities, qualifications, etc.",
            help="The more complete the job description, the better the analysis"
        )
        
        if job_description:
            word_count = len(job_description.split())
            st.caption(f"Word count: {word_count}")
    
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        analyze_btn = st.button(
            "🚀 Analyze My Resume",
            type="primary",
            use_container_width=True,
            help="Click to start AI-powered analysis"
        )
    
    if analyze_btn:
        if not uploaded_file:
            st.error("❌ Please upload your resume PDF first")
            return
        
        if not job_description or len(job_description.strip()) < 50:
            st.error("❌ Please paste a complete job description (at least 50 characters)")
            return
        
        with st.spinner("📖 Reading your resume..."):
            resume_text = get_pdf_text(uploaded_file)
        
        if not resume_text:
            st.error("❌ Could not extract text from the PDF. Please ensure it's not a scanned image.")
            return
        
        st.session_state.resume_text = resume_text
        st.session_state.job_description = job_description
        st.session_state.app_state = "analyzing"
        
        st.success("✅ Resume extracted successfully!")
        time.sleep(0.5)
        st.rerun()

# -----------------------------------------------------------------
# --- PAGE: ANALYZING ---
# -----------------------------------------------------------------

def show_analyzing_page():
    """Display analysis in progress."""
    
    st.title("🔍 Analyzing Your Resume...")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Resume Length", f"{len(st.session_state.resume_text)} chars")
    with col2:
        st.metric("Resume Words", len(st.session_state.resume_text.split()))
    with col3:
        st.metric("Job Desc Words", len(st.session_state.job_description.split()))
    
    st.markdown("---")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    steps = [
        ("📊 Extracting keywords from job description...", 20),
        ("🔍 Analyzing resume content...", 40),
        ("💼 Matching skills and experience...", 60),
        ("📈 Calculating ATS compatibility score...", 80),
        ("✍️ Generating personalized suggestions...", 90),
    ]
    
    for message, progress in steps:
        status_text.text(message)
        progress_bar.progress(progress)
        time.sleep(0.3)
    
    status_text.text("🤖 AI is analyzing (this may take 10-30 seconds)...")
    progress_bar.progress(95)
    
    prompt = create_analysis_prompt(
        st.session_state.resume_text,
        st.session_state.job_description
    )
    
    result = get_gemini_response(prompt)
    
    if result:
        st.session_state.analysis_result = result
        
        try:
            match = re.search(r'\*?\*?ATS Score:?\s*(\d+)\s*%', result, re.IGNORECASE)
            if match:
                st.session_state.ats_score = int(match.group(1))
        except:
            st.session_state.ats_score = None

        def parse_sub_score(pattern, text):
            try:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return int(match.group(1))
            except:
                pass
            return None
            
        st.session_state.score_breakdown = {
            "Keyword Match": parse_sub_score(r"Keyword Match:?\s*(\d+)\s*%", result),
            "Skills Alignment": parse_sub_score(r"Skills Alignment:?\s*(\d+)\s*%", result),
            "Experience Relevance": parse_sub_score(r"Experience Relevance:?\s*(\d+)\s*%", result),
            "Format & Structure": parse_sub_score(r"Format & Structure:?\s*(\d+)\s*%", result),
        }
        
        progress_bar.progress(100)
        status_text.text("✅ Analysis complete!")
        time.sleep(0.5)
        
        st.session_state.app_state = "results"
        st.rerun()
    else:
        st.session_state.app_state = "upload"
        st.error("❌ Analysis failed. Please try again.")
        
        if st.button("🔄 Back to Upload", use_container_width=True):
            st.rerun()

# -----------------------------------------------------------------
# --- PAGE: RESULTS ---
# -----------------------------------------------------------------

def show_results_page():
    """Display analysis results."""
    
    result = st.session_state.analysis_result
    ats_score = st.session_state.ats_score
    score_breakdown = st.session_state.score_breakdown
    
    st.title("✅ Your ATS Analysis Report")
    
    col1, col2 = st.columns([1, 2], gap="large")
    
    with col1:
        st.markdown("##### Overall ATS Score")
        if ats_score:
            if ats_score >= 80:
                st.success("🎉 Excellent Match!")
            elif ats_score >= 60:
                st.warning("👍 Good Match - Room for Improvement")
            elif ats_score >= 40:
                st.warning("⚠️ Fair Match - Needs Work")
            else:
                st.error("❌ Poor Match - Significant Changes Needed")
            
            st.metric("ATS Match Score", f"{ats_score}%")
            st.progress(ats_score / 100) 
        else:
            st.metric("ATS Match Score", "N/A")
            st.caption("Score not found in analysis")
    
    with col2:
        st.markdown("##### Score Breakdown (from AI)")
        
        if score_breakdown and any(score_breakdown.values()):
            cols_breakdown = st.columns(4)
            with cols_breakdown[0]:
                st.metric("Keywords", f"{score_breakdown.get('Keyword Match') or 'N/A'}" + ("%" if score_breakdown.get('Keyword Match') else ""))
            with cols_breakdown[1]:
                st.metric("Skills", f"{score_breakdown.get('Skills Alignment') or 'N/A'}" + ("%" if score_breakdown.get('Skills Alignment') else ""))
            with cols_breakdown[2]:
                st.metric("Experience", f"{score_breakdown.get('Experience Relevance') or 'N/A'}" + ("%" if score_breakdown.get('Experience Relevance') else ""))
            with cols_breakdown[3]:
                st.metric("Format", f"{score_breakdown.get('Format & Structure') or 'N/A'}" + ("%" if score_breakdown.get('Format & Structure') else ""))
        else:
            st.info("AI did not provide a detailed score breakdown.")

    st.markdown("---")
    
    st.subheader("📊 Statistical Metrics")
    
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    
    with col_m1:
        resume_words_count = len(st.session_state.resume_text.split())
        st.metric("Resume Words", resume_words_count)

    with col_m2:
        job_words_count = len(st.session_state.job_description.split())
        st.metric("Job Desc. Words", job_words_count)

    with col_m3:
        job_words_set = set(re.findall(r'\w+', st.session_state.job_description.lower()))
        resume_words_set = set(re.findall(r'\w+', st.session_state.resume_text.lower()))
        common_count = len(job_words_set.intersection(resume_words_set))
        st.metric("Common Keywords", common_count)
    
    with col_m4:
        match_rate = int((common_count / len(job_words_set)) * 100) if job_words_set else 0
        st.metric("Job Keyword Match", f"{match_rate}%")

    st.markdown("---")
    
    st.subheader("🤖 AI-Generated Analysis")
    
    with st.container():
        st.markdown(result)
    
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        report_text = f"""ATS RESUME ANALYSIS REPORT
{'=' * 50}

ATS SCORE: {ats_score if ats_score else 'N/A'}% (out of 100%)
Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}

{'=' * 50}

SCORE BREAKDOWN:
• Keyword Match: {score_breakdown.get('Keyword Match', 'N/A')}%
• Skills Alignment: {score_breakdown.get('Skills Alignment', 'N/A')}%
• Experience Relevance: {score_breakdown.get('Experience Relevance', 'N/A')}%
• Format & Structure: {score_breakdown.get('Format & Structure', 'N/A')}%

{'=' * 50}

{result}

{'=' * 50}

RESUME TEXT (First 1000 chars):
{st.session_state.resume_text[:1000]}...

JOB DESCRIPTION (First 1000 chars):
{st.session_state.job_description[:1000]}...
"""
        
        st.download_button(
            label="📥 Download Full Report",
            data=report_text,
            file_name=f"ATS_Report_{time.strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True
        )
    
    with col2:
        if st.button("📋 Copy Analysis", use_container_width=True):
            st.code(result, language=None)
            st.info("👆 Select all (Ctrl+A) and copy (Ctrl+C)")
    
    with col3:
        if st.button("🔄 Analyze Another Resume", type="primary", use_container_width=True):
            st.session_state.app_state = "upload"
            st.session_state.resume_text = None
            st.session_state.job_description = None
            st.session_state.analysis_result = None
            st.session_state.ats_score = None
            st.session_state.score_breakdown = {}
            st.rerun()

# -----------------------------------------------------------------
# --- MAIN ROUTING ---
# -----------------------------------------------------------------

# First, check if API key is configured
if not st.session_state.get("api_key") or not st.session_state.get("api_configured"):
    # Try to configure from secrets if not done
    if st.session_state.api_key and not st.session_state.api_configured:
        try:
            genai.configure(api_key=st.session_state.api_key)
            st.session_state.api_configured = True
            st.rerun() # Rerun to enter the main app logic
        except Exception as e:
            st.error(f"❌ Error configuring API key from secrets: {e}")
            st.session_state.api_key = None # Clear bad key
            show_api_key_page()
    else:
        show_api_key_page()
else:
    # API is configured, proceed with the app
    if st.session_state.app_state == "upload":
        show_upload_page()
    elif st.session_state.app_state == "analyzing":
        show_analyzing_page()
    elif st.session_state.app_state == "results":
        show_results_page()
    else:
        # Fallback
        st.session_state.app_state = "upload"
        st.rerun()
