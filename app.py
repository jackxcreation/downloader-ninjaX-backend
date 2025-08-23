from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)

@app.route('/get_info', methods=['POST'])
def get_info():
    video_url = request.json.get('url')
    if not video_url:
        return jsonify({'error': 'No URL provided.'}), 400

    # Decide cookies file based on URL
    if "youtube.com" in video_url or "youtu.be" in video_url:
        cookie_file = 'cookies_youtube.txt'
    elif "instagram.com" in video_url:
        cookie_file = 'cookies_insta.txt'
    else:
        cookie_file = None  # Or handle other domains

    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'noplaylist': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/115.0.0.0 Safari/537.36'
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

            formats = []
            for f in info.get('formats', []):
                if f.get('url'):
                    formats.append({
                        'format_id': f.get('format_id'),
                        'resolution': f.get('height') or f.get('format_note') or 'audio',
                        'extension': f.get('ext'),
                        'filesize': f.get('filesize') or 0,
                        'format_note': f.get('format_note') or '',
                        'url': f.get('url')
                    })

            return jsonify({
                'title': info.get('title', ''),
                'thumbnail': info.get('thumbnail', ''),
                'formats': formats
            })
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 400

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

if __name__ == '__main__':
    app.run(debug=True)
