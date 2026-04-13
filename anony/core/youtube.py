import re
import asyncio
import yt_dlp
import aiohttp

from Anony.helpers import Track, utils

YOUTUBE_API_KEY = "AIzaSyBgBglXFiOGycp3MbMAJibytpLsD8I5Hho"


class YouTube:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?(youtube\.com|youtu\.be)/"
        )

    def is_url(self, text: str) -> bool:
        return bool(re.match(self.regex, text))

    # ---------------- API SEARCH ----------------
    async def api_search(self, query: str):
        url = (
            "https://www.googleapis.com/youtube/v3/search"
            f"?part=snippet&q={query}&maxResults=1&type=video&key={YOUTUBE_API_KEY}"
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()

        items = data.get("items")
        if not items:
            return None

        video = items[0]
        video_id = video["id"]["videoId"]

        return {
            "id": video_id,
            "title": video["snippet"]["title"],
            "channel": video["snippet"]["channelTitle"],
            "thumbnail": video["snippet"]["thumbnails"]["high"]["url"],
        }

    # ---------------- SEARCH ----------------
    async def search(self, query: str, m_id: int, video: bool = False):
        try:
            if self.is_url(query):
                return await self.get_track_from_url(query, m_id, video)

            data = await self.api_search(query)

            if not data:
                return None

            return Track(
                id=data["id"],
                channel_name=data["channel"],
                duration="Unknown",
                duration_sec=0,
                message_id=m_id,
                title=data["title"][:60],
                thumbnail=data["thumbnail"],
                url=self.base + data["id"],
                view_count="",
                video=video,
            )

        except Exception as e:
            print("SEARCH ERROR:", e)
            return None

    # ---------------- URL TRACK ----------------
    async def get_track_from_url(self, url: str, m_id: int, video: bool):
        def extract():
            try:
                with yt_dlp.YoutubeDL(self.ydl_opts()) as ydl:
                    return ydl.extract_info(url, download=False)
            except Exception as e:
                print("URL ERROR:", e)
                return None

        info = await asyncio.to_thread(extract)

        if not info:
            return None

        return Track(
            id=info.get("id"),
            channel_name=info.get("uploader", ""),
            duration=utils.format_duration(info.get("duration", 0)),
            duration_sec=info.get("duration", 0),
            message_id=m_id,
            title=(info.get("title") or "")[:60],
            thumbnail=info.get("thumbnail", ""),
            url=url,
            view_count=str(info.get("view_count", "")),
            video=video,
        )

    # ---------------- STREAM ----------------
    def ydl_opts(self):
        return {
            "quiet": True,
            "no_warnings": True,
            "geo_bypass": True,
            "nocheckcertificate": True,
            "ignoreerrors": True,
            "retries": 10,

            "format": "bestaudio/best",

            "extractor_args": {
                "youtube": {
                    "player_client": [
                        "android",
                        "web",
                        "web_embedded"
                    ]
                }
            },

            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Linux; Android 13) "
                    "AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
                )
            },
        }

    async def stream(self, url_or_id: str):
        url = url_or_id if self.is_url(url_or_id) else self.base + url_or_id

        def extract():
            try:
                with yt_dlp.YoutubeDL(self.ydl_opts()) as ydl:
                    info = ydl.extract_info(url, download=False)

                    if not info:
                        return None

                    if info.get("url"):
                        return info["url"]

                    for f in reversed(info.get("formats", [])):
                        if f.get("acodec") != "none" and f.get("url"):
                            return f["url"]

                    return None

            except Exception as e:
                print("STREAM ERROR:", e)
                return None

        return await asyncio.to_thread(extract)

    # ---------------- PLAYLIST ----------------
    async def playlist(self, limit: int, user: str, query: str, video=False):
        tracks = []

        data = await self.api_search(query)
        if not data:
            return tracks

        tracks.append(
            Track(
                id=data["id"],
                channel_name=data["channel"],
                duration="Unknown",
                duration_sec=0,
                title=data["title"][:60],
                thumbnail=data["thumbnail"],
                url=self.base + data["id"],
                user=user,
                view_count="",
                video=video,
            )
        )

        return tracks