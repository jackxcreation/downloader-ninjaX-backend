import os
import tempfile
import subprocess
import requests
from flask import Flask, request, jsonify, send_file, abort
from flask_cors import CORS
import yt_dlp

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

# ---- Instagram multi-image endpoint (with cookies) ----

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
    app.run(host='0.0.0.0', port=10000, debug=True)
