"""
Lets a buyer add a vendor response by pasting a link instead of only
uploading a file - e.g. a Google Doc/Sheet a vendor shared, or a direct
link to a file (including one copied out of an email).

Scope, stated honestly: this fetches PUBLIC links only. There's no OAuth
flow here - we're not asking the buyer to sign into their Google account
or their email inbox. For a Google Doc/Sheet, that means the vendor (or
buyer) needs to have sharing set to "Anyone with the link can view" -
exactly the permission Google's own share dialog calls out. A private
link will fail with a clear message rather than silently doing nothing,
and the buyer can fall back to downloading the file themselves and using
the regular upload widget instead.
"""
import mimetypes
import os
import re
from urllib.parse import urlparse

import requests

MAX_BYTES = 50 * 1024 * 1024  # 50MB, well above any realistic vendor quote file
TIMEOUT_SECS = 20

CONTENT_TYPE_TO_EXT = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/msword": ".doc",
    "application/vnd.ms-excel": ".xls",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "text/plain": ".txt",
    "message/rfc822": ".eml",
}

GOOGLE_DOC_RE = re.compile(r"docs\.google\.com/document/d/([a-zA-Z0-9_-]+)")
GOOGLE_SHEET_RE = re.compile(r"docs\.google\.com/spreadsheets/d/([a-zA-Z0-9_-]+)")
GOOGLE_SLIDES_RE = re.compile(r"docs\.google\.com/presentation/d/([a-zA-Z0-9_-]+)")
GOOGLE_DRIVE_FILE_RE = re.compile(r"drive\.google\.com/file/d/([a-zA-Z0-9_-]+)")


class FetchError(Exception):
    pass


def _resolve_google_link(url: str):
    """Returns (export_url, forced_extension) for a Google Docs/Sheets/Drive
    link, or None if this isn't one."""
    if m := GOOGLE_DOC_RE.search(url):
        return f"https://docs.google.com/document/d/{m.group(1)}/export?format=docx", ".docx"
    if m := GOOGLE_SHEET_RE.search(url):
        return f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=xlsx", ".xlsx"
    if m := GOOGLE_SLIDES_RE.search(url):
        raise FetchError(
            "This looks like a Google Slides link - a vendor rate card as a slide deck isn't "
            "one of the supported formats. Export it to PDF from Google Slides and paste that "
            "link instead, or upload the exported file directly."
        )
    if m := GOOGLE_DRIVE_FILE_RE.search(url):
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}", None
    return None


def _filename_from_response(url: str, resp: requests.Response, forced_ext: str | None) -> str:
    cd = resp.headers.get("content-disposition", "")
    if m := re.search(r'filename="?([^";]+)"?', cd):
        return m.group(1).strip()

    ext = forced_ext
    if not ext:
        path_ext = os.path.splitext(urlparse(url).path)[1].lower()
        if path_ext in CONTENT_TYPE_TO_EXT.values() or path_ext in (".jpeg",):
            ext = path_ext
        else:
            content_type = resp.headers.get("content-type", "").split(";")[0].strip()
            ext = CONTENT_TYPE_TO_EXT.get(content_type) or mimetypes.guess_extension(content_type) or ""

    host = urlparse(url).netloc.replace("www.", "").split(".")[0] or "vendor_link"
    return f"{host}_linked{ext or '.bin'}"


def fetch_vendor_file_from_url(url: str):
    """Returns (filename, content_bytes). Raises FetchError with a message
    safe to show directly to the buyer on anything that goes wrong."""
    url = url.strip()
    if not url.lower().startswith(("http://", "https://")):
        raise FetchError("That doesn't look like a URL - links should start with http:// or https://")

    forced_ext = None
    google_resolution = _resolve_google_link(url)
    if google_resolution:
        url, forced_ext = google_resolution

    try:
        resp = requests.get(url, timeout=TIMEOUT_SECS, allow_redirects=True, stream=True)
    except requests.exceptions.RequestException as e:
        raise FetchError(f"Couldn't reach that link: {e}")

    if resp.status_code == 404:
        raise FetchError("That link returned a 404 - double check it's correct and still active.")
    if resp.status_code in (401, 403):
        raise FetchError(
            "That link isn't publicly accessible (got a permission error). If this is a Google "
            "Doc/Sheet, set sharing to 'Anyone with the link can view' and try again, or "
            "download the file yourself and use the upload box instead."
        )
    if resp.status_code >= 400:
        raise FetchError(f"That link returned an error (HTTP {resp.status_code}).")

    content_type = resp.headers.get("content-type", "").split(";")[0].strip().lower()

    content = b""
    for chunk in resp.iter_content(chunk_size=1024 * 256):
        content += chunk
        if len(content) > MAX_BYTES:
            raise FetchError(f"That file is larger than the {MAX_BYTES // (1024*1024)}MB limit for a link add.")

    if not forced_ext and content_type == "text/html" and len(content) < 200_000:
        raise FetchError(
            "That link returned a webpage, not a file - this usually means the link needs sign-in "
            "or isn't set to public access. Set sharing to 'Anyone with the link can view' (for "
            "Google Docs/Sheets), or download the file yourself and use the upload box instead."
        )

    filename = _filename_from_response(url, resp, forced_ext)
    ext = os.path.splitext(filename)[1].lower()
    supported = {".xlsx", ".pdf", ".docx", ".jpg", ".jpeg", ".png", ".txt", ".eml"}
    if ext not in supported:
        raise FetchError(
            f"That link resolved to a {ext or 'file with an unrecognized type'}, which isn't one "
            f"of the supported vendor response formats (Excel, PDF, Word, image, or plain text/email)."
        )

    return filename, content
