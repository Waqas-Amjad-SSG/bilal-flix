"""
BILAL FLIX — Movie Catalog Auto-Scanner
========================================
Run this script whenever you add new movies to your OneDrive folders.
It scans for video files, fetches posters from OMDB, and updates index.html.

Usage:
  python update-catalog.py

Requirements:
  pip install requests
"""

import os, re, json, sys, time

try:
    import requests
except ImportError:
    print("Installing requests...")
    os.system(f"{sys.executable} -m pip install requests")
    import requests

# ── CONFIGURATION ──
# Folders to scan (relative to this script's location, or absolute paths)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))  # Goes up to "Seasons & Movies 2"

SCAN_FOLDERS = [
    os.path.join(PARENT_DIR, "Movies"),
    os.path.join(PARENT_DIR, "Season"),
    os.path.join(PARENT_DIR, "Movies for mano 2"),
]

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".m4v", ".webm", ".ts"}
INDEX_FILE = os.path.join(SCRIPT_DIR, "index.html")
OMDB_API_KEY = "trilogy"  # Free OMDB key

# ── HELPERS ──
def clean_title(filename):
    """Extract clean movie title from filename."""
    name = os.path.splitext(filename)[0]
    # Remove common tags
    patterns = [
        r'\[.*?\]', r'\(.*?\)', r'\.(?:720|1080|2160|480)p.*', r'\.(?:BluRay|BRRip|WEBRip|WEB-DL|HDRip|DVDRip|HDTV).*',
        r'\.(?:x264|x265|HEVC|H\.?264|H\.?265|AAC|AC3|DTS).*', r'\.(?:YIFY|YTS|RARBG|EVO|SPARKS|FGT|ETRG).*',
        r'(?:720|1080|2160|480)p.*', r'(?:BluRay|BRRip|WEBRip|WEB-DL|HDRip|DVDRip).*',
        r'(?:x264|x265|HEVC).*', r'(?:YIFY|YTS|RARBG).*',
    ]
    for p in patterns:
        name = re.sub(p, '', name, flags=re.IGNORECASE)
    # Replace dots and underscores with spaces
    name = re.sub(r'[._]', ' ', name)
    # Extract year if present
    year_match = re.search(r'\b(19|20)\d{2}\b', name)
    year = int(year_match.group()) if year_match else None
    if year_match:
        name = name[:year_match.start()]
    name = name.strip(' -–')
    return name.strip(), year

def make_id(title):
    """Create a safe ID from title."""
    return re.sub(r'[^a-z0-9]+', '_', title.lower()).strip('_')

def detect_series(filepath):
    """Check if a path indicates a TV series (has season folders)."""
    parts = filepath.replace('\\', '/').split('/')
    for part in parts:
        if re.match(r'(?i)^s(?:eason)?\s*\d+', part):
            return True
    return False

def detect_category(title, filepath, folder_name):
    """Guess category based on title and path."""
    title_lower = title.lower()
    kids_keywords = ['cocomelon', 'peppa', 'paw patrol', 'bluey', 'sesame', 'dora',
                     'frozen', 'moana', 'encanto', 'coco ', 'lego', 'minion']
    if any(k in title_lower for k in kids_keywords):
        return "kids"
    if detect_series(filepath) or 'season' in folder_name.lower():
        return "series"
    return "movies"

def fetch_poster(title, year=None):
    """Fetch poster URL from OMDB."""
    try:
        params = {"t": title, "apikey": OMDB_API_KEY}
        if year:
            params["y"] = year
        r = requests.get("https://www.omdbapi.com/", params=params, timeout=10)
        data = r.json()
        if data.get("Response") == "True" and data.get("Poster", "N/A") != "N/A":
            return data["Poster"], data.get("Genre", "").split(",")[0].strip() or "Drama"
        # Retry without year
        if year:
            del params["y"]
            r = requests.get("https://www.omdbapi.com/", params=params, timeout=10)
            data = r.json()
            if data.get("Response") == "True" and data.get("Poster", "N/A") != "N/A":
                return data["Poster"], data.get("Genre", "").split(",")[0].strip() or "Drama"
    except:
        pass
    return "", "Drama"

