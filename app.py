import os
import tempfile
import subprocess
import requests
from flask import Flask, request, jsonify, send_file, abort
from flask_cors import CORS
import yt_dlp
import instaloader
import re
import time
import random

app = Flask(__name__)
CORS(app)

def sizeof_fmt(num, suffix="B"):
    try:
        num = int(num)
    except:
        return "Unknown"
    for unit in ["","K","M","G","T"]:
        if abs(num) < 1024:
            return f"{num:.2f} {unit}{suffix}"
        num /= 1024
    return f"{num:.2f} P{suffix}"

@app.route('/get_info', methods=['POST'])
def get_info():
    video_url = request.json.get('url')
    if not video_url:
        return jsonify({'error': 'No URL provided.'}), 400

    if "youtube.com" in video_url or "youtu.be" in video_url:
        platform = 'youtube'
        cookie_file = 'cookies_youtube.txt'
    elif "instagram.com" in video_url:
        platform = 'insta'
        cookie_file = 'cookies_insta.txt'
    elif "facebook.com" in video_url:
        platform = 'facebook'
        cookie_file = 'cookies_facebook.txt'
    elif "pinterest.com" in video_url:
        platform = 'pinterest'
        cookie_file = 'cookies_pinterest.txt'
    else:
        platform = 'other'
        cookie_file = None

    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'noplaylist': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    if cookie_file:
        ydl_opts['cookiefile'] = cookie_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            if not info:
                return jsonify({'error': 'Failed to fetch video info.'}), 400
            if 'entries' in info and isinstance(info['entries'], list):
                info = info['entries'][0] if info['entries'] else {}

            resp = {
                'title': info.get('title', ''),
                'thumbnail': info.get('thumbnail', ''),
                'duration': int(info.get('duration') or 0),
                'formats': info.get('formats', []),
                'formats_raw': info.get('formats', []),
                'width': None,
                'height': None,
                'aspect_ratio': None
            }

            width = info.get('width')
            height = info.get('height')
            formats = resp['formats']

            if not width or not height:
                best_format = None
                for f in formats:
                    if 'width' in f and 'height' in f and f.get('url'):
                        if not best_format or f['width'] > best_format['width']:
                            best_format = f
                if best_format:
                    width = best_format['width']
                    height = best_format['height']

            if width and height:
                resp['width'] = width
                resp['height'] = height
                resp['aspect_ratio'] = f"{width}:{height}"

            if platform == 'youtube':
                audio_formats = []
                video_formats = []
                for f in formats:
                    if not f.get('url'):
                        continue
                    size_val = f.get('filesize') or f.get('filesize_approx')
                    readable_size = sizeof_fmt(size_val) if size_val else "Unknown"
                    out = {
                        'format_id': f.get('format_id', ''),
                        'format_note': f.get('format_note', ''),
                        'extension': f.get('ext', ''),
                        'filesize': readable_size,
                        'filesize_bytes': size_val,
                        'resolution': str(f.get('height') or f.get('format_note') or 'audio'),
                        'acodec': f.get('acodec'),
                        'vcodec': f.get('vcodec'),
                        'abr': f.get('abr'),
                        'tbr': f.get('tbr'),
                        'fps': f.get('fps'),
                        'url': f.get('url'),
                    }
                    if f.get('vcodec', 'none') == 'none':
                        audio_formats.append(out)
                    else:
                        video_formats.append(out)
                video_formats = sorted(video_formats, key=lambda x: int(x['resolution']) if x['resolution'].isdigit() else 0, reverse=True)
                audio_formats = sorted(audio_formats, key=lambda x: float(x['abr']) if x['abr'] else 0, reverse=True)
                resp['audio_formats'] = audio_formats
                resp['video_formats'] = video_formats
            else:
                best_muxed = None
                best_video = None
                best_audio = None

                for f in formats:
                    if not f.get('url'):
                        continue
                    if f.get('vcodec', 'none') != 'none' and f.get('acodec', 'none') != 'none':
                        if not best_muxed or (f.get('height', 0) or 0) > (best_muxed['height'] or 0):
                            best_muxed = f
                    if f.get('vcodec', 'none') != 'none':
                        if not best_video or (f.get('height', 0) or 0) > (best_video['height'] or 0):
                            best_video = f
                    if f.get('acodec', 'none') != 'none' and f.get('vcodec', 'none') == 'none':
                        if not best_audio or (f.get('abr', 0) or 0) > (best_audio['abr'] or 0):
                            best_audio = f

                if best_muxed:
                    size_val = best_muxed.get('filesize') or best_muxed.get('filesize_approx')
                    resp['video_muxed'] = {
                        'resolution': str(best_muxed['height']) + "p" if best_muxed['height'] else "HD",
                        'extension': best_muxed.get('ext'),
                        'filesize': sizeof_fmt(size_val) if size_val else "Unknown",
                        'filesize_bytes': size_val,
                        'url': best_muxed.get('url'),
                        'tbr': best_muxed.get('tbr'),
                        'fps': best_muxed.get('fps'),
                    }

                if best_video and (not best_muxed or best_video['url'] != best_muxed['url']):
                    size_val = best_video.get('filesize') or best_video.get('filesize_approx')
                    resp['video_only'] = {
                        'resolution': str(best_video['height']) + "p" if best_video['height'] else "HD",
                        'extension': best_video.get('ext'),
                        'filesize': sizeof_fmt(size_val) if size_val else "Unknown",
                        'filesize_bytes': size_val,
                        'url': best_video.get('url'),
                        'tbr': best_video.get('tbr'),
                        'fps': best_video.get('fps'),
                    }

                if best_audio:
                    size_val = best_audio.get('filesize') or best_audio.get('filesize_approx')
                    resp['audio'] = {
                        'extension': best_audio.get('ext'),
                        'filesize': sizeof_fmt(size_val) if size_val else "Unknown",
                        'filesize_bytes': size_val,
                        'url': best_audio.get('url'),
                        'abr': best_audio.get('abr'),
                    }

            return jsonify(resp)
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 400

