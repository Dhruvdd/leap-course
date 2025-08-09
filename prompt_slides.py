# prompt_slides.py
from openai import OpenAI
from config import OPENAI_API_KEY
import re

DONE_MARKER_TMPL = "[[DONE PAGE {i}]]"

HEADER_RE = re.compile(r"(?m)^Slide\s*\d+\s*[–-]\s*.*$")
HEADER_OR_DASH_RE = re.compile(r"(?m)^Slide\s*\d+\s*[–-]\s*")
BULLET_HEADER_RE = re.compile(r"(?m)^Slide\s*\d+\s*[–-]\s*.*$")

def _count_slide_headers(text: str) -> int:
    return len(HEADER_RE.findall(text))

def collapse_to_single_header(page_text: str) -> str:
    """
    Safety net: enforce at most one 'Slide X – ...' header per page.
    If multiple headers exist, keep the first and convert subsequent headers into a simple bullet.
    """
    headers = list(HEADER_RE.finditer(page_text))
    if len(headers) <= 1:
        return page_text

    first_header_line = headers[0].group(0)
    rest_start = headers[0].end()
    rest = page_text[rest_start:].strip()

    # Replace any subsequent slide headers with a simple bullet so content isn't lost
    rest = BULLET_HEADER_RE.sub("•", rest)

    collapsed = f"{first_header_line}\n{rest}".strip()
    return collapsed

def prompt_slides_from_pages(
    pages,
    api_key: str = OPENAI_API_KEY,
    model: str = "gpt-4",
    max_tokens: int = 1600,
) -> str:
    """
    Process slides page-by-page with continuation.
    - Forces at most one header per page (unless multiple distinct titles truly exist).
    - Adds a per-page DONE marker and retries until the page is complete.
    - Only increments slide numbering once per page (prevents number creep).
    """
    client = OpenAI(api_key=api_key)

    base_rules = (
        "Extract slides from the given PAGE ONLY in this exact format:\n\n"
        "Slide X – [Slide Title]\n"
        "• Bullet\n"
        "    • Sub-bullet\n"
        "        • Sub-sub-bullet\n\n"
        "Rules:\n"
        "- Use 4 spaces for each sub-level.\n"
        "- Treat THIS PAGE as a hard boundary; do not include text from other pages.\n"
        "- Continue slide numbering from the given starting number.\n"
        "- Do NOT add any commentary.\n"
        "- IMPORTANT: Produce AT MOST ONE 'Slide X – ...' block for THIS PAGE, unless the page shows clear evidence of multiple distinct slide titles.\n"
        "- If the page appears to be a continuation of the previous slide, keep all bullets under a single 'Slide X – [same title] (cont.)' block; do not open a second header.\n"
        "- When you finish THIS PAGE, append the literal marker: [[DONE PAGE {i}]]\n"
    )

    all_pages_output = []
    next_slide_num = 1

    for i, page_text in enumerate(pages, start=1):
        page_done_marker = DONE_MARKER_TMPL.format(i=i)
        accumulated_page = ""
        tries = 0

        while True:
            tries += 1
            if tries > 6:  # safety guard to avoid infinite loops
                accumulated_page += f"\n\n{page_done_marker}"
                break

            if not accumulated_page:
                prompt = (
                    f"{base_rules}\n"
                    f"Start numbering at Slide {next_slide_num}.\n\n"
                    f"=== PAGE {i} CONTENT START ===\n{page_text}\n=== PAGE {i} CONTENT END ===\n\n"
                    f"Output slides now and end with {page_done_marker}."
                )
            else:
                prompt = (
                    f"{base_rules}\n"
                    f"Continue numbering at Slide {next_slide_num}.\n"
                    "Continue from where you left off on THIS PAGE. Do NOT repeat any lines already produced.\n\n"
                    f"=== PAGE {i} CONTENT START ===\n{page_text}\n=== PAGE {i} CONTENT END ===\n\n"
                    f"Continue ONLY the remaining slides/bullets for THIS PAGE and end with {page_done_marker}."
                )

            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.1,
            )
            out = resp.choices[0].message.content.strip()
            accumulated_page += ("\n\n" if accumulated_page else "") + out

            if page_done_marker in out:
                break
            # NOTE: we do NOT increment next_slide_num mid-page; only after the page is finalized

        # Clean marker and collapse extra headers (if any)
        accumulated_page_clean = accumulated_page.replace(page_done_marker, "").strip()
        accumulated_page_clean = collapse_to_single_header(accumulated_page_clean)

        # Now count how many headers on this page (after collapse) and bump numbering ONCE
        produced_total = _count_slide_headers(accumulated_page_clean)
        next_slide_num += produced_total

        all_pages_output.append(accumulated_page_clean)
        print(f"[page {i}] slide headers after collapse: {produced_total}; next starts at {next_slide_num}")

    final_text = "\n\n".join(all_pages_output)
    total_headers = _count_slide_headers(final_text)
    print(f"TOTAL slide headers: {total_headers}")
    return final_text