def get_existing_ids(html):
    """Extract existing movie IDs from the catalog."""
    return set(re.findall(r'id:\s*"([^"]+)"', html))

# ── MAIN ──
def main():
    print("=" * 50)
    print("  BILAL FLIX — Catalog Scanner")
    print("=" * 50)

    # Read existing catalog
    with open(INDEX_FILE, 'r', encoding='utf-8') as f:
        html = f.read()

    existing_ids = get_existing_ids(html)
    print(f"\nExisting catalog: {len(existing_ids)} titles")

    # Scan folders for video files
    all_videos = []
    for folder in SCAN_FOLDERS:
        if not os.path.exists(folder):
            print(f"  Skipping (not found): {folder}")
            continue
        folder_name = os.path.basename(folder)
        print(f"  Scanning: {folder_name}/")
        for root, dirs, files in os.walk(folder):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in VIDEO_EXTENSIONS:
                    filepath = os.path.join(root, f)
                    title, year = clean_title(f)
                    if len(title) < 2:
                        continue
                    mid = make_id(title)
                    category = detect_category(title, filepath, folder_name)
                    all_videos.append({
                        "id": mid,
                        "title": title,
                        "year": year,
                        "category": category,
                        "filepath": filepath,
                        "folder": folder_name
                    })

    # Deduplicate by ID (keep first occurrence)
    seen = {}
    unique = []
    for v in all_videos:
        if v["id"] not in seen:
            seen[v["id"]] = v
            unique.append(v)

    # Find NEW movies not in existing catalog
    new_movies = [v for v in unique if v["id"] not in existing_ids]

    if not new_movies:
        print(f"\n✓ No new movies found. Catalog is up to date!")
        return

    print(f"\n★ Found {len(new_movies)} new titles!")
    print("  Fetching posters and metadata...\n")

    # Build new catalog entries
    new_entries = []
    for v in new_movies:
        poster, genre = fetch_poster(v["title"], v["year"])
        year = v["year"] or 2024
        emoji_map = {
            "Action": "💥", "Comedy": "😂", "Drama": "🎭", "Horror": "😱",
            "Thriller": "🔪", "Sci-Fi": "🚀", "Romance": "❤️", "Animation": "🧸",
            "Crime": "🕵️", "Adventure": "🌍", "Documentary": "📽️", "Fantasy": "🧙",
        }
        emoji = emoji_map.get(genre, "🎬")
        status = "✓" if poster else "✗ (no poster)"
        print(f"  {status} {v['title']} ({year}) — {genre}")

        entry = (
            f'  {{ id: "{v["id"]}", title: "{v["title"]}", year: {year}, '
            f'category: "{v["category"]}", genre: "{genre}", '
            f'desc: "", poster: "{poster}", videoUrl: "", '
            f'duration: "", emoji: "{emoji}" }},'
        )
        new_entries.append(entry)
        time.sleep(0.3)

    # Insert new entries before the closing ];
    marker = "];"
    # Find the CATALOG closing
    catalog_end = html.rfind(marker, html.find("const CATALOG"))
    if catalog_end == -1:
        print("\n✗ Could not find CATALOG end marker in index.html")
        return

    new_block = "\n  // ═══ AUTO-ADDED " + time.strftime("%Y-%m-%d %H:%M") + " ═══\n"
    new_block += "\n".join(new_entries) + "\n"

    html = html[:catalog_end] + new_block + html[catalog_end:]

    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\n{'=' * 50}")
    print(f"  ✓ Added {len(new_entries)} new titles to Bilal Flix!")
    print(f"  Refresh the page to see them.")
    print(f"{'=' * 50}")

if __name__ == "__main__":
    main()