# ---- Instagram multi-image endpoint (yt-dlp, video/reel) ----

@app.route('/api/ig_photos', methods=['POST'])
def ig_photos():
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        if not url or "instagram.com" not in url:
            return jsonify({"status": "fail", "error": "Invalid Instagram URL."})

        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'forcejson': True,
            'noplaylist': True,
        }
        cookie_file = 'cookies_insta.txt'
        if cookie_file and os.path.exists(cookie_file):
            ydl_opts['cookiefile'] = cookie_file
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        photos = []
        caption = ""

        if "entries" in info and isinstance(info["entries"], list):
            for entry in info["entries"]:
                if entry.get("ext") in ("jpg", "jpeg", "png", "webp"):
                    photos.append({
                        "url": entry.get("url"),
                        "caption": entry.get("description", ""),
                        "ext": entry.get("ext"),
                        "size": entry.get("filesize_approx"),
                        "width": entry.get("width", 0),
                        "height": entry.get("height", 0)
                    })
                    if not caption:
                        caption = entry.get("description", "")
        elif info.get("ext") in ("jpg", "jpeg", "png", "webp"):
            photos.append({
                "url": info.get("url"),
                "caption": info.get("description", ""),
                "ext": info.get("ext"),
                "size": info.get("filesize_approx"),
                "width": info.get("width", 0),
                "height": info.get("height", 0)
            })
            caption = info.get("description", "")

        if not photos:
            return jsonify({"status": "fail", "error": "No photos found in this post"})

        return jsonify({"status": "ok", "caption": caption, "photos": photos})

    except Exception as e:
        print("[IG_PHOTOS ERROR]:", str(e))
        return jsonify({"status": "fail", "error": str(e)}), 500

# ---- NEW! Ultimate IG image multi-method endpoint ----

