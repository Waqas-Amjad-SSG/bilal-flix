"""
BILAL FLIX - Local Video & Subtitle Scanner
=============================================
Scans your OneDrive movie folders for video and subtitle files,
then updates index.html with local streaming paths.

Usage:
  python setup-local.py

After running, start the server:
  python run-server.py
"""

import os, re, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))  # "Seasons & Movies 2"
INDEX_FILE = os.path.join(SCRIPT_DIR, "index.html")

# Folders to scan (relative to "Seasons & Movies 2")
SCAN_FOLDERS = [
    os.path.join(PARENT_DIR, "Movies", "00 - Watched"),
    os.path.join(PARENT_DIR, "Movies for mano 2"),
]

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".m4v", ".webm", ".ts"}
SUB_EXTS = {".srt", ".vtt", ".sub", ".ass", ".ssa", ".idx"}


# ══════════════════════════════════════════
# Scanner
# ══════════════════════════════════════════

def scan_folder(folder_path):
    """Scan a folder for movie subfolders containing video + subtitle files."""
    results = []
    if not os.path.exists(folder_path):
        print(f"  Skipping (not found): {folder_path}")
        return results

    folder_name = os.path.basename(folder_path)
    print(f"\n  Scanning: {folder_name}/")

    for entry in sorted(os.listdir(folder_path)):
        entry_path = os.path.join(folder_path, entry)

        if os.path.isdir(entry_path):
            # Movie subfolder — look inside for video + subtitle files
            videos = []
            subs = []
            for root, dirs, files in os.walk(entry_path):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    rel = os.path.relpath(os.path.join(root, f), PARENT_DIR)
                    rel = rel.replace("\\", "/")  # Use forward slashes for URLs
                    if ext in VIDEO_EXTS:
                        videos.append({"name": f, "path": "/" + rel, "size": get_size(os.path.join(root, f))})
                    elif ext in SUB_EXTS:
                        subs.append({"name": f, "path": "/" + rel})

            if videos:
                # Pick the largest video file (usually the movie, not a sample)
                best_video = max(videos, key=lambda v: v["size"])
                best_sub = subs[0]["path"] if subs else ""

                # Folder path relative to server root
                folder_rel = "/" + os.path.relpath(entry_path, PARENT_DIR).replace("\\", "/")

                results.append({
                    "folder_name": entry,
                    "folder_path": folder_rel,
                    "video_path": best_video["path"],
                    "video_name": best_video["name"],
                    "subtitle_path": best_sub,
                    "subtitle_name": subs[0]["name"] if subs else "",
                })
                sub_mark = " + subs" if best_sub else ""
                print(f"    + {entry[:55]:55s} {best_video['name'][-20:]}{sub_mark}")
            else:
                # Empty folder (cloud-only files not synced)
                # Guess the video filename from the folder name
                guessed_name = entry + ".mp4"
                folder_rel = "/" + os.path.relpath(entry_path, PARENT_DIR).replace("\\", "/")
                results.append({
                    "folder_name": entry,
                    "folder_path": folder_rel,
                    "video_path": folder_rel + "/" + guessed_name,
                    "video_name": guessed_name,
                    "subtitle_path": "",
                    "subtitle_name": "",
                    "guessed": True,
                })
                print(f"    ? {entry[:55]:55s} (guessed: {guessed_name[-25:]})")

        elif os.path.isfile(entry_path):
            # Standalone video file (not in a subfolder)
            ext = os.path.splitext(entry)[1].lower()
            if ext in VIDEO_EXTS:
                rel = "/" + os.path.relpath(entry_path, PARENT_DIR).replace("\\", "/")
                folder_rel = "/" + os.path.relpath(folder_path, PARENT_DIR).replace("\\", "/")
                results.append({
                    "folder_name": os.path.splitext(entry)[0],
                    "folder_path": folder_rel,
                    "video_path": rel,
                    "video_name": entry,
                    "subtitle_path": "",
                    "subtitle_name": "",
                })
                print(f"    + {entry[:55]:55s} (standalone)")

    return results


def get_size(path):
    """Get file size, returning 0 for cloud-only files."""
    try:
        return os.path.getsize(path)
    except:
        return 0


# ══════════════════════════════════════════
# Title Matching
# ══════════════════════════════════════════

def clean_filename(filename):
    """Strip codec/resolution tags from a filename to get a clean title."""
    name = os.path.splitext(filename)[0] if "." in filename else filename
    for pat in [
        r"\[.*?\]", r"\(.*?\)",
        r"\.?(?:720|1080|2160|480)p.*",
        r"\.?(?:BluRay|BRRip|WEBRip|WEB-DL|HDRip|DVDRip|HDTV).*",
        r"\.?(?:x264|x265|HEVC|H\.?264|H\.?265|AAC|AC3|DTS).*",
        r"\.?(?:YIFY|YTS|RARBG|EVO|SPARKS|FGT|ETRG|GalaxyRG).*",
        r"(?:720|1080|2160|480)p.*",
        r"DC\.REMASTERED",
        r"PROPER",
    ]:
        name = re.sub(pat, "", name, flags=re.IGNORECASE)
    name = re.sub(r"[._]", " ", name).strip(" -–")
    name = re.sub(r"\s+\d{4}\s*$", "", name)
    return name.strip().lower()


