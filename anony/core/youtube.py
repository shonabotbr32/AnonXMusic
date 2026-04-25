import re
import asyncio
import yt_dlp
import aiohttp
import time
import random

from AloneX.helpers import Track, utils

# 🔁 Multiple API Keys
API_KEYS = [
    "AIzaSyBTrBavSJWwUGmgb-Moy-O5E7x1wq13XpE",
    "AIzaSyBCHeIXZPaYaYMew6HtAC23xOEnWwxqBHo",
    "AIzaSyAz4L9FY1Q8LNjaA5vq_bRPmifkNzptOiQ"
]


class YouTube:
    def __init__(self):  # ✅ FIXED
        self.base = "https://www.youtube.com/watch?v="
        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?(youtube\.com|youtu\.be)/"
        )

        self.cache = {}
        self.cache_ttl = 3600

        # ❌ yaha session nahi banega
        self.session = None

    # ✅ SAFE SESSION CREATE
    async def get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    # ✅ CLOSE SESSION (important)
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    def get_api_key(self):
        return random.choice(API_KEYS)

    def is_url(self, text: str) -> bool:
        return bool(re.match(self.regex, text))

    # ---------------- CACHE ----------------
    def get_cache(self, query):
        data = self.cache.get(query)
        if data:
            result, expiry = data
            if time.time() < expiry:
                return result
            else:
                del self.cache[query]
        return None

    def set_cache(self, query, result):
        self.cache[query] = (result, time.time() + self.cache_ttl)

    # ---------------- API SEARCH ----------------
    async def api_search(self, query: str):
        session = await self.get_session()

        for _ in range(len(API_KEYS)):
            key = self.get_api_key()
            try:
                url = (
                    "https://www.googleapis.com/youtube/v3/search"
                    f"?part=snippet&q={query}&maxResults=1&type=video&key={key}"
                )

                async with session.get(url, timeout=10) as resp:
                    data = await resp.json()

                if "items" in data and data["items"]:
                    video = data["items"][0]
                    return {
                        "id": video["id"]["videoId"],
                        "title": video["snippet"]["title"],
                        "channel": video["snippet"]["channelTitle"],
                        "thumbnail": video["snippet"]["thumbnails"]["high"]["url"],
                    }

            except Exception as e:
                print("API FAIL:", key, e)
                continue

        return None

    # ---------------- YTDLP FALLBACK ----------------
    async def ytdlp_search(self, query: str):
        def extract():
            try:
                with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
                    data = ydl.extract_info(f"ytsearch1:{query}", download=False)
                    return data["entries"][0] if data else None
            except:
                return None

        info = await asyncio.to_thread(extract)

        if not info:
            return None

        return {
            "id": info.get("id"),
            "title": info.get("title"),
            "channel": info.get("uploader", ""),
            "thumbnail": info.get("thumbnail", ""),
        }

    # ---------------- SEARCH ----------------
    async def search(self, query: str, m_id: int, video: bool = False):
        try:
            cached = self.get_cache(query)
            if cached:
                return cached

            if self.is_url(query):
                return await self.get_track_from_url(query, m_id, video)

            data = await self.api_search(query)

            if not data:
                data = await self.ytdlp_search(query)

            if not data:
                return None

            track = Track(
                id=data["id"],
                channel_name=data["channel"],
                duration="Unknown",
                duration_sec=0,
                message_id=m_id,
                title=(data["title"] or "")[:60],
                thumbnail=data["thumbnail"],
                url=self.base + data["id"],
                view_count="",
                video=video,
            )

            self.set_cache(query, track)
            return track

        except Exception as e:
            print("SEARCH ERROR:", e)
            return None

    # ---------------- URL TRACK ----------------
    async def get_track_from_url(self, url: str, m_id: int, video: bool):
        def extract():
            try:
                with yt_dlp.YoutubeDL(self.ydl_opts()) as ydl:
                    return ydl.extract_info(url, download=False)
            except:
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
        }

    async def stream(self, url_or_id: str):
        url = url_or_id if self.is_url(url_or_id) else self.base + url_or_id

        def extract():
            try:
                with yt_dlp.YoutubeDL(self.ydl_opts()) as ydl:
                    info = ydl.extract_info(url, download=False)

                    if info.get("url"):
                        return info["url"]

                    for f in reversed(info.get("formats", [])):
                        if f.get("acodec") != "none":
                            return f["url"]

            except:
                return None

        return await asyncio.to_thread(extract)