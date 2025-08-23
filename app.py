from flask import Flask, request, jsonify
import yt_dlp

app = Flask(__name__)

@app.route('/get_info', methods=['POST'])
def get_info():
    video_url = request.json.get('url')
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'skip_download': True}) as ydl:
            info = ydl.extract_info(video_url, download=False)
        formats = [
            {
                'format_id': f['format_id'],
                'resolution': f.get('height') or f.get('format_note') or 'audio',
                'extension': f['ext'],
                'filesize': f.get('filesize') or 0,
                'format_note': f.get('format_note') or '',
                'url': f.get('url')
            }
            for f in info['formats'] if f.get('url')
        ]
        return jsonify({
            'title': info.get('title', ''),
            'thumbnail': info.get('thumbnail', ''),
            'formats': formats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)
