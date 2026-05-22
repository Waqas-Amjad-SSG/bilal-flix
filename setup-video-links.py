"""
BILAL FLIX - OneDrive Video Link Setup
=======================================
Connects your OneDrive movies to BILAL FLIX for streaming.

HOW TO USE:
  1. Open OneDrive in your browser (onedrive.live.com)
  2. Right-click each movie folder > Share > "Anyone with the link" > "Can view"
  3. Copy the sharing link
  4. Run: python setup-video-links.py
  5. Paste the links when prompted

Requirements: pip install requests (auto-installed if missing)
"""

import os, re, sys, base64, time

try:
    import requests
except ImportError:
    print("Installing requests library...")
    os.system(f'"{sys.executable}" -m pip install requests')
    import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(SCRIPT_DIR, "index.html")
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".m4v", ".webm", ".ts"}


# ══════════════════════════════════════════
# OneDrive API Helpers
# ══════════════════════════════════════════

def encode_sharing_url(url):
    """Convert a OneDrive sharing URL to an API share token."""
    raw = base64.b64encode(url.strip().encode("utf-8")).decode("utf-8")
    return "u!" + raw.rstrip("=").replace("/", "_").replace("+", "-")


def api_list(sharing_url, subpath=""):
    """List items in a shared OneDrive folder or subfolder."""
    token = encode_sharing_url(sharing_url)
    if subpath:
        endpoint = f"https://api.onedrive.com/v1.0/shares/{token}/root:/{subpath}:/children?$top=200"
    else:
        endpoint = f"https://api.onedrive.com/v1.0/shares/{token}/root/children?$top=200"

    items = []
    while endpoint:
        try:
            r = requests.get(endpoint, timeout=30)
            if r.status_code != 200:
                print(f"    API error {r.status_code}: {r.text[:150]}")
                return items
            data = r.json()
            items.extend(data.get("value", []))
            endpoint = data.get("@odata.nextLink")
        except Exception as e:
            print(f"    Network error: {e}")
            return items
    return items


def find_videos(sharing_url, subpath="", depth=0):
    """Recursively find all video files in a shared folder."""
    if depth > 6:
        return []

    videos = []
    items = api_list(sharing_url, subpath)

    for item in items:
        name = item.get("name", "")
        full = f"{subpath}/{name}" if subpath else name

        if "folder" in item:
            # Skip the "01 - TO Watch" folder
            if "01" in name and "watch" in name.lower():
                print(f"    Skipping: {name}/")
                continue
            videos.extend(find_videos(sharing_url, full, depth + 1))
        else:
            ext = os.path.splitext(name)[1].lower()
            if ext in VIDEO_EXTS:
                token = encode_sharing_url(sharing_url)
                url = f"https://api.onedrive.com/v1.0/shares/{token}/root:/{full}:/content"
                videos.append({"name": name, "path": full, "url": url})
    return videos


# ══════════════════════════════════════════
# Title Matching
# ══════════════════════════════════════════

def clean_filename(filename):
    """Strip codec/resolution tags from a filename to get a clean title."""
    name = os.path.splitext(filename)[0]
    for pat in [
        r"\[.*?\]", r"\(.*?\)",
        r"\.?(?:720|1080|2160|480)p.*",
        r"\.?(?:BluRay|BRRip|WEBRip|WEB-DL|HDRip|DVDRip|HDTV).*",
        r"\.?(?:x264|x265|HEVC|H\.?264|H\.?265|AAC|AC3|DTS).*",
        r"\.?(?:YIFY|YTS|RARBG|EVO|SPARKS|FGT|ETRG|GalaxyRG).*",
        r"(?:720|1080|2160|480)p.*",
    ]:
        name = re.sub(pat, "", name, flags=re.IGNORECASE)
    name = re.sub(r"[._]", " ", name).strip(" -–")
    # Remove trailing year
    name = re.sub(r"\s+\d{4}\s*$", "", name)
    return name.strip().lower()


def match_to_catalog(video_name, catalog):
    """Match a video filename to the best catalog entry. Returns entry id or None."""
    clean = clean_filename(video_name)
    if not clean:
        return None

    best_id = None
    best_score = 0

    for eid, etitle in catalog:
        t = etitle.lower()

        # Exact
        if clean == t:
            return eid

        # Word overlap scoring
        v_words = set(clean.split())
        t_words = set(t.split())
        if not t_words:
            continue

        overlap = len(v_words & t_words)
        score = overlap / len(t_words)

        # Boost if title is fully contained in filename
        if t in clean:
            score = max(score, 0.95)

        if score > best_score and score >= 0.55:
            best_score = score
            best_id = eid

    return best_id


