from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)

# Endpoint for video info
@app.route('/get_info', methods=['POST'])
def get_info():
    video_url = request.json.get('url')
    if not video_url:
        return jsonify({'error': 'No URL provided.'}), 400

    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'cookiefile': 'cookies.txt',
        'noplaylist': True,
    }
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

# New endpoint to update cookies.txt via POST request
@app.route('/update_cookies', methods=['POST'])
def update_cookies():
    # Expect raw text data (cookies content) in body
    cookies_content = request.get_data(as_text=True)
    if not cookies_content or not cookies_content.strip():
        return jsonify({'error': 'No cookie content provided'}), 400

    try:
        with open('cookies.txt', 'w', encoding='utf-8') as f:
            f.write(cookies_content)
        return jsonify({'status': 'Cookies updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
