import os
import uuid
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL", "tiny")
_whisper_model = None


def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        import whisper
        _whisper_model = whisper.load_model(WHISPER_MODEL_SIZE)
    return _whisper_model


def extract_video_id(url_or_id: str) -> str:
    if "youtube.com" in url_or_id or "youtu.be" in url_or_id:
        if "v=" in url_or_id:
            return url_or_id.split("v=")[1].split("&")[0]
        if "youtu.be/" in url_or_id:
            return url_or_id.split("youtu.be/")[1].split("?")[0]
    return url_or_id


def try_captions(video_id: str):
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


def try_whisper(video_id: str):
    import yt_dlp

    audio_path = f"/tmp/{uuid.uuid4()}"
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": audio_path + ".%(ext)s",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }],
        "quiet": True,
        "noplaylist": True,
    }

    url = f"https://www.youtube.com/watch?v={video_id}"
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    mp3_path = audio_path + ".mp3"

    try:
        model = get_whisper_model()
        result = model.transcribe(mp3_path)
        segments = [
            {"start": seg["start"], "end": seg["end"], "text": seg["text"].strip()}
            for seg in result["segments"]
        ]
        return {
            "video_id": video_id,
            "method_used": "whisper",
            "is_manual": False,
            "language": result.get("language", "unknown"),
            "segments": segments,
        }
    finally:
        if os.path.exists(mp3_path):
            os.remove(mp3_path)


def transcribe_video(url_or_id: str) -> dict:
    video_id = extract_video_id(url_or_id)

    result = try_captions(video_id)
    if result:
        return result

    result = try_whisper(video_id)
    if result:
        return result

    raise RuntimeError(f"Could not transcribe video {video_id} via captions or Whisper")


def get_playlist_video_ids(playlist_url: str):
    import yt_dlp
    ydl_opts = {"extract_flat": True, "quiet": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)
        return [entry["id"] for entry in info["entries"]]
