
import story_shorts_mgr
import os

def status_update(msg):
    print(f"[STATUS] {msg}")

prompt = "Tell the story of 'Fight Club' from Tyler Durden's perspective"
print(f"Testing generation with prompt: {prompt}")

output = story_shorts_mgr.create_story_video(
    prompt, 
    output_file="test_fight_club.mp4",
    status_callback=status_update
)

print(f"Generation result: {output}")
