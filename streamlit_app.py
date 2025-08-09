import streamlit as st
import tempfile
import re
from extract_text import extract_pages
from prompt_slides import prompt_slides_from_pages
from build_ppt import build_ppt_from_slides

with st.form("ppt_form"):
    pdf_file = st.file_uploader("Upload your PDF", type=["pdf"])
    bg_file = st.file_uploader("Upload your background image", type=["png", "jpg", "jpeg"])
    submitted = st.form_submit_button("Submit")

if submitted and pdf_file and bg_file:
    st.info("Processing... please wait.")
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
        tmp_pdf.write(pdf_file.read())
        pdf_path = tmp_pdf.name
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_img:
        tmp_img.write(bg_file.read())
        bg_path = tmp_img.name

    print("Extracting pages...")
    pages = extract_pages(pdf_path)
    print(f"Page count: {len(pages)}")

    print("Calling GPT per page with continuation...")
    slides_text = prompt_slides_from_pages(pages)  # uses 1600 tokens per page call
    print("GPT (per-page) complete.")

    # Save for debugging/diff
    with open("streamlit_slides_output.txt", "w", encoding="utf-8") as f:
        f.write(slides_text)

    num = len(re.findall(r"(?m)^Slide\s*\d+\s*[–-]\s*", slides_text))
    print(f"Found {num} slide headers in LLM output")

    with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as tmp_pptx:
        build_ppt_from_slides(slides_text, bg_path, tmp_pptx.name)
        pptx_path = tmp_pptx.name

    with open(pptx_path, "rb") as f:
        st.success(f"Done! Generated {num} slides. Download below.")
        st.download_button(
            "Download Your PowerPoint",
            f,
            file_name="ConvertedPresentation.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )