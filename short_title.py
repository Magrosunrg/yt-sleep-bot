from story_picker import get_memorized_title

DEFAULT_TAGS = ["#reddit", "#shorts", "#storytime", "#viral", "#amazingcontent"]

def generate_title_and_description(part_number=1, total_parts=1):
    reddit_title = get_memorized_title()
    hashtags = " #reddit #story"
    part_suffix = f" (Part {part_number})" if total_parts > 1 else ""

    max_title_length = 100
    fixed_suffix_length = len(part_suffix + hashtags)
    max_title_text_length = max_title_length - fixed_suffix_length

    if reddit_title and reddit_title.strip():
        title_raw = reddit_title.strip()
        if '.' in title_raw:
            sentence_cut = title_raw.split('.', 1)[0]
        else:
            sentence_cut = title_raw

        # Truncate if needed
        title_text = sentence_cut[:max_title_text_length].strip()
        if not title_text:
            title_text = "Amazing Reddit Story"
    else:
        title_text = "Amazing Reddit Story"

    full_title = f"{title_text}{part_suffix}{hashtags}"
    return full_title, "Like and subscribe for more amazing content!", DEFAULT_TAGS
