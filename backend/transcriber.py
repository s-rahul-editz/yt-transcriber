import os
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound


def extract_video_id(url_or_id: str) -> str:
    """Accepts a full YouTube URL or a raw video ID and returns the video ID."""
    if "youtube.com" in url_or_id or "youtu.be" in url_or_id:
        if "v=" in url_or_id:
            return url_or_id.split("v=")[1].split("&")[0]
        if "youtu.be/" in url_or_id:
            return url_or_id.split("youtu.be/")[1].split("?")[0]
    return url_or_id  # assume it's already a bare video ID


def try_captions(video_id: str):
    """Pull existing captions (manual > auto-generated)."""
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        try:
            transcript = transcript_list.find_manually_created_transcript(["en"])
        except NoTranscriptFound:
            transcript = transcript_list.find_generated_transcript(["en"])

        data = transcript.fetch()
        segments = [
            {"start": entry["start"], "end": entry["start"] + entry["duration"], "text": entry["text"]}
            for entry in data
        ]
        return {
            "video_id": video_id,
            "method_used": "captions",
            "is_manual": transcript.is_generated is False,
            "language": transcript.language_code,
            "segments": segments,
        }
    except (TranscriptsDisabled, NoTranscriptFound):
        return None
    except Exception:
        return None


def transcribe_video(url_or_id: str) -> dict:
    """Main entry point: captions only, no Whisper fallback."""
    video_id = extract_video_id(url_or_id)

    result = try_captions(video_id)
    if result:
        return result

    raise RuntimeError(
        f"No captions available for video {video_id}. "
        f"This video doesn't have manual or auto-generated captions, "
        f"so it can't be transcribed."
    )


def get_playlist_video_ids(playlist_url: str):
    import yt_dlp
    ydl_opts = {"extract_flat": True, "quiet": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)
        return [{"id": entry["id"], "title": entry.get("title", entry["id"])} for entry in info["entries"]]
