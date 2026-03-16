#!/usr/bin/env python3
"""
Transcribes audio/video file using Whisper with word-level timestamps.
Usage: python utils_py/transcribe_audio.py "path/to/audio.mov" --lang es --model base
"""
import json
import sys
import argparse


def transcribe(audio_path: str, language: str = "es", model_name: str = "base") -> list:
    try:
        import whisper
    except ImportError:
        print(json.dumps({"error": "openai-whisper not installed. Run: pip install openai-whisper"}))
        sys.exit(1)

    model = whisper.load_model(model_name)
    result = model.transcribe(
        audio_path,
        word_timestamps=True,
        language=language,
    )

    words = []
    for segment in result.get("segments", []):
        for word_data in segment.get("words", []):
            word = word_data.get("word", "").strip()
            start = round(word_data.get("start", 0), 3)
            end = round(word_data.get("end", 0), 3)

            if not word:
                continue

            # Ensure minimum duration of 0.1s
            if (end - start) < 0.1:
                end = round(start + 0.1, 3)

            words.append({
                "word": word,
                "start": start,
                "end": end,
            })

    # Fix overlapping timestamps: if word[i].start < word[i-1].end, push start forward
    for i in range(1, len(words)):
        if words[i]["start"] < words[i - 1]["end"]:
            words[i]["start"] = round(words[i - 1]["end"] + 0.01, 3)
            # If fix inverted the segment, extend end to preserve minimum duration
            if words[i]["end"] <= words[i]["start"]:
                words[i]["end"] = round(words[i]["start"] + 0.1, 3)

    return words


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transcribe audio with word timestamps")
    parser.add_argument("audio_path", help="Path to audio or video file")
    parser.add_argument("--lang", default="es", help="Language code (default: es)")
    parser.add_argument("--model", default="base", help="Whisper model: tiny/base/small/medium/large (default: base)")
    args = parser.parse_args()

    words = transcribe(args.audio_path, args.lang, args.model)
    print(json.dumps(words, indent=2, ensure_ascii=False))