def match_to_catalog(folder_name, catalog):
    """Match a folder name to the best catalog entry. Returns entry id or None."""
    clean = clean_filename(folder_name)
    if not clean:
        return None

    best_id = None
    best_score = 0

    for eid, etitle in catalog:
        t = etitle.lower()

        # Exact match
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
        if clean in t:
            score = max(score, 0.9)

        if score > best_score and score >= 0.5:
            best_score = score
            best_id = eid

    return best_id


# ══════════════════════════════════════════
# HTML Updater
# ══════════════════════════════════════════

def update_catalog(html, updates):
    """Update videoUrl, subtitleUrl, and folderPath in the CATALOG entries."""
    count = 0
    for entry_id, data in updates.items():
        video_url = data["video_path"]
        sub_url = data.get("subtitle_path", "")
        folder_path = data.get("folder_path", "")

        # Find the catalog entry by ID and update videoUrl
        pattern = r'(id:\s*"' + re.escape(entry_id) + r'"[^}]*?)videoUrl:\s*""'
        replacement = lambda m: m.group(1) + 'videoUrl: "' + video_url + '"'
        new_html = re.sub(pattern, replacement, html, count=1)

        if new_html != html:
            html = new_html
            count += 1

            # Add subtitleUrl and folderPath if not already present
            if sub_url:
                # Add subtitleUrl after videoUrl
                old = f'videoUrl: "{video_url}"'
                new = f'videoUrl: "{video_url}", subtitleUrl: "{sub_url}"'
                html = html.replace(old, new, 1)

            if folder_path:
                # Add folderPath after the videoUrl (or subtitleUrl)
                if sub_url:
                    old = f'subtitleUrl: "{sub_url}"'
                    new = f'subtitleUrl: "{sub_url}", folderPath: "{folder_path}"'
                else:
                    old = f'videoUrl: "{video_url}"'
                    new = f'videoUrl: "{video_url}", folderPath: "{folder_path}"'
                html = html.replace(old, new, 1)

    return html, count


# ══════════════════════════════════════════
# Main
# ══════════════════════════════════════════

def main():
    print()
    print("=" * 58)
    print("   BILAL FLIX - Local Video & Subtitle Scanner")
    print("=" * 58)

    if not os.path.exists(INDEX_FILE):
        print(f"\n  ERROR: index.html not found at:\n  {INDEX_FILE}")
        return

    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    # Extract catalog entries
    catalog = re.findall(r'id:\s*"([^"]+)".*?title:\s*"([^"]+)"', html)
    empty_count = len(re.findall(r'videoUrl:\s*""', html))
    linked_count = len(re.findall(r'videoUrl:\s*"[^"]+"', html)) - len(re.findall(r'videoUrl:\s*""', html))
    print(f"\n  Catalog: {len(catalog)} titles ({linked_count} linked, {empty_count} need links)")

    # Scan all folders
    print()
    print("-" * 58)
    print("  STEP 1: Scanning folders for video & subtitle files...")
    print("-" * 58)

    all_scanned = []
    for folder in SCAN_FOLDERS:
        all_scanned.extend(scan_folder(folder))

    if not all_scanned:
        print("\n  No video files found!")
        print("  Make sure OneDrive has synced your movie folders.")
        print("  (Right-click folder > Always keep on this device)")
        return

    # Match to catalog
    print()
    print("-" * 58)
    print(f"  STEP 2: Matching {len(all_scanned)} items to catalog...")
    print("-" * 58)

    updates = {}
    unmatched = []

    for item in all_scanned:
        eid = match_to_catalog(item["folder_name"], catalog)
        if eid and eid not in updates:
            updates[eid] = item
            title = next((t for i, t in catalog if i == eid), eid)
            guessed = " (guessed)" if item.get("guessed") else ""
            sub = " + subs" if item["subtitle_path"] else ""
            print(f"    + {title[:45]:45s} {sub}{guessed}")
        elif not eid:
            unmatched.append(item["folder_name"])

    print(f"\n    Matched: {len(updates)}  |  Unmatched: {len(unmatched)}")

    if unmatched:
        print("\n    Unmatched folders:")
        for name in unmatched[:15]:
            print(f"      ? {clean_filename(name)[:60]}")
        if len(unmatched) > 15:
            print(f"      ... and {len(unmatched) - 15} more")

    if not updates:
        print("\n  No matches found. Exiting.")
        return

    # Update index.html
    print()
    print("-" * 58)
    print("  STEP 3: Updating index.html...")
    print("-" * 58)

    html, count = update_catalog(html, updates)

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    remaining = len(re.findall(r'videoUrl:\s*""', html))
    subs_count = len(re.findall(r'subtitleUrl:\s*"[^"]+"', html))

    print(f"\n    Updated {count} video links")
    print(f"    Subtitles found: {subs_count}")
    print(f"    Remaining without links: {remaining}")

    print()
    print("=" * 58)
    print(f"   Done! {count} movies linked for local streaming.")
    print(f"   Now run: python run-server.py")
    print("=" * 58)
    print()


if __name__ == "__main__":
    main()