@app.route('/api/ig_photo_dl', methods=['POST'])
def ig_photo_dl():
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        if not url or "instagram.com/p/" not in url:
            return jsonify({"status": "fail", "error": "Invalid Instagram photo URL."})

        match = re.search(r"instagram\.com/p/([^/?#&]+)/?", url)
        if not match:
            return jsonify({"status": "fail", "error": "Invalid Instagram post URL or missing shortcode."})
        shortcode = match.group(1)

        user_agents = [
            'Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (Android 12; Mobile; rv:98.0) Gecko/98.0 Firefox/98.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.75 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 12_3_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36'
        ]

        # --- METHOD 1: Instaloader ---
        try:
            L = instaloader.Instaloader(
                download_pictures=False,
                download_video_thumbnails=False,
                download_videos=False,
                quiet=True,
                save_metadata=False,
                max_connection_attempts=3
            )
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            photos = []
            caption = post.caption or ""
            if post.typename == 'GraphSidecar':
                for node in post.get_sidecar_nodes():
                    if not node.is_video:
                        photos.append({
                            "url": node.display_url,
                            "caption": caption,
                            "width": getattr(node, 'dimensions', [1080, 1080])[0],
                            "height": getattr(node, 'dimensions', [1080, 1080])[1],
                            "ext": "jpg"
                        })
            elif not post.is_video:
                photos.append({
                    "url": post.url,
                    "caption": caption,
                    "width": getattr(post, 'dimensions', [1080, 1080])[0],
                    "height": getattr(post, 'dimensions', [1080, 1080])[1],
                    "ext": "jpg"
                })
            if photos:
                return jsonify({"status": "ok", "caption": caption, "photos": photos, "method": "instaloader"})
        except Exception as e:
            print(f"[METHOD 1 FAILED] Instaloader: {str(e)}")

        # --- METHOD 2: Scraping ---
        for ua_index, user_agent in enumerate(user_agents):
            try:
                session = requests.Session()
                headers = {
                    'User-Agent': user_agent,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive'
                }
                session.headers.update(headers)

                to_try_urls = [
                    url,
                    url.replace('www.', ''),
                    f"https://www.instagram.com/p/{shortcode}/?hl=en",
                    f"https://www.instagram.com/p/{shortcode}/?__a=1&__d=dis"
                ]

                for test_url in to_try_urls:
                    response = session.get(test_url, timeout=10, allow_redirects=True)
                    if response.status_code == 200:
                        content = response.text
                        image_patterns = [
                            r'"display_url":"([^"]+)"',
                            r'<meta property="og:image" content="([^"]+)"',
                            r'"src":"([^"]*cdninstagram[^"]+)"'
                        ]
                        photos = []
                        found_urls = set()
                        for pattern in image_patterns:
                            matches = re.findall(pattern, content)
                            for match in matches:
                                url_img = match.encode('utf-8').decode('unicode_escape').replace('\\u0026', '&').replace('\\/', '/')
                                if url_img not in found_urls and url_img.startswith('http'):
                                    found_urls.add(url_img)
                                    photos.append({
                                        "url": url_img,
                                        "caption": "",
                                        "width": 1080,
                                        "height": 1080,
                                        "ext": url_img.split('.')[-1].split('?')[0] if '.' in url_img else 'jpg'
                                    })
                        if photos:
                            return jsonify({"status": "ok", "caption": "", "photos": photos, "method": f"scraping_ua_{ua_index+1}"})
            except Exception as e:
                continue

        # --- METHOD 3: yt-dlp fallback ---
        try:
            ydl_opts = {
                'quiet': True,
                'skip_download': True,
                'forcejson': True,
                'noplaylist': True,
                'ignoreerrors': True,
                'user_agent': random.choice(user_agents)
            }
            cookie_file = 'cookies_insta.txt'
            if os.path.exists(cookie_file):
                ydl_opts['cookiefile'] = cookie_file
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                photos = []
                if info:
                    if "entries" in info and isinstance(info["entries"], list):
                        for entry in info["entries"]:
                            if entry.get("url") and any(ext in entry.get("url", "") for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                                photos.append({
                                    "url": entry.get("url"),
                                    "caption": entry.get("description", ""),
                                    "width": entry.get("width", 1080),
                                    "height": entry.get("height", 1080),
                                    "ext": entry.get("ext", "jpg")
                                })
                    elif info.get("url") and any(ext in info.get("url", "") for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                        photos.append({
                            "url": info.get("url"),
                            "caption": info.get("description", ""),
                            "width": info.get("width", 1080),
                            "height": info.get("height", 1080),
                            "ext": info.get("ext", "jpg")
                        })
                if photos:
                    return jsonify({"status": "ok", "caption": photos[0].get('caption', ''), "photos": photos, "method": "yt-dlp"})
        except Exception as e:
            print(f"[METHOD 3 FAILED] yt-dlp: {str(e)}")

        # Total fail
        return jsonify({
            "status": "fail",
            "error": "Instagram has blocked all extraction methods for this post. This might be a private post, story, or Instagram updated their anti-scraping measures."
        })
    except Exception as e:
        print(f"[MASTER ERROR]: {str(e)}")
        return jsonify({"status": "fail", "error": f"Unexpected system error: {str(e)}"}), 500

@app.route('/merge', methods=['POST'])
def merge_video_audio():
    try:
        video_url = request.json.get('video_url')
        audio_url = request.json.get('audio_url')

        for link in (video_url, audio_url):
            if not (link and link.startswith('http')):
                return jsonify({'error': 'Invalid URL'}), 400

        with tempfile.TemporaryDirectory() as td:
            video_path = os.path.join(td, 'video.mp4')
            audio_path = os.path.join(td, 'audio.m4a')
            output_path = os.path.join(td, 'merged.mp4')

            r = requests.get(video_url, stream=True)
            with open(video_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            r = requests.get(audio_url, stream=True)
            with open(audio_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', audio_path,
                '-c', 'copy',
                '-movflags', 'faststart',
                output_path
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode != 0:
                return jsonify({'error': 'ffmpeg failed to merge'}), 500

            return send_file(output_path, as_attachment=True, download_name='merged.mp4')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/update_cookies/<platform>', methods=['POST'])
def update_cookies(platform):
    if platform not in ['youtube', 'insta', 'facebook', 'pinterest']:
        return jsonify({'error': 'Invalid platform'}), 400
    path = f'{platform}_cookies.txt'
    content = request.data.decode('utf-8')
    if not content.strip():
        return jsonify({'error': 'No cookie content provided'}), 400
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({'status': f'{platform} cookies updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=True)
