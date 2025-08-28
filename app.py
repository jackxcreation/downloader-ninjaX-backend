import os
import tempfile
import subprocess
import requests
from flask import Flask, request, jsonify, send_file, abort, Response
from flask_cors import CORS
import yt_dlp
import threading
import time

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

# SIMPLE YT-DLP CONFIG (Just like working sites)
def get_ydl_opts():
    return {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'writethumbnail': False,
        'writeinfojson': False,
        'ignoreerrors': False,
        'format': 'best',
    }

@app.route('/get_info', methods=['POST'])
def get_info():
    video_url = request.json.get('url')
    if not video_url:
        return jsonify({'error': 'No URL provided.'}), 400

    # URL normalization (exactly like yt1d.com)
    if "youtube.com/shorts/" in video_url:
        import re
        match = re.search(r'youtube.com/shorts/([a-zA-Z0-9_-]+)', video_url)
        if match:
            video_id = match.group(1)
            video_url = f"https://www.youtube.com/watch?v={video_id}"
    elif "youtu.be/" in video_url:
        import re
        match = re.search(r'youtu.be/([a-zA-Z0-9_-]+)', video_url)
        if match:
            video_id = match.group(1)
            video_url = f"https://www.youtube.com/watch?v={video_id}"

    print(f"Processing: {video_url}")

    try:
        with yt_dlp.YoutubeDL(get_ydl_opts()) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            if 'entries' in info:
                info = info['entries'][0]

            formats = info.get('formats', [])
            
            # Separate audio and video (like ssyoutube.com)
            audio_formats = []
            video_formats = []
            
            for f in formats:
                if not f.get('url'):
                    continue
                    
                format_info = {
                    'format_id': f.get('format_id', ''),
                    'ext': f.get('ext', ''),
                    'filesize': sizeof_fmt(f.get('filesize') or f.get('filesize_approx') or 0),
                    'filesize_bytes': f.get('filesize') or f.get('filesize_approx'),
                    'url': f.get('url', ''),
                    'resolution': f.get('resolution', ''),
                    'format_note': f.get('format_note', ''),
                    'abr': f.get('abr'),
                    'vcodec': f.get('vcodec'),
                    'acodec': f.get('acodec')
                }
                
                if f.get('vcodec') == 'none':  # Audio only
                    audio_formats.append(format_info)
                elif f.get('acodec') == 'none':  # Video only
                    video_formats.append(format_info)
                elif f.get('vcodec') != 'none' and f.get('acodec') != 'none':  # Mixed
                    video_formats.append(format_info)

            # Sort by quality
            video_formats.sort(key=lambda x: int(x.get('format_id', '0')), reverse=True)
            audio_formats.sort(key=lambda x: x.get('abr', 0) or 0, reverse=True)

            return jsonify({
                'title': info.get('title', ''),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'audio_formats': audio_formats,
                'video_formats': video_formats
            })

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 400

# DIRECT YOUTUBE DOWNLOAD (Like working sites)
@app.route('/youtube_download', methods=['POST'])
def youtube_download():
    try:
        data = request.json
        video_url = data.get('url')
        format_id = data.get('format_id', 'best')
        audio_only = data.get('audio_only', False)
        
        if not video_url:
            return jsonify({'error': 'No URL provided'}), 400

        print(f"Direct YouTube download: {video_url}")
        print(f"Format: {format_id}, Audio only: {audio_only}")

        # Configure yt-dlp for download
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': format_id if format_id != 'best' else 'best',
            'outtmpl': tempfile.gettempdir() + '/%(title)s.%(ext)s',
        }
        
        if audio_only:
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Get info first
            info = ydl.extract_info(video_url, download=False)
            if 'entries' in info:
                info = info['entries'][0]
            
            title = info.get('title', 'video')
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()[:50]
            
            # Download
            ydl.download([video_url])
            
            # Find downloaded file
            import glob
            pattern = os.path.join(tempfile.gettempdir(), f"*{safe_title[:20]}*")
            files = glob.glob(pattern)
            
            if not files:
                # Fallback: find any recent file
                import os
                import time
                temp_dir = tempfile.gettempdir()
                files = [f for f in os.listdir(temp_dir) if f.endswith(('.mp4', '.webm', '.mp3', '.m4a'))]
                if files:
                    files = [os.path.join(temp_dir, f) for f in files]
                    files.sort(key=os.path.getctime, reverse=True)
            
            if files:
                file_path = files[0]
                if os.path.exists(file_path):
                    ext = 'mp3' if audio_only else 'mp4'
                    filename = f"{safe_title}.{ext}"
                    
                    def cleanup():
                        time.sleep(10)  # Wait before cleanup
                        try:
                            os.remove(file_path)
                        except:
                            pass
                    
                    threading.Thread(target=cleanup).start()
                    
                    return send_file(file_path, as_attachment=True, download_name=filename)
            
            return jsonify({'error': 'File not found after download'}), 500

    except Exception as e:
        print(f"YouTube download error: {str(e)}")
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

# SIMPLE STREAM (For preview)
@app.route('/stream', methods=['GET'])
def stream_video():
    video_url = request.args.get('url')
    if not video_url:
        return abort(400)
    
    try:
        # Get stream URL using yt-dlp
        ydl_opts = {'quiet': True, 'format': 'best[height<=720]'}
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            if 'entries' in info:
                info = info['entries'][0]
            
            stream_url = info.get('url')
            if not stream_url:
                return abort(404)
            
            # Proxy the stream
            resp = requests.get(stream_url, stream=True, timeout=10)
            if resp.status_code == 200:
                def generate():
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            yield chunk
                
                return Response(
                    generate(),
                    mimetype='video/mp4',
                    headers={'Cache-Control': 'no-cache'}
                )
            
            return abort(resp.status_code)
            
    except Exception as e:
        print(f"Stream error: {e}")
        return abort(500)

# MERGE FUNCTION (Simple)
@app.route('/merge', methods=['POST'])
def merge_video_audio():
    try:
        data = request.json
        video_url = data.get('video_url')
        audio_url = data.get('audio_url')
        
        if not video_url or not audio_url:
            return jsonify({'error': 'Missing URLs'}), 400
        
        print("Starting merge...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            video_path = os.path.join(temp_dir, 'video.mp4')
            audio_path = os.path.join(temp_dir, 'audio.m4a')
            output_path = os.path.join(temp_dir, 'merged.mp4')
            
            # Download video
            with requests.get(video_url, stream=True) as r:
                with open(video_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            # Download audio
            with requests.get(audio_url, stream=True) as r:
                with open(audio_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            # Merge using ffmpeg
            cmd = ['ffmpeg', '-y', '-i', video_path, '-i', audio_path, '-c', 'copy', output_path]
            result = subprocess.run(cmd, capture_output=True)
            
            if result.returncode != 0:
                return jsonify({'error': 'Merge failed'}), 500
            
            return send_file(output_path, as_attachment=True, download_name='merged.mp4')
            
    except Exception as e:
        print(f"Merge error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=True)
