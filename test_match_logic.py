
import difflib
import re

def is_good_match(filename, subject, year=None):
    print(f"\n--- Testing: '{subject}' (Year: {year}) vs '{filename}' ---")
    
    # Normalize
    name_clean = filename.rsplit('.', 1)[0]
    norm_file = re.sub(r'[._\-]', ' ', name_clean).lower()
    norm_subj = re.sub(r'[._\-]', ' ', subject).lower()
    
    tags = ["1080p", "720p", "480p", "webrip", "bluray", "x264", "x265", "aac", "yts", "mx", "amzn", "h264"]
    for tag in tags:
        norm_file = norm_file.replace(tag, "")
    
    norm_file = re.sub(r'\s+', ' ', norm_file).strip()
    print(f"Cleaned File: '{norm_file}'")
    
    if year:
        if str(year) not in norm_file:
            print("❌ Year mismatch")
            return False
        else:
            print("✅ Year matched")

    matcher = difflib.SequenceMatcher(None, norm_subj, norm_file)
    ratio = matcher.ratio()
    print(f"DiffLib Ratio: {ratio:.2f}")
    
    # Check if subject is a distinct word sequence in file
    # Regex word boundary check
    if re.search(r'\b' + re.escape(norm_subj) + r'\b', norm_file):
        print("✅ Word boundary match")
    else:
        print("❌ No word boundary match")

    return ratio > 0.6

file_wrong = "The.Last.Days.Of.American.Crime.2020.720p.WEBRip.x264.AAC-[YTS.MX].mp4"
file_right = "The.American.2010.1080p.BluRay.x264.YIFY.mp4"

is_good_match(file_wrong, "The American", None)