# ══════════════════════════════════════════
# HTML Updater
# ══════════════════════════════════════════

def update_catalog_urls(html, updates):
    """Update videoUrl fields in the HTML catalog."""
    count = 0
    for entry_id, url in updates.items():
        # Match the specific catalog entry and replace its empty videoUrl
        pattern = r'(id:\s*"' + re.escape(entry_id) + r'"[^}]*?)videoUrl:\s*""'
        new_html = re.sub(pattern, lambda m: m.group(1) + 'videoUrl: "' + url + '"', html, count=1)
        if new_html != html:
            html = new_html
            count += 1
    return html, count


# ══════════════════════════════════════════
# Main
# ══════════════════════════════════════════

def main():
    print()
    print("=" * 58)
    print("   BILAL FLIX - OneDrive Video Link Setup")
    print("=" * 58)

    if not os.path.exists(INDEX_FILE):
        print(f"\n  ERROR: index.html not found at:\n  {INDEX_FILE}")
        return

    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    # Extract catalog entries
    catalog = re.findall(r'id:\s*"([^"]+)".*?title:\s*"([^"]+)"', html)
    empty_count = len(re.findall(r'videoUrl:\s*""', html))
    print(f"\n  Catalog: {len(catalog)} titles ({empty_count} need video links)")

    # ── Collect sharing links ──
    print()
    print("-" * 58)
    print("  STEP 1: Paste your OneDrive sharing links")
    print("-" * 58)
    print("""
  Go to onedrive.live.com and share each folder:
    Right-click folder > Share > Anyone with the link > Can view

  Folders to share:
    1. Movies        (has 00-Watched subfolder)
    2. Season        (has Lost, Malcolm, etc.)
    3. Movies for mano 2
    """)

    folders = {}
    for name in ["Movies", "Season", "Movies for mano 2"]:
        link = input(f'  Link for "{name}" (Enter to skip): ').strip()
        if link:
            folders[name] = link
            print(f"    Saved!\n")

    if not folders:
        print("\n  No links provided. Exiting.")
        return

    # ── Scan folders ──
    print("-" * 58)
    print("  STEP 2: Scanning OneDrive folders for videos...")
    print("-" * 58)

    all_videos = []
    for fname, link in folders.items():
        print(f"\n  Scanning: {fname}/")
        vids = find_videos(link)
        print(f"    Found {len(vids)} video files")
        all_videos.extend(vids)

    if not all_videos:
        print("\n  No video files found! Check your sharing links.")
        print("  Make sure the folders are shared with 'Anyone with the link'.")
        return

    # ── Match to catalog ──
    print()
    print("-" * 58)
    print(f"  STEP 3: Matching {len(all_videos)} files to catalog...")
    print("-" * 58)

    updates = {}
    unmatched = []

    for v in all_videos:
        eid = match_to_catalog(v["name"], catalog)
        if eid and eid not in updates:
            updates[eid] = v["url"]
            title = next((t for i, t in catalog if i == eid), eid)
            print(f"    + {title}")
        elif not eid:
            unmatched.append(v["name"])

    print(f"\n    Matched: {len(updates)}  |  Unmatched: {len(unmatched)}")

    if unmatched:
        print("\n    Unmatched files:")
        for name in unmatched[:15]:
            print(f"      ? {name[:60]}")
        if len(unmatched) > 15:
            print(f"      ... and {len(unmatched) - 15} more")

    if not updates:
        print("\n  No matches found. Exiting.")
        return

    # ── Update index.html ──
    print()
    print("-" * 58)
    print(f"  STEP 4: Updating index.html...")
    print("-" * 58)

    html, count = update_catalog_urls(html, updates)

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    remaining = len(re.findall(r'videoUrl:\s*""', html))

    print(f"\n    Updated {count} video links in index.html")
    print(f"    Remaining without links: {remaining}")

    print()
    print("=" * 58)
    print(f"   Done! {count} movies are now linked for streaming.")
    print("   Refresh BILAL FLIX in your browser to test.")
    print("=" * 58)
    print()


if __name__ == "__main__":
    main()
