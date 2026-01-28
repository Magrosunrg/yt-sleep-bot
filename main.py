# author: Giorgio
# date: 23.08.2024
# topic: TikTok-Voice-TTS -> Edge-TTS Replacement
# version: 1.4

import argparse
import asyncio
import edge_tts
from typing import Optional
import os

async def _run_tts(text, voice, output_file):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)

def tts(text, voice, output_file, play=False):
    try:
        asyncio.run(_run_tts(text, voice, output_file))
        print(f"Generated: {output_file}")
        if play:
            print("Playback not implemented in this replacement version.")
    except Exception as e:
        print(f"Error generating TTS: {e}")

def main():
    # adding arguments
    parser = argparse.ArgumentParser(description='Edge TTS (Replacing TikTok TTS)')
    parser.add_argument('-t', help='text input')
    parser.add_argument('-v', help='voice selection', default='en-US-AriaNeural')
    parser.add_argument('-o', help='output filename', default='output.mp3')
    parser.add_argument('-txt', help='text input from a txt file', type=argparse.FileType('r', encoding="utf-8"))
    parser.add_argument('-play', help='play sound after generating audio', action='store_true')

    args = parser.parse_args()

    # checking if given values are valid
    if not args.t and not args.txt:
        # If no arguments provided, print help
        parser.print_help()
        return

    if args.t and args.txt:
        raise ValueError("only one input type is possible")
    
    voice = args.v
    
    # executing script
    if args.t:
        tts(args.t, voice, args.o, args.play)
    elif args.txt:
        tts(args.txt.read(), voice, args.o, args.play)

if __name__ == "__main__":
    main()
