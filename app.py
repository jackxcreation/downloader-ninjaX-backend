import os
import tempfile
import subprocess
import requests
from flask import Flask, request, jsonify, send_file, abort
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)

# Ye function size ko readable format mein convert karta hai
def sizeof_fmt(num, suffix="B"):
    try:
        num = int(num)
    except:
        return "Unknown"
    for unit in ["","K","M","G","T"]:
        if abs(num) < 1024.0:
            return f"{num:.2f} {unit}{suffix}"
        num /= 1024.0
    return f"{num:.2f} P{suffix}"

# Ye endpoint main info fetch karta hai tumhare video link ka
@app.route('/get_info', methods=['POST'])
def get_info():
    video_url = request.json.get('url')
    if not video_url:
        return jsonify({'error': 'No URL provided.'}), 400

    # Platform detect kar le
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
                'width': None,
                'height': None,
                'aspect_ratio': None
            }

            # Width aur height dhundho
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

            # Formats ko audio aur video buckets mein split kar lo
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
                        'resolution': str(f.get('height') or f.get('format_note') or 'audio'),
                        'acodec': f.get('acodec'),
                        'vcodec': f.get('vcodec'),
                        'abr': f.get('abr'),
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
                # Non-yt platforms ke liye
                best_muxed = None
                best_video = None
                best_audio = None

                for f in formats:
                    if not f.get('url'):
                        continue
                    if f.get('vcodec', 'none') != 'none' and f.get('acodec', 'none') != 'none':
                        if not best_muxed or (f.get('height', 0) or 0) > (best_muxed.get('height', 0) or 0):
                            best_muxed = f
                    if f.get('vcodec', 'none') != 'none':
                        if not best_video or (f.get('height', 0) or 0) > (best_video.get('height', 0) or 0):
                            best_video = f
                    if f.get('acodec', 'none') != 'none' and f.get('vcodec', 'none') == 'none':
                        if not best_audio or (f.get('abr', 0) or 0) > (best_audio.get('abr', 0) or 0):
                            best_audio = f

                if best_muxed:
                    size_val = best_muxed.get('filesize') or best_muxed.get('filesize_approx')
                    resp['video_muxed'] = {
                        'resolution': str(best_muxed.get('height', 'HD')) + "p",
                        'extension': best_muxed.get('ext', ''),
                        'filesize': sizeof_fmt(size_val) if size_val else "Unknown",
                        'url': best_muxed.get('url'),
                        'tbr': best_muxed.get('tbr'),
                        'fps': best_muxed.get('fps'),
                    }
                if best_video and (not best_muxed or best_video.get('url') != best_muxed.get('url')):
                    size_val = best_video.get('filesize') or best_video.get('filesize_approx')
                    resp['video_only'] = {
                        'resolution': str(best_video.get('height', 'HD')) + "p",
                        'extension': best_video.get('ext', ''),
                        'filesize': sizeof_fmt(size_val) if size_val else "Unknown",
                        'url': best_video.get('url'),
                        'tbr': best_video.get('tbr'),
                        'fps': best_video.get('fps'),
                    }
                if best_audio:
                    size_val = best_audio.get('filesize') or best_audio.get('filesize_approx')
                    resp['audio'] = {
                        'extension': best_audio.get('ext', ''),
                        'filesize': sizeof_fmt(size_val) if size_val else "Unknown",
                        'url': best_audio.get('url'),
                        'abr': best_audio.get('abr'),
                    }
            return jsonify(resp)

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 400


# Cookie upload routes (Jaise tha waise hi baaki)
# Aapke cookies management ke liye wahi handle kar lenge

@app.route('/update_cookies/youtube', methods=['POST'])
def update_cookies_youtube():
    cookies = request.data.decode('utf-8')
    if not cookies.strip():
        return jsonify({"error": "No cookie content provided"}), 400
    try:
        with open("cookies_youtube.txt", "w", encoding='utf-8') as f:
            f.write(cookies)
        return jsonify({"status": "YouTube cookies updated successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/update_cookies/instagram', methods=['POST'])
def update_cookies_instagram():
    cookies = request.data.decode('utf-8')
    if not cookies.strip():
        return jsonify({"error": "No cookie content provided"}), 400
    try:
        with open("cookies_insta.txt", "w", encoding='utf-8') as f:
            f.write(cookies)
        return jsonify({"status": "Instagram cookies updated successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/update_cookies/facebook', methods=['POST'])
def update_cookies_facebook():
    cookies = request.data.decode('utf-8')
    if not cookies.strip():
        return jsonify({"error": "No cookie content provided"}), 400
    try:
        with open("cookies_facebook.txt", "w", encoding='utf-8') as f:
            f.write(cookies)
        return jsonify({"status": "Facebook cookies updated successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/update_cookies/pinterest', methods=['POST'])
def update_cookies_pinterest():
    cookies = request.data.decode('utf-8')
    if not cookies.strip():
        return jsonify({"error": "No cookie content provided"}), 400
    try:
        with open("cookies_pinterest.txt", "w", encoding='utf-8') as f:
            f.write(cookies)
        return jsonify({"status": "Pinterest cookies updated successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
