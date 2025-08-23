from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)

@app.route('/get_info', methods=['POST'])
def get_info():
    # Get video or reel URL from frontend body
    data = request.get_json()
    video_url = data.get('url')
    if not video_url:
        return jsonify({'error': 'No URL provided.'}), 400

    # yt-dlp options including cookies
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'cookiefile': 'cookies.txt',  # Make sure cookies.txt is in repo
        'noplaylist': True,           # Avoid playlist fetch issues
        'ignoreerrors': True,         # Avoid crash on single video error
        # Optional: 'user_agent': 'Mozilla/5.0 ...' # for bot bypass (try if errors)
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            if not info:
                return jsonify({'error': 'Failed to fetch video info.'}), 400

            # If info is a playlist, get first entry
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
        print(f"Error: {e}")  # Debug: dekhna ho to logs me mil jayega
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)
