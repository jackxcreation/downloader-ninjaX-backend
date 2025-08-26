import os
import tempfile
import subprocess
import requests
from flask import Flask, request, jsonify, send_file, abort, Response
from flask_cors import CORS
import yt_dlp
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

@app.route('/get_info', methods=['POST'])
def get_info():
    video_url = request.json.get('url')
    if not video_url:
        return jsonify({'error': 'No URL provided.'}), 400

    # --- YT Shorts and youtu.be fix: Put BEFORE yt-dlp extract_info! ---
    if "youtube.com/shorts/" in video_url:
        import re
        match = re.search(r'youtube\.com/shorts/([a-zA-Z0-9_-]+)', video_url)
        if match:
            video_id = match.group(1)
            video_url = f"https://www.youtube.com/watch?v={video_id}"
    elif "youtu.be/" in video_url:
        import re
        match = re.search(r'youtu\.be/([a-zA-Z0-9_-]+)', video_url)
        if match:
            video_id = match.group(1)
            video_url = f"https://www.youtube.com/watch?v={video_id}"

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
    if cookie_file and os.path.exists(cookie_file):
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

# DIRECT DOWNLOAD ROUTE (Backend handles full download) - FIXED VERSION
@app.route('/download_file', methods=['POST'])
def download_file():
    try:
        data = request.json
        file_url = data.get('url')
        file_type = data.get('type', 'video')
        filename = data.get('filename', 'download.mp4')
        
        print(f"Download request - URL: {file_url[:100]}...")
        print(f"Filename: {filename}")
        
        if not file_url:
            return jsonify({'error': 'No URL provided'}), 400
            
        # Enhanced headers with more realistic browser signature
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'identity',
            'Connection': 'keep-alive',
            'Referer': 'https://www.youtube.com/'
        }
        
        # Add timeout and better error handling
        print("Starting file download from source...")
        response = requests.get(file_url, headers=headers, stream=True, timeout=30)
        print(f"Response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Failed to fetch file. Status: {response.status_code}")
            return jsonify({'error': f'Failed to fetch file. Status: {response.status_code}'}), 400
            
        # Get content length for progress tracking
        total_size = response.headers.get('content-length')
        if total_size:
            print(f"File size: {sizeof_fmt(int(total_size))}")
        
        # Create temporary file with proper extension
        file_ext = filename.split('.')[-1] if '.' in filename else 'mp4'
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_ext}')
        tmp_file_path = tmp_file.name
        
        print("Writing file to temporary location...")
        try:
            downloaded_size = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    tmp_file.write(chunk)
                    downloaded_size += len(chunk)
            tmp_file.close()
            
            print(f"Download completed. Size: {sizeof_fmt(downloaded_size)}")
            
            # Send file and cleanup after sending
            def cleanup_file():
                try:
                    if os.path.exists(tmp_file_path):
                        os.unlink(tmp_file_path)
                        print("Temporary file cleaned up")
                except Exception as e:
                    print(f"Cleanup error: {e}")
            
            # Schedule cleanup after response is sent
            response_obj = send_file(
                tmp_file_path, 
                as_attachment=True, 
                download_name=filename,
                mimetype='application/octet-stream'
            )
            
            # Cleanup will happen after the response is sent
            import atexit
            atexit.register(cleanup_file)
            
            return response_obj
            
        except Exception as e:
            # Cleanup on error
            tmp_file.close()
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
            raise e
        
    except requests.exceptions.Timeout:
        print("Request timeout")
        return jsonify({'error': 'Request timeout - file too large or slow connection'}), 408
    except requests.exceptions.ConnectionError:
        print("Connection error")
        return jsonify({'error': 'Connection error - unable to reach file source'}), 503
    except Exception as e:
        print(f"Download error: {str(e)}")
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

