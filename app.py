from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)

def sizeof_fmt(num, suffix="B"):
    # Smart file size formatting (B, KB, MB, GB...)
    try:
        num = int(num)
    except:
        return "Unknown"
    for unit in ["","K","M","G","T"]:
        if abs(num) < 1024.0:
            return "%3.2f %s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.2f%s%s" % (num, 'P', suffix)

@app.route('/get_info', methods=['POST'])
def get_info():
    video_url = request.json.get('url')
    if not video_url:
        return jsonify({'error': 'No URL provided.'}), 400

    # Detect platform and cookies
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

            # Meta for UI
            resp = {
                'title': info.get('title', ''),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration'), # in seconds
                'formats_raw': [], # for debug
            }

            # Platform: YouTube → all audio/video formats, rest: only best video/audio
            formats = info.get('formats', [])
            resp['formats_raw'] = formats # Optional: remove later
            if platform == 'youtube':
                audio_formats, video_formats = [], []
                for f in formats:
                    if not f.get('url'): continue
                    size_val = f.get('filesize') or f.get('filesize_approx') or None
                    readable_size = sizeof_fmt(size_val) if size_val else "Unknown"
                    out = {
                        'format_id': f.get('format_id',''),
                        'format_note': f.get('format_note') or '',
                        'extension': f.get('ext',''),
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
                    # Split audio only vs video
                    if f.get('vcodec','none') == 'none':
                        audio_formats.append(out)
                    else:
                        video_formats.append(out)
                # Sort videos high→low by resolution
                video_formats = sorted(video_formats, key=lambda x: int(x['resolution']) if x['resolution'].isdigit() else 0, reverse=True)
                # Sort audio by bitrate (best first)
                audio_formats = sorted(audio_formats, key=lambda x: float(x['abr']) if x['abr'] else 0, reverse=True)
                resp['audio_formats'] = audio_formats
                resp['video_formats'] = video_formats

            else:
                # Find best audio, best video only
                best_video = None
                best_audio = None
                vstreams = [f for f in formats if f.get('vcodec','none') != 'none' and f.get('url')]
                astreams = [f for f in formats if f.get('acodec','none') != 'none' and f.get('url')]
                if vstreams:
                    # Pick highest resolution, then highest bitrate
                    best_video = max(vstreams, key=lambda f: (f.get('height',0) or 0, f.get('tbr',0) or 0))
                if astreams:
                    best_audio = max(astreams, key=lambda f: (f.get('abr',0) or 0))
                # Add to resp
                if best_video:
                    size_val = best_video.get('filesize') or best_video.get('filesize_approx') or None
                    resp['video'] = {
                        'resolution': str(best_video.get('height', 'HD'))+"p",
                        'format_note': best_video.get('format_note') or '',
                        'extension': best_video.get('ext',''),
                        'filesize': sizeof_fmt(size_val) if size_val else "Unknown",
                        'filesize_bytes': size_val,
                        'url': best_video.get('url'),
                        'tbr': best_video.get('tbr'),
                        'fps': best_video.get('fps'),
                    }
                if best_audio:
                    size_val = best_audio.get('filesize') or best_audio.get('filesize_approx') or None
                    resp['audio'] = {
                        'format_note': best_audio.get('format_note') or '',
                        'extension': best_audio.get('ext',''),
                        'filesize': sizeof_fmt(size_val) if size_val else "Unknown",
                        'filesize_bytes': size_val,
                        'url': best_audio.get('url'),
                        'abr': best_audio.get('abr')
                    }

            return jsonify(resp)
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 400

# =============== Cookies Endpoints ===============
@app.route('/update_cookies/youtube', methods=['POST'])
def update_cookies_youtube():
    cookies_content = request.get_data(as_text=True)
    if not cookies_content.strip():
        return jsonify({'error': 'No cookie content provided'}), 400
    try:
        with open('cookies_youtube.txt', 'w', encoding='utf-8') as f:
            f.write(cookies_content)
        return jsonify({'status': 'YouTube cookies updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/update_cookies/instagram', methods=['POST'])
def update_cookies_instagram():
    cookies_content = request.get_data(as_text=True)
    if not cookies_content.strip():
        return jsonify({'error': 'No cookie content provided'}), 400
    try:
        with open('cookies_insta.txt', 'w', encoding='utf-8') as f:
            f.write(cookies_content)
        return jsonify({'status': 'Instagram cookies updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/update_cookies/facebook', methods=['POST'])
def update_cookies_facebook():
    cookies_content = request.get_data(as_text=True)
    if not cookies_content.strip():
        return jsonify({'error': 'No cookie content provided'}), 400
    try:
        with open('cookies_facebook.txt', 'w', encoding='utf-8') as f:
            f.write(cookies_content)
        return jsonify({'status': 'Facebook cookies updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/update_cookies/pinterest', methods=['POST'])
def update_cookies_pinterest():
    cookies_content = request.get_data(as_text=True)
    if not cookies_content.strip():
        return jsonify({'error': 'No cookie content provided'}), 400
    try:
        with open('cookies_pinterest.txt', 'w', encoding='utf-8') as f:
            f.write(cookies_content)
        return jsonify({'status': 'Pinterest cookies updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
