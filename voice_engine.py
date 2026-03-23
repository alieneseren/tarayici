"""
Visionary Navigator — Ses Motoru
edge-tts (TTS) + SpeechRecognition (STT) + yt-dlp (müzik) + Müzik Kütüphanesi.
"""

import asyncio
import json
import logging
import os
import tempfile
import subprocess
from typing import Optional, Callable, List

from PyQt6.QtCore import QThread, pyqtSignal, QUrl, QTimer
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

import config

logger = logging.getLogger("VoiceEngine")
logger.setLevel(logging.INFO)


# ─── Müzik Kütüphanesi Yönetimi ───────────────────────────────────

class MusicLibrary:
    """Kalıcı müzik kütüphanesi — MUSIC_DIR altında mp3 dosyaları saklar."""

    META_FILE = "library.json"

    def __init__(self):
        os.makedirs(config.MUSIC_DIR, exist_ok=True)
        self._meta_path = os.path.join(config.MUSIC_DIR, self.META_FILE)
        self._tracks: List[dict] = []
        self._load()

    def _load(self):
        try:
            if os.path.exists(self._meta_path):
                with open(self._meta_path, "r", encoding="utf-8") as f:
                    self._tracks = json.load(f)
            self._tracks = [t for t in self._tracks if os.path.exists(t.get("path", ""))]
        except Exception:
            self._tracks = []

    def _save(self):
        try:
            with open(self._meta_path, "w", encoding="utf-8") as f:
                json.dump(self._tracks, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Kütüphane kaydetme hatası: {e}")

    @property
    def tracks(self) -> List[dict]:
        return list(self._tracks)

    @property
    def track_count(self) -> int:
        return len(self._tracks)

    def get_track(self, index: int) -> Optional[dict]:
        """Belirtilen indeksteki track bilgisini döndürür."""
        if 0 <= index < len(self._tracks):
            return dict(self._tracks[index])
        return None

    def add_track(self, title: str, path: str, url: str = "") -> dict:
        track = {"title": title, "path": path, "url": url}
        self._tracks.append(track)
        self._save()
        logger.info(f"Kütüphaneye eklendi: {title[:40]} (url={'var' if url else 'yok'})")
        return track

    def remove_track(self, index: int):
        if 0 <= index < len(self._tracks):
            track = self._tracks.pop(index)
            try:
                if os.path.exists(track.get("path", "")):
                    os.remove(track["path"])
            except Exception:
                pass
            self._save()
            logger.info(f"Kütüphaneden silindi: {track.get('title', '?')[:40]}")

    def get_path(self, index: int) -> Optional[str]:
        if 0 <= index < len(self._tracks):
            return self._tracks[index].get("path")
        return None

    def get_url(self, index: int) -> Optional[str]:
        """Belirtilen indeksteki track'in YouTube URL'sini döndürür."""
        if 0 <= index < len(self._tracks):
            return self._tracks[index].get("url", "")
        return None

    def find_index_by_path(self, path: str) -> int:
        """Dosya yoluna göre track indeksini bul — tam ve yaklaşık eşleme."""
        # 1. Tam eşleme
        for i, t in enumerate(self._tracks):
            if t.get("path") == path:
                return i
        # 2. Basename eşleme (farklı kök yol)
        basename = os.path.basename(path)
        for i, t in enumerate(self._tracks):
            if os.path.basename(t.get("path", "")) == basename:
                return i
        # 3. Fuzzy: noktalama farkı yok say (prod. by == prod by)
        def _norm(s: str) -> str:
            import re
            return re.sub(r'[^\w\s]', '', s).lower()
        norm_base = _norm(basename)
        for i, t in enumerate(self._tracks):
            if _norm(os.path.basename(t.get("path", ""))) == norm_base:
                return i
        return -1

    def scan_music_dir(self) -> int:
        """MUSIC_DIR içindeki .mp3 dosyalarını tara, library'de olmayanları ekle."""
        import glob as _glob
        added = 0
        existing_paths = {t.get("path", "") for t in self._tracks}
        existing_basenames = {os.path.basename(p) for p in existing_paths}
        pattern = os.path.join(config.MUSIC_DIR, "*.mp3")
        for mp3_path in _glob.glob(pattern):
            basename = os.path.basename(mp3_path)
            if mp3_path not in existing_paths and basename not in existing_basenames:
                title = os.path.splitext(basename)[0]
                self._tracks.append({"title": title, "path": mp3_path, "url": ""})
                added += 1
        if added:
            self._save()
            logger.info(f"Müzik dizini tarandı: {added} yeni şarkı eklendi.")
        return added

    # ── Playlist yönetimi ──────────────────────────────────────────

    PLAYLISTS_FILE = "playlists.json"

    def _load_playlists(self) -> dict:
        """Playlist'leri diskten yükle."""
        path = os.path.join(config.MUSIC_DIR, self.PLAYLISTS_FILE)
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_playlists(self, playlists: dict) -> None:
        path = os.path.join(config.MUSIC_DIR, self.PLAYLISTS_FILE)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(playlists, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Playlist kaydetme hatası: {e}")

    def get_playlists(self) -> dict:
        """Tüm playlist'leri döndürür: {isim: [track_index, ...]}"""
        return self._load_playlists()

    def create_playlist(self, name: str) -> bool:
        """Yeni boş playlist oluştur. Zaten varsa False döner."""
        playlists = self._load_playlists()
        if name in playlists:
            return False
        playlists[name] = []
        self._save_playlists(playlists)
        logger.info(f"Playlist oluşturuldu: {name}")
        return True

    def rename_playlist(self, old_name: str, new_name: str) -> bool:
        playlists = self._load_playlists()
        if old_name not in playlists or new_name in playlists:
            return False
        playlists[new_name] = playlists.pop(old_name)
        self._save_playlists(playlists)
        return True

    def delete_playlist(self, name: str) -> bool:
        playlists = self._load_playlists()
        if name not in playlists:
            return False
        del playlists[name]
        self._save_playlists(playlists)
        logger.info(f"Playlist silindi: {name}")
        return True

    def add_to_playlist(self, playlist_name: str, track_index: int) -> bool:
        """Track'i playlist'e ekle (tekrar yoksa)."""
        playlists = self._load_playlists()
        if playlist_name not in playlists:
            playlists[playlist_name] = []
        if track_index not in playlists[playlist_name]:
            playlists[playlist_name].append(track_index)
            self._save_playlists(playlists)
            logger.info(f"Track {track_index} → '{playlist_name}' playlist'e eklendi")
            return True
        return False

    def remove_from_playlist(self, playlist_name: str, track_index: int) -> bool:
        playlists = self._load_playlists()
        if playlist_name in playlists and track_index in playlists[playlist_name]:
            playlists[playlist_name].remove(track_index)
            self._save_playlists(playlists)
            return True
        return False

    def get_playlist_tracks(self, playlist_name: str) -> List[dict]:
        """Playlist'teki track'leri döndürür."""
        playlists = self._load_playlists()
        indices = playlists.get(playlist_name, [])
        result = []
        for idx in indices:
            track = self.get_track(idx)
            if track:
                track["_lib_index"] = idx
                result.append(track)
        return result


class MusicLibraryDownloader(QThread):
    """YouTube URL'den müzik indir ve kütüphaneye ekle."""

    progress = pyqtSignal(str)
    finished = pyqtSignal(str, str)  # (title, path)
    error = pyqtSignal(str)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self._url = url

    def run(self):
        try:
            import shutil
            yt_dlp_bin = shutil.which("yt-dlp")
            if not yt_dlp_bin:
                # venv içinde olabilir
                venv_bin = os.path.join(config.BASE_DIR, "venv", "bin", "yt-dlp")
                if os.path.exists(venv_bin):
                    yt_dlp_bin = venv_bin
                else:
                    self.error.emit("yt-dlp bulunamadı (pip install yt-dlp)")
                    return

            ffmpeg_bin = shutil.which("ffmpeg")
            if not ffmpeg_bin:
                ffmpeg_bin = "/opt/homebrew/bin/ffmpeg"

            self.progress.emit("🔍 Video bilgisi alınıyor...")

            # Başlık al
            cmd_title = [yt_dlp_bin, "--no-warnings", "--quiet", "--get-title", self._url]
            res_title = subprocess.run(cmd_title, capture_output=True, text=True, timeout=15)
            title = res_title.stdout.strip() if res_title.returncode == 0 else "Bilinmeyen Şarkı"
            safe_title = "".join(c for c in title if c.isalnum() or c in " -_()").strip()[:80]
            if not safe_title:
                safe_title = f"track_{id(self)}"

            out_path = os.path.join(config.MUSIC_DIR, f"{safe_title}.mp3")

            if os.path.exists(out_path):
                self.finished.emit(title, out_path)
                return

            self.progress.emit(f"⬇️ İndiriliyor: {title[:40]}...")

            # yt-dlp ile direkt mp3 olarak indir (tek adım — en güvenilir yöntem)
            cmd = [
                yt_dlp_bin,
                "--no-warnings",
                "-f", "bestaudio/best",
                "-x", "--audio-format", "mp3",
                "--audio-quality", "192K",
                "--ffmpeg-location", os.path.dirname(ffmpeg_bin),
                "-o", out_path.replace(".mp3", ".%(ext)s"),
                "--no-playlist",
                self._url
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)

            # yt-dlp çıktı dosyası .mp3 olmayabilir, kontrol et
            if result.returncode == 0:
                # yt-dlp bazen .mp3 uzantısıyla kaydeder
                if os.path.exists(out_path):
                    self.finished.emit(title, out_path)
                    return
                # Alternatif uzantıları kontrol et
                base = out_path.replace(".mp3", "")
                for ext in [".mp3", ".opus", ".m4a", ".webm"]:
                    candidate = base + ext
                    if os.path.exists(candidate):
                        # mp3 değilse yeniden adlandır (yt-dlp -x zaten dönüştürür)
                        if candidate != out_path:
                            os.rename(candidate, out_path)
                        self.finished.emit(title, out_path)
                        return
                self.error.emit("Dosya indirilemedi — çıktı bulunamadı")
            else:
                err = result.stderr[:120] if result.stderr else "Bilinmeyen hata"
                self.error.emit(f"İndirme hatası: {err}")

        except subprocess.TimeoutExpired:
            self.error.emit("İndirme zaman aşımı (3dk)")
        except FileNotFoundError as e:
            self.error.emit(f"Araç bulunamadı: {e}")
        except Exception as e:
            logger.error(f"Kütüphane indirme hatası: {e}")
            self.error.emit(str(e)[:80])


class YouTubeSearchWorker(QThread):
    """YouTube'da yt-dlp ile arama yap, sonuçları döndür."""

    results_ready = pyqtSignal(list)  # [{title, url, duration, thumbnail}]
    error = pyqtSignal(str)

    def __init__(self, query: str, max_results: int = 8, parent=None):
        super().__init__(parent)
        self._query = query
        self._max = max_results

    def run(self):
        try:
            import shutil, json
            yt_dlp_bin = shutil.which("yt-dlp")
            if not yt_dlp_bin:
                venv_bin = os.path.join(config.BASE_DIR, "venv", "bin", "yt-dlp")
                if os.path.exists(venv_bin):
                    yt_dlp_bin = venv_bin
                else:
                    self.error.emit("yt-dlp bulunamadı")
                    return

            cmd = [
                yt_dlp_bin,
                "--no-warnings", "--quiet",
                "--flat-playlist",
                "--dump-json",
                "--no-download",
                f"ytsearch{self._max}:{self._query}"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            if result.returncode != 0:
                self.error.emit("Arama başarısız")
                return

            items = []
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    dur = data.get("duration") or 0
                    mins, secs = divmod(int(dur), 60)
                    items.append({
                        "title": data.get("title", "?"),
                        "url": data.get("url") or data.get("webpage_url") or f"https://www.youtube.com/watch?v={data.get('id','')}",
                        "duration": f"{mins}:{secs:02d}",
                        "channel": data.get("channel", data.get("uploader", "")),
                    })
                except json.JSONDecodeError:
                    continue

            self.results_ready.emit(items)

        except subprocess.TimeoutExpired:
            self.error.emit("Arama zaman aşımı")
        except Exception as e:
            self.error.emit(str(e)[:80])


class YouTubeStreamResolver(QThread):
    """YouTube video URL'sini direkt audio stream URL'sine çözer."""

    stream_ready = pyqtSignal(str, str)   # (audio_url, title)
    error = pyqtSignal(str)

    def __init__(self, yt_url: str, title: str = "", parent=None):
        super().__init__(parent)
        self._yt_url = yt_url
        self._title = title

    def run(self):
        try:
            import shutil, json
            yt_dlp_bin = shutil.which("yt-dlp")
            if not yt_dlp_bin:
                venv_bin = os.path.join(config.BASE_DIR, "venv", "bin", "yt-dlp")
                yt_dlp_bin = venv_bin if os.path.exists(venv_bin) else None
            if not yt_dlp_bin:
                self.error.emit("yt-dlp bulunamadı")
                return

            cmd = [
                yt_dlp_bin,
                "--no-warnings", "--quiet",
                "-f", "bestaudio[ext=m4a]/bestaudio/best",
                "--get-url",
                self._yt_url
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            audio_url = result.stdout.strip().split("\n")[0]
            if audio_url and audio_url.startswith("http"):
                self.stream_ready.emit(audio_url, self._title)
            else:
                self.error.emit("Stream URL alınamadı")
        except subprocess.TimeoutExpired:
            self.error.emit("Zaman aşımı")
        except Exception as e:
            self.error.emit(str(e)[:80])


class YouTubeTrendWorker(QThread):
    """YouTube müzik trendlerini (TR + global) getir."""

    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    TREND_QUERIES = [
        "Türkçe müzik 2025 en çok dinlenenler",
        "trending music 2025 top hits",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        try:
            import shutil, json, random
            yt_dlp_bin = shutil.which("yt-dlp")
            if not yt_dlp_bin:
                venv_bin = os.path.join(config.BASE_DIR, "venv", "bin", "yt-dlp")
                yt_dlp_bin = venv_bin if os.path.exists(venv_bin) else None
            if not yt_dlp_bin:
                self.error.emit("yt-dlp bulunamadı")
                return

            query = random.choice(self.TREND_QUERIES)
            cmd = [
                yt_dlp_bin,
                "--no-warnings", "--quiet",
                "--flat-playlist", "--dump-json", "--no-download",
                f"ytsearch12:{query}"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
            items = []
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    dur = data.get("duration") or 0
                    mins, secs = divmod(int(dur), 60)
                    items.append({
                        "title": data.get("title", "?"),
                        "url": (data.get("url") or data.get("webpage_url")
                                or f"https://www.youtube.com/watch?v={data.get('id','')}"),
                        "duration": f"{mins}:{secs:02d}",
                        "channel": data.get("channel", data.get("uploader", "")),
                        "is_trend": True,
                    })
                except json.JSONDecodeError:
                    continue
            self.results_ready.emit(items)
        except subprocess.TimeoutExpired:
            self.error.emit("Trend zaman aşımı")
        except Exception as e:
            self.error.emit(str(e)[:80])


class TTSEngine(QThread):
    """edge-tts ile metin→ses dönüşümü."""

    audio_ready = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, text: str, voice: str = "tr-TR-AhmetNeural", parent=None):
        super().__init__(parent)
        self._text = text
        self._voice = voice

    def run(self):
        try:
            import edge_tts

            async def _generate():
                out = os.path.join(tempfile.gettempdir(), f"visionary_tts_{id(self)}.mp3")
                comm = edge_tts.Communicate(self._text, self._voice)
                await comm.save(out)
                return out

            path = asyncio.run(_generate())
            self.audio_ready.emit(path)
        except Exception as e:
            logger.error(f"TTS hatası: {e}")
            self.error.emit(str(e))


class _MusicDownloader(QThread):
    """yt-dlp ile YouTube/web URL'den ses indir."""

    ready = pyqtSignal(str)   # indirilen dosya yolu
    error = pyqtSignal(str)

    def __init__(self, url: str, start_sec: int = 0, duration_sec: int = 120, parent=None):
        super().__init__(parent)
        self._url = url
        self._start = start_sec
        self._duration = duration_sec

    def run(self):
        try:
            import shutil
            yt_dlp_bin = shutil.which("yt-dlp")
            if not yt_dlp_bin:
                venv_bin = os.path.join(config.BASE_DIR, "venv", "bin", "yt-dlp")
                yt_dlp_bin = venv_bin if os.path.exists(venv_bin) else "yt-dlp"

            ffmpeg_bin = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"

            # Benzersiz geçici dosya adı
            import time
            out_path = os.path.join(tempfile.gettempdir(), f"visionary_music_{int(time.time())}.mp3")

            # Önce yt-dlp ile en iyi ses akışını bul
            cmd_extract = [
                yt_dlp_bin,
                "--no-warnings", "--quiet",
                "-f", "bestaudio",
                "--get-url",
                self._url
            ]
            result = subprocess.run(cmd_extract, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                audio_url = self._url
            else:
                audio_url = result.stdout.strip()

            if not audio_url:
                self.error.emit("Ses URL'si alınamadı")
                return

            # ffmpeg ile belirli süre kes ve mp3 olarak kaydet
            cmd_ff = [
                ffmpeg_bin, "-y",
                "-loglevel", "warning",
                "-ss", str(self._start),
                "-i", audio_url,
                "-t", str(self._duration),
                "-vn",
                "-acodec", "libmp3lame",
                "-ab", "128k",
                "-ar", "44100",
                "-write_xing", "0",
                out_path
            ]
            ff_result = subprocess.run(cmd_ff, capture_output=True, text=True, timeout=60)

            if ff_result.returncode == 0 and os.path.exists(out_path):
                size = os.path.getsize(out_path)
                logger.info(f"Müzik indirildi: {size} bytes, başlangıç: {self._start}sn")
                self.ready.emit(out_path)
            else:
                self.error.emit(f"ffmpeg hatası: {ff_result.stderr[:100]}")

        except subprocess.TimeoutExpired:
            self.error.emit("İndirme zaman aşımı")
        except FileNotFoundError as e:
            self.error.emit(f"Araç bulunamadı: {e}")
        except Exception as e:
            logger.error(f"Müzik indirme hatası: {e}")
            self.error.emit(str(e)[:80])


class AudioPlayer:
    """QMediaPlayer ile ses dosyası çalar. Kuyruk sistemiyle sıralı TTS desteği."""

    def __init__(self):
        self._player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._player.setAudioOutput(self._audio_output)
        self._audio_output.setVolume(0.8)
        self._tts_worker: Optional[TTSEngine] = None
        self._on_start_cb: Optional[Callable] = None
        self._on_done_cb: Optional[Callable] = None
        self._done_fired = False
        self._is_speaking = False

        # TTS kuyruk sistemi — konuşmalar sırayla çalır, birbirini kesmez
        self._speech_queue: list = []  # [(text, voice, on_start, on_done), ...]

        # Tek bir bağlantı — biriken lambda'ları önle
        self._player.playbackStateChanged.connect(self._on_playback_state)
        self._player.mediaStatusChanged.connect(self._on_media_status)
        self._player.errorOccurred.connect(self._on_player_error)

    def _on_playback_state(self, state) -> None:
        """Çalma başladığında on_start callback'i tetikle."""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            if self._on_start_cb:
                logger.info("TTS çalmaya başladı — on_start tetikleniyor")
                cb = self._on_start_cb
                self._on_start_cb = None  # Bir kez çağır
                cb()

    def _on_media_status(self, status) -> None:
        """Medya bittiğinde on_done callback'i tetikle ve kuyruktaki sonraki konuşmayı başlat."""
        if status == QMediaPlayer.MediaStatus.EndOfMedia and not self._done_fired:
            self._done_fired = True
            self._is_speaking = False
            if self._on_done_cb:
                logger.info("TTS bitti — on_done tetikleniyor")
                cb = self._on_done_cb
                self._on_done_cb = None
                cb()
            # Kuyrukta bekleyen konuşma varsa 500ms sonra başlat
            if self._speech_queue:
                QTimer.singleShot(500, self._play_next_in_queue)
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            logger.warning("TTS ses dosyası geçersiz/okunamadı")
            self._done_fired = True
            self._is_speaking = False
            if self._on_done_cb:
                cb = self._on_done_cb
                self._on_done_cb = None
                cb()
            if self._speech_queue:
                QTimer.singleShot(500, self._play_next_in_queue)

    def _on_player_error(self, error, error_string="") -> None:
        """Player hatası — loglayıp on_done çağır ki müzik sesi geri açılsın."""
        logger.error(f"AudioPlayer hatası: {error} — {error_string}")
        self._is_speaking = False
        if self._on_done_cb and not self._done_fired:
            self._done_fired = True
            cb = self._on_done_cb
            self._on_done_cb = None
            cb()
        if self._speech_queue:
            QTimer.singleShot(500, self._play_next_in_queue)

    def play_file(self, path: str) -> None:
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.play()

    def speak(self, text: str, voice: str = "tr-TR-AhmetNeural",
              on_start: Callable = None, on_done: Callable = None) -> None:
        """edge-tts ile TTS üret ve çal. Kuyruk sistemiyle sıralı çalışır."""
        if self._is_speaking:
            # Zaten bir konuşma çalıyor — kuyruğa ekle, sırası gelince çalacak
            logger.info(f"TTS kuyruğa eklendi (kuyruk: {len(self._speech_queue)+1}): {text[:50]}...")
            self._speech_queue.append((text, voice, on_start, on_done))
            return

        self._do_speak(text, voice, on_start, on_done)

    def _play_next_in_queue(self) -> None:
        """Kuyruktaki sonraki konuşmayı başlat."""
        if not self._speech_queue:
            return
        if self._is_speaking:
            return  # Hâlâ çalıyor, bekle
        text, voice, on_start, on_done = self._speech_queue.pop(0)
        logger.info(f"Kuyruktan sonraki TTS başlatılıyor (kalan: {len(self._speech_queue)}): {text[:50]}...")
        self._do_speak(text, voice, on_start, on_done)

    def _do_speak(self, text: str, voice: str,
                  on_start: Callable = None, on_done: Callable = None) -> None:
        """Gerçek TTS üretimi ve çalma."""
        self._is_speaking = True
        self._on_start_cb = on_start
        self._on_done_cb = on_done
        self._done_fired = False

        self._tts_worker = TTSEngine(text, voice)

        def _on_ready(path):
            # Dosya boyutunu kontrol et — boş/bozuk olabilir
            if not os.path.exists(path) or os.path.getsize(path) < 500:
                logger.warning(f"TTS dosyası yok veya çok küçük ({path}), macOS fallback deneniyor")
                self._speak_macos_fallback(text, on_start, on_done)
                return
            logger.info(f"TTS dosyası hazır ({os.path.getsize(path)} bytes), çalınıyor: {path}")
            self.play_file(path)

        def _on_tts_error(err):
            logger.warning(f"edge-tts başarısız: {err} — macOS fallback deneniyor")
            self._speak_macos_fallback(text, on_start, on_done)

        self._tts_worker.audio_ready.connect(_on_ready)
        self._tts_worker.error.connect(_on_tts_error)
        self._tts_worker.start()

    def _speak_macos_fallback(self, text: str, on_start: Callable = None,
                               on_done: Callable = None) -> None:
        """macOS 'say' komutu ile offline TTS fallback — asenkron (Qt event loop bloklamaz)."""
        if on_start:
            on_start()
        logger.info("macOS 'say' komutu ile TTS deneniyor (asenkron)...")

        class _SayThread(QThread):
            finished_signal = pyqtSignal()

            def __init__(self, say_text):
                super().__init__()
                self._text = say_text

            def run(self):
                try:
                    subprocess.run(
                        ["say", "-v", "Yelda", self._text],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=30,
                    )
                except Exception as e:
                    logger.error(f"macOS TTS hatası: {e}")
                self.finished_signal.emit()

        self._say_thread = _SayThread(text)

        def _on_say_done():
            logger.info("macOS TTS bitti")
            self._is_speaking = False
            if on_done:
                on_done()
            if self._speech_queue:
                QTimer.singleShot(500, self._play_next_in_queue)

        self._say_thread.finished_signal.connect(_on_say_done)
        self._say_thread.start()

    def stop(self) -> None:
        self._player.stop()

    def set_volume(self, vol: float) -> None:
        self._audio_output.setVolume(vol)


class STTEngine(QThread):
    """SpeechRecognition ile ses→metin."""

    text_recognized = pyqtSignal(str)
    listening_started = pyqtSignal()
    listening_stopped = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, language: str = "tr-TR", parent=None):
        super().__init__(parent)
        self._language = language

    def run(self):
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            recognizer.dynamic_energy_threshold = True

            with sr.Microphone() as source:
                self.listening_started.emit()
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=10, phrase_time_limit=15)
                self.listening_stopped.emit()

            text = recognizer.recognize_google(audio, language=self._language)
            if text:
                self.text_recognized.emit(text)
            else:
                self.error.emit("Ses algılanamadı")

        except Exception as e:
            self.listening_stopped.emit()
            msg = str(e)
            if "timed out" in msg.lower():
                self.error.emit("Zaman aşımı — ses algılanamadı")
            else:
                logger.error(f"STT hatası: {e}")
                self.error.emit(msg[:80])


class _WeatherWorker(QThread):
    """IP tabanlı konum tespiti + hava durumu bilgisi çeker."""

    finished = pyqtSignal(str, str, str, str)  # (şehir, sıcaklık, açıklama, ekstra)
    error = pyqtSignal(str)

    def run(self):
        import urllib.request
        import json as _json

        # Önce konum al (bağımsız olarak)
        city = ""
        lat = lon = 0
        try:
            city, lat, lon = self._get_location(urllib.request, _json)
        except Exception as e:
            logger.warning(f"Konum tespiti başarısız: {e}")

        # Hava durumu API'lerini dene
        # 1) Open-Meteo
        if lat and lon:
            try:
                self._try_open_meteo_weather(urllib.request, _json, city, lat, lon)
                return
            except Exception as e1:
                logger.warning(f"Open-Meteo hava durumu başarısız: {e1}")

        # 2) wttr.in (kendi konum tespitini de yapar)
        try:
            self._try_wttr(urllib.request, _json)
            return
        except Exception as e2:
            logger.warning(f"wttr.in de başarısız: {e2}")

        # Her iki API de başarısız — en azından şehir adı varsa gönder
        if city:
            self.finished.emit(city, "?", "bilinmeyen hava koşullarında", "Hava durumu servisleri şu an yanıt vermiyor.")
        else:
            self.error.emit("Tüm hava durumu API'leri başarısız")

    def _get_location(self, urllib_request, _json):
        """IP'den konum tespiti — birden fazla servisle fallback."""
        errors = []

        # 1) ipinfo.io (HTTPS, güvenilir)
        try:
            req = urllib_request.Request(
                "https://ipinfo.io/json",
                headers={"User-Agent": "VisionaryNavigator/1.0"}
            )
            resp = urllib_request.urlopen(req, timeout=6)
            data = _json.loads(resp.read().decode("utf-8"))
            city = data.get("city", "Bilinmeyen")
            loc = data.get("loc", "0,0").split(",")
            lat = float(loc[0])
            lon = float(loc[1])
            logger.info(f"Konum (ipinfo.io): {city} ({lat}, {lon})")
            return city, lat, lon
        except Exception as e:
            errors.append(f"ipinfo.io: {e}")

        # 2) ipapi.co (HTTPS, alternatif)
        try:
            req = urllib_request.Request(
                "https://ipapi.co/json/",
                headers={"User-Agent": "VisionaryNavigator/1.0"}
            )
            resp = urllib_request.urlopen(req, timeout=6)
            data = _json.loads(resp.read().decode("utf-8"))
            city = data.get("city", "Bilinmeyen")
            lat = float(data.get("latitude", 0))
            lon = float(data.get("longitude", 0))
            logger.info(f"Konum (ipapi.co): {city} ({lat}, {lon})")
            return city, lat, lon
        except Exception as e:
            errors.append(f"ipapi.co: {e}")

        # 3) ip-api.com (HTTP, son çare)
        try:
            req = urllib_request.Request(
                "http://ip-api.com/json/?fields=city,lat,lon,country&lang=tr",
                headers={"User-Agent": "VisionaryNavigator/1.0"}
            )
            resp = urllib_request.urlopen(req, timeout=6)
            data = _json.loads(resp.read().decode("utf-8"))
            city = data.get("city", "Bilinmeyen")
            lat = float(data.get("lat", 0))
            lon = float(data.get("lon", 0))
            logger.info(f"Konum (ip-api.com): {city} ({lat}, {lon})")
            return city, lat, lon
        except Exception as e:
            errors.append(f"ip-api.com: {e}")

        # Hiçbiri çalışmadıysa hata fırlat
        raise ConnectionError(f"Konum tespiti başarısız: {'; '.join(errors)}")

    def _try_open_meteo_weather(self, urllib_request, _json, city, lat, lon):
        """Open-Meteo API ile hava durumu al (konum zaten biliniyor)."""
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m"
            f"&timezone=auto"
        )
        w_req = urllib_request.Request(weather_url, headers={"User-Agent": "VisionaryNavigator/1.0"})
        w_resp = urllib_request.urlopen(w_req, timeout=8)
        w_data = _json.loads(w_resp.read().decode("utf-8"))

        current = w_data.get("current", {})
        temp = str(round(current.get("temperature_2m", 0)))
        wind = current.get("wind_speed_10m", 0)
        humidity = current.get("relative_humidity_2m", 0)
        code = current.get("weather_code", 0)

        # WMO hava kodu → Türkçe açıklama
        desc = self._wmo_to_turkish(code)

        # Ekstra bilgi
        extras = []
        if wind and wind > 20:
            extras.append(f"Rüzgar oldukça kuvvetli, saatte {round(wind)} kilometre.")
        elif wind and wind > 0:
            extras.append(f"Rüzgar hızı saatte {round(wind)} kilometre.")
        if humidity:
            extras.append(f"Nem oranı yüzde {humidity}.")

        extra = " ".join(extras)
        self.finished.emit(city, temp, desc, extra)

    def _try_wttr(self, urllib_request, _json):
        """wttr.in API ile hava durumu al (fallback)."""
        req = urllib_request.Request(
            "https://wttr.in/?format=j1",
            headers={"User-Agent": "VisionaryNavigator/1.0", "Accept-Language": "tr"}
        )
        resp = urllib_request.urlopen(req, timeout=10)
        data = _json.loads(resp.read().decode("utf-8"))

        # Konum bilgisi
        nearest = data.get("nearest_area", [{}])[0]
        city = nearest.get("areaName", [{}])[0].get("value", "Bilinmeyen")

        # Mevcut hava durumu
        current = data.get("current_condition", [{}])[0]
        temp = current.get("temp_C", "?")
        humidity = current.get("humidity", "")
        wind_kmph = current.get("windspeedKmph", "")

        # Açıklama — Türkçe lang desc varsa kullan
        desc_list = current.get("lang_tr", [])
        if desc_list:
            desc = desc_list[0].get("value", "değişken")
        else:
            desc = current.get("weatherDesc", [{}])[0].get("value", "değişken")

        # Ekstra bilgi
        extras = []
        try:
            w = int(wind_kmph)
            if w > 20:
                extras.append(f"Rüzgar oldukça kuvvetli, saatte {w} kilometre.")
            elif w > 0:
                extras.append(f"Rüzgar hızı saatte {w} kilometre.")
        except (ValueError, TypeError):
            pass
        if humidity:
            extras.append(f"Nem oranı yüzde {humidity}.")

        extra = " ".join(extras)
        self.finished.emit(city, temp, desc, extra)

    @staticmethod
    def _wmo_to_turkish(code: int) -> str:
        """WMO hava durumu kodunu Türkçe açıklamaya çevirir."""
        mapping = {
            0: "açık ve güneşli",
            1: "genellikle açık",
            2: "parçalı bulutlu",
            3: "kapalı ve bulutlu",
            45: "sisli",
            48: "yoğun sisli",
            51: "hafif çiseleyen yağmurlu",
            53: "çiseleyen yağmurlu",
            55: "yoğun çiseleyen yağmurlu",
            61: "hafif yağmurlu",
            63: "yağmurlu",
            65: "şiddetli yağmurlu",
            71: "hafif kar yağışlı",
            73: "kar yağışlı",
            75: "yoğun kar yağışlı",
            77: "kar taneli",
            80: "hafif sağanak yağışlı",
            81: "sağanak yağışlı",
            82: "şiddetli sağanak yağışlı",
            85: "hafif kar sağanağı",
            86: "yoğun kar sağanağı",
            95: "gök gürültülü fırtınalı",
            96: "dolu ile fırtınalı",
            99: "şiddetli dolu ile fırtınalı",
        }
        return mapping.get(code, "değişken hava koşullarında")


class _InstagramWorker(QThread):
    """Instagram'dan kullanıcının son 7 gün içindeki paylaşımını çeker."""

    finished = pyqtSignal(str, str, str)  # (caption, post_url, post_type)
    error = pyqtSignal(str)

    def __init__(self, username: str, parent=None):
        super().__init__(parent)
        self._username = username.lstrip("@").strip()

    def run(self):
        import threading

        result = {"ok": False}

        def _fetch():
            try:
                import instaloader
                import datetime

                L = instaloader.Instaloader(
                    download_pictures=False,
                    download_videos=False,
                    download_video_thumbnails=False,
                    download_comments=False,
                    download_geotags=False,
                    save_metadata=False,
                    compress_json=False,
                    quiet=True,
                )
                L.context._session.headers["User-Agent"] = (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )

                profile = instaloader.Profile.from_username(L.context, self._username)

                now = datetime.datetime.now(datetime.timezone.utc)
                seven_days_ago = now - datetime.timedelta(days=7)

                latest_post = None
                for post in profile.get_posts():
                    if post.date_utc.replace(tzinfo=datetime.timezone.utc) < seven_days_ago:
                        break
                    if latest_post is None:
                        latest_post = post
                    break  # Sadece en son paylaşıma bak, gereksiz iterasyon yapma

                if latest_post is None:
                    result["error"] = "Son 7 günde paylaşım bulunamadı"
                    return

                caption = latest_post.caption or ""
                post_url = f"https://www.instagram.com/p/{latest_post.shortcode}/"

                if latest_post.is_video:
                    post_type = "video"
                elif latest_post.typename == "GraphSidecar":
                    post_type = "carousel"
                else:
                    post_type = "photo"

                result["ok"] = True
                result["caption"] = caption[:500]
                result["url"] = post_url
                result["type"] = post_type

            except Exception as e:
                result["error"] = str(e)[:100]

        # Alt thread ile çalıştır — 15 sn timeout
        t = threading.Thread(target=_fetch, daemon=True)
        t.start()
        t.join(timeout=15)

        if not t.is_alive() and result.get("ok"):
            self.finished.emit(result["caption"], result["url"], result["type"])
        else:
            err = result.get("error", "Zaman aşımı (15s)")
            logger.info(f"Instagram atlanıyor: {err}")
            self.error.emit(err)


class _InstagramCommentWorker(QThread):
    """Instagram paylaşımının açıklamasını Gemini ile yorumlayan worker."""

    finished = pyqtSignal(str)  # yorum metni
    error = pyqtSignal(str)

    def __init__(self, caption: str, post_type: str, parent=None):
        super().__init__(parent)
        self._caption = caption
        self._post_type = post_type

    def run(self):
        try:
            from settings_manager import SettingsManager
            settings = SettingsManager()
            api_key = settings.gemini_api_key

            if not api_key:
                self.error.emit("Gemini API key yok")
                return

            from google import genai

            client = genai.Client(api_key=api_key)

            prompt = (
                f"Kullanıcının Instagram'da son paylaştığı {self._post_type} "
                f"paylaşımının açıklaması şu:\n\n"
                f"\"{self._caption}\"\n\n"
                f"Bu paylaşım hakkında kısa, samimi ve dostça bir yorum yap. "
                f"Türkçe konuş, sanki yakın bir arkadaşı gibi. "
                f"Maksimum 2 cümle olsun. Emoji kullanma. "
                f"Cevabını direkt yorum olarak ver, başka açıklama ekleme."
            )

            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
            )

            comment = response.text.strip() if response.text else ""
            if comment:
                # TTS için ön ek ekle
                intro = "Bu arada, Instagram'daki son paylaşımını gördüm. "
                self.finished.emit(intro + comment)
            else:
                self.error.emit("Gemini boş yanıt döndü")

        except Exception as e:
            logger.error(f"Instagram yorum AI hatası: {e}")
            self.error.emit(str(e)[:80])


class WelcomeGreeting:
    """Başlangıç müzik + sesli hoşgeldin + hava durumu. Müzik bağımsız olarak devam eder."""

    def __init__(self, music_url: str = "", voice: str = "tr-TR-AhmetNeural",
                 music_start_sec: int = 0):
        self._music_url = music_url
        self._voice = voice
        self._music_start = music_start_sec

        # TTS için ayrı AudioPlayer (müzikten tamamen bağımsız)
        self._tts_player = AudioPlayer()

        # Müzik için ayrı QMediaPlayer + QAudioOutput (kendi yaşam döngüsü)
        self._music_player = QMediaPlayer()
        self._music_output = QAudioOutput()
        self._music_player.setAudioOutput(self._music_output)
        self._music_output.setVolume(0.25)

        # Müzik durumunu izle — hata varsa logla
        self._music_player.errorOccurred.connect(self._on_music_error)
        self._music_player.mediaStatusChanged.connect(self._on_music_status)

        # İndirici referansı (GC koruması)
        self._downloader: Optional[_MusicDownloader] = None

        # Hava durumu worker
        self._weather_worker: Optional[_WeatherWorker] = None

        # Instagram worker
        self._ig_worker: Optional[_InstagramWorker] = None
        self._ig_comment_thread: Optional[_InstagramCommentWorker] = None
        self._ig_caption: str = ""
        self._ig_post_type: str = ""

        # Müzik durumu
        self._is_playing = False
        self._shuffle_mode = False
        self._repeat_mode = 0  # 0=kapalı, 1=tümü, 2=tek şarkı

        # Playlist sistemi
        self._playlist_mode = False
        self._music_library: Optional[MusicLibrary] = None
        self._current_track_index: int = -1
        self._current_track_title: str = ""
        self._current_track_url: str = ""  # YouTube URL
        self._on_track_changed_cb: Optional[Callable] = None  # (title, url, index) callback

    def _on_music_error(self, error, error_string=""):
        """Müzik çalma hatalarını logla."""
        logger.warning(f"Müzik player hatası: {error} — {error_string}")

    def _on_music_status(self, status):
        """Müzik durum değişikliklerini izle — şarkı bitince sıradakine geç."""
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            # Tek şarkı tekrarı
            if self._repeat_mode == 2:
                self._music_player.setPosition(0)
                self._music_player.play()
                return
            # Playlist modunda sıradaki şarkıya geç
            if self._playlist_mode and self._music_library:
                if self._shuffle_mode:
                    import random
                    count = self._music_library.track_count
                    if count > 1:
                        next_idx = self._current_track_index
                        while next_idx == self._current_track_index:
                            next_idx = random.randint(0, count - 1)
                    else:
                        next_idx = 0
                    self._play_track_at_index(next_idx)
                    return
                next_idx = self._current_track_index + 1
                if next_idx < self._music_library.track_count:
                    self._play_track_at_index(next_idx)
                    logger.info(f"Sıradaki şarkıya geçildi: index={next_idx}")
                    return
                elif self._repeat_mode == 1:
                    self._play_track_at_index(0)
                    logger.info("Playlist başa döndü (tekrar modu)")
                    return
                else:
                    # Playlist bitti, tekrar kapalı — dur
                    self._is_playing = False
                    return
            # Playlist yoksa loop
            logger.info("Müzik bitti, döngüye alınıyor.")
            self._music_player.setPosition(0)
            self._music_player.play()
        elif status == QMediaPlayer.MediaStatus.LoadedMedia:
            logger.info("Müzik yüklendi, çalınıyor.")
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            logger.warning("Geçersiz müzik dosyası.")
            # Geçersiz dosyaysa sıradakine atla
            if self._playlist_mode and self._music_library:
                next_idx = self._current_track_index + 1
                if next_idx < self._music_library.track_count:
                    QTimer.singleShot(500, lambda: self._play_track_at_index(next_idx))

    def play(self) -> None:
        """Müzik indir + hava durumu al + Instagram kontrol et + hoşgeldin TTS."""
        if self._music_url:
            self._downloader = _MusicDownloader(
                self._music_url,
                start_sec=self._music_start,
                duration_sec=120
            )
            self._downloader.ready.connect(self._on_music_ready)
            self._downloader.error.connect(lambda e: logger.warning(f"Müzik hatası: {e}"))
            self._downloader.start()

        # Hava durumu bilgisini arka planda al, sonra TTS ile selamla
        self._weather_worker = _WeatherWorker()
        self._weather_worker.finished.connect(self._on_weather_ready)
        self._weather_worker.error.connect(self._on_weather_error)
        self._weather_worker.start()

        # Instagram — ayarlarda hesap varsa başlat (bağımsız, hata toleranslı)
        try:
            self._start_instagram_check()
        except Exception as e:
            logger.info(f"Instagram atlandı: {e}")

    def _start_instagram_check(self) -> None:
        """Ayarlardan Instagram kullanıcı adını al ve son paylaşımı çek."""
        try:
            from settings_manager import SettingsManager
            settings = SettingsManager()
            social = settings.social_accounts
            ig_username = ""
            for platform, value in social.items():
                if "instagram" in platform.lower():
                    # URL veya kullanıcı adı olabilir
                    val = value.strip().rstrip("/")
                    if "instagram.com/" in val:
                        ig_username = val.split("instagram.com/")[-1].split("?")[0].strip("/")
                    else:
                        ig_username = val.lstrip("@")
                    break

            if not ig_username:
                logger.info("Instagram hesabı ayarlarda bulunamadı, atlanıyor.")
                return

            logger.info(f"Instagram kontrol ediliyor: @{ig_username}")
            self._ig_worker = _InstagramWorker(ig_username)
            self._ig_worker.finished.connect(self._on_instagram_ready)
            self._ig_worker.error.connect(lambda e: logger.info(f"Instagram: {e}"))
            self._ig_worker.start()

        except Exception as e:
            logger.warning(f"Instagram başlatma hatası: {e}")

    def _on_instagram_ready(self, caption: str, post_url: str, post_type: str) -> None:
        """Instagram paylaşımı geldi — Gemini ile yorumla ve TTS ile söyle."""
        logger.info(f"Instagram paylaşım bulundu ({post_type}): {caption[:60]}...")
        self._ig_caption = caption
        self._ig_post_type = post_type

        # Gemini ile yorumlat (arka planda)
        self._ig_comment_thread = _InstagramCommentWorker(caption, post_type)
        self._ig_comment_thread.finished.connect(self._on_ig_comment_ready)
        self._ig_comment_thread.error.connect(
            lambda e: logger.warning(f"Instagram yorum AI hatası: {e}")
        )
        self._ig_comment_thread.start()

    def _on_ig_comment_ready(self, comment: str) -> None:
        """Gemini yorumu geldi — TTS kuyruğuna ekle (sırası gelince söyler)."""
        if comment:
            logger.info(f"Instagram AI yorumu kuyruğa ekleniyor: {comment[:80]}...")
            self._tts_player.speak(
                comment, self._voice,
                on_start=self._duck_music,
                on_done=self._unduck_music,
            )

    def _on_weather_ready(self, city: str, temp: str, desc: str, extra: str) -> None:
        """Hava durumu geldi — kişiselleştirilmiş selamlama yap."""
        import datetime
        hour = datetime.datetime.now().hour
        if hour < 6:
            greeting = "İyi geceler"
        elif hour < 12:
            greeting = "Günaydın"
        elif hour < 18:
            greeting = "İyi günler"
        else:
            greeting = "İyi akşamlar"

        msg = (
            f"{greeting} efendim! Visionary Navigator hazır. "
            f"Şu anda {city} konumundasınız. "
            f"Hava {desc}, sıcaklık {temp} derece. {extra}"
        )
        logger.info(f"Hoşgeldin + hava durumu: {msg}")
        self._tts_player.speak(
            msg, self._voice,
            on_start=self._duck_music,
            on_done=self._unduck_music,
        )

    def _on_weather_error(self, err: str) -> None:
        """Hava durumu alınamazsa sadece basit selamlama yap."""
        import datetime
        hour = datetime.datetime.now().hour
        if hour < 6:
            greeting = "İyi geceler"
        elif hour < 12:
            greeting = "Günaydın"
        elif hour < 18:
            greeting = "İyi günler"
        else:
            greeting = "İyi akşamlar"

        logger.warning(f"Hava durumu hatası: {err}")
        self._tts_player.speak(
            f"{greeting} efendim! Visionary Navigator hazır.",
            self._voice,
            on_start=self._duck_music,
            on_done=self._unduck_music,
        )

    def _duck_music(self) -> None:
        """TTS konuşurken müzik sesini kıs (ama tamamen kapatma)."""
        self._pre_duck_volume = self._music_output.volume()
        self._music_output.setVolume(0.12)
        logger.info("Müzik sesi kısıldı (TTS konuşuyor)")

    def _unduck_music(self) -> None:
        """TTS bittikten sonra müzik sesini geri aç."""
        vol = getattr(self, '_pre_duck_volume', 0.25)
        self._music_output.setVolume(vol)
        logger.info("Müzik sesi geri açıldı")

    def _on_music_ready(self, path: str) -> None:
        """İndirilen müziği çal."""
        logger.info(f"Başlangıç müziği çalınıyor: {path}")
        self._music_player.setSource(QUrl.fromLocalFile(path))
        # Küçük gecikme ile çal (source set edildikten hemen sonra çalmayı garanti et)
        QTimer.singleShot(200, self._music_player.play)
        self._is_playing = True

    def stop_music(self) -> None:
        self._music_player.stop()
        self._is_playing = False

    def pause_music(self) -> None:
        self._music_player.pause()
        self._is_playing = False

    def resume_music(self) -> None:
        self._music_player.play()
        self._is_playing = True

    def toggle_music(self) -> bool:
        """Müziği aç/kapat. Yeni durumu döndürür (True=çalıyor)."""
        if self._is_playing:
            self.pause_music()
            return False
        else:
            self.resume_music()
            return True

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    def set_volume(self, vol: float) -> None:
        self._music_output.setVolume(max(0.0, min(1.0, vol)))

    @property
    def volume(self) -> float:
        return self._music_output.volume()

    def set_library(self, library: 'MusicLibrary') -> None:
        """Müzik kütüphanesini bağla — playlist modu için."""
        self._music_library = library

    def set_on_track_changed(self, callback: Callable) -> None:
        """Şarkı değiştiğinde çağrılacak callback: callback(title, url, index)"""
        self._on_track_changed_cb = callback

    def _play_track_at_index(self, index: int) -> None:
        """Kütüphanedeki belirli indeksteki şarkıyı çal."""
        if not self._music_library:
            return
        track = self._music_library.get_track(index)
        if not track:
            return
        path = track.get("path", "")
        if not os.path.exists(path):
            logger.warning(f"Track dosyası bulunamadı: {path}")
            return
        self._current_track_index = index
        self._current_track_title = track.get("title", "Bilinmeyen")
        self._current_track_url = track.get("url", "")
        self._playlist_mode = True
        self._music_player.setSource(QUrl.fromLocalFile(path))
        QTimer.singleShot(200, self._music_player.play)
        self._is_playing = True
        logger.info(f"Playlist çalınıyor [{index}]: {self._current_track_title[:40]}")
        # Track değişim callback
        if self._on_track_changed_cb:
            try:
                self._on_track_changed_cb(self._current_track_title,
                                          self._current_track_url,
                                          self._current_track_index)
            except Exception as e:
                logger.warning(f"Track changed callback hatası: {e}")

    def play_next_track(self) -> None:
        """Sıradaki şarkıya geç."""
        if not self._music_library:
            return
        next_idx = self._current_track_index + 1
        if next_idx >= self._music_library.track_count:
            next_idx = 0
        self._play_track_at_index(next_idx)

    def play_prev_track(self) -> None:
        """Önceki şarkıya geç."""
        if not self._music_library:
            return
        prev_idx = self._current_track_index - 1
        if prev_idx < 0:
            prev_idx = max(0, self._music_library.track_count - 1)
        self._play_track_at_index(prev_idx)

    @property
    def current_track_title(self) -> str:
        return self._current_track_title

    @property
    def current_track_url(self) -> str:
        return self._current_track_url

    @property
    def current_track_index(self) -> int:
        return self._current_track_index

    def seek_forward(self, secs: int = 10) -> None:
        """Müziği ilerlet (varsayılan 10 saniye)."""
        pos = self._music_player.position()
        dur = self._music_player.duration()
        new_pos = min(pos + secs * 1000, dur - 500 if dur > 0 else pos)
        self._music_player.setPosition(max(0, new_pos))
        logger.info(f"Müzik ileri sarıldı: {pos}ms → {new_pos}ms")

    def seek_backward(self, secs: int = 10) -> None:
        """Müziği geri sar (varsayılan 10 saniye)."""
        pos = self._music_player.position()
        new_pos = max(0, pos - secs * 1000)
        self._music_player.setPosition(new_pos)
        logger.info(f"Müzik geri sarıldı: {pos}ms → {new_pos}ms")

    def play_library_track(self, path: str) -> None:
        """Kütüphaneden bir şarkıyı çal — playlist modunu aktifle."""
        # Kütüphanede index bul (fuzzy dahil)
        if self._music_library:
            idx = self._music_library.find_index_by_path(path)
            if idx >= 0:
                # Library'deki kaydı kullan (gerçek path)
                track = self._music_library.get_track(idx)
                real_path = track.get("path", path) if track else path
                # Gerçek path ile kaydı güncelle
                if track and real_path != path and os.path.exists(real_path):
                    track["path"] = real_path
                self._play_track_at_index(idx)
                return
        # Kütüphane yoksa direkt çal
        if os.path.exists(path):
            self._current_track_title = os.path.basename(path).replace(".mp3", "")
            self._current_track_url = ""
            self._music_player.setSource(QUrl.fromLocalFile(path))
            QTimer.singleShot(200, self._music_player.play)
            self._is_playing = True
            if self._on_track_changed_cb:
                try:
                    self._on_track_changed_cb(self._current_track_title, "", -1)
                except Exception:
                    pass

    def play_stream_url(self, url: str, title: str = "") -> None:
        """YouTube URL veya herhangi bir stream URL'yi indirmeden çal."""
        self._current_track_title = title or url[:60]
        self._current_track_url = url
        self._playlist_mode = False
        self._music_player.setSource(QUrl(url))
        QTimer.singleShot(200, self._music_player.play)
        self._is_playing = True
        logger.info(f"Stream çalınıyor: {title[:40]}")
        if self._on_track_changed_cb:
            try:
                self._on_track_changed_cb(self._current_track_title,
                                          self._current_track_url, -1)
            except Exception as e:
                logger.warning(f"Track changed callback hatası: {e}")