# STREAMING PREVIEW ROUTE - ENHANCED VERSION
@app.route('/stream_media')
def stream_media():
    try:
        file_url = request.args.get('url')
        if not file_url:
            return abort(400)
        
        print(f"Streaming request for: {file_url[:100]}...")
            
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Referer': 'https://www.youtube.com/'
        }
        
        response = requests.get(file_url, headers=headers, stream=True, timeout=10)
        print(f"Stream response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Stream failed with status: {response.status_code}")
            return abort(response.status_code)
            
        def generate():
            try:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
            except Exception as e:
                print(f"Streaming error: {e}")
                return
                
        content_type = response.headers.get('Content-Type', 'video/mp4')
        print(f"Streaming content type: {content_type}")
        
        return Response(
            generate(), 
            content_type=content_type,
            headers={
                'Accept-Ranges': 'bytes',
                'Cache-Control': 'no-cache'
            }
        )
                       
    except Exception as e:
        print(f"Stream media error: {e}")
        return abort(500)

@app.route('/proxy_download')
def proxy_download():
    file_url = request.args.get('url')
    if not file_url or not file_url.startswith('http'):
        return abort(400)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        r = requests.get(file_url, stream=True, headers=headers, timeout=30)
        if r.status_code != 200:
            return abort(r.status_code)
        
        def generate():
            for chunk in r.iter_content(chunk_size=8192):
                yield chunk
                
        return Response(generate(), content_type=r.headers.get('Content-Type', 'application/octet-stream'))
    except Exception as e:
        print(f"Proxy download error: {e}")
        return abort(500)

@app.route('/proxy_media')
def proxy_media():
    file_url = request.args.get('url')
    if not file_url or not file_url.startswith('http'):
        return abort(400)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        r = requests.get(file_url, stream=True, headers=headers, timeout=15)
        if r.status_code != 200:
            return abort(r.status_code)
        
        def generate():
            for chunk in r.iter_content(chunk_size=8192):
                yield chunk
                
        content_type = r.headers.get('Content-Type', 'application/octet-stream')
        return Response(generate(), content_type=content_type)
    except Exception as e:
        print(f"Proxy media error: {e}")
        return abort(500)

@app.route('/merge', methods=['POST'])
def merge_video_audio():
    try:
        video_url = request.json.get('video_url')
        audio_url = request.json.get('audio_url')

        print(f"Merge request - Video: {video_url[:100] if video_url else 'None'}...")
        print(f"Merge request - Audio: {audio_url[:100] if audio_url else 'None'}...")

        for link in (video_url, audio_url):
            if not (link and link.startswith('http')):
                return jsonify({'error': 'Invalid URL'}), 400

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        with tempfile.TemporaryDirectory() as td:
            video_path = os.path.join(td, 'video.mp4')
            audio_path = os.path.join(td, 'audio.m4a')
            output_path = os.path.join(td, 'merged.mp4')

            print("Downloading video stream...")
            r = requests.get(video_url, stream=True, headers=headers, timeout=30)
            if r.status_code != 200:
                return jsonify({'error': f'Failed to download video: {r.status_code}'}), 400
                
            with open(video_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            print("Downloading audio stream...")
            r = requests.get(audio_url, stream=True, headers=headers, timeout=30)
            if r.status_code != 200:
                return jsonify({'error': f'Failed to download audio: {r.status_code}'}), 400
                
            with open(audio_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            print("Starting FFmpeg merge...")
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
                print(f"FFmpeg error: {result.stderr.decode()}")
                return jsonify({'error': 'ffmpeg failed to merge'}), 500

            print("Merge completed successfully")
            return send_file(output_path, as_attachment=True, download_name='merged.mp4')
            
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Merge timeout - files too large'}), 408
    except Exception as e:
        print(f"Merge error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/update_cookies/<platform>', methods=['POST'])
def update_cookies(platform):
    if platform not in ['youtube', 'insta', 'facebook', 'pinterest']:
        return jsonify({'error': 'Invalid platform'}), 400
    path = f'cookies_{platform}.txt'
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
