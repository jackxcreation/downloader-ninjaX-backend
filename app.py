import os
import tempfile
import subprocess
import requests
from flask import Flask, request, jsonify, send_file, abort, Response
from flask_cors import CORS
import yt_dlp
import time
import random
import json
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)

# ADVANCED USER AGENTS ROTATION (YouTube can't detect pattern)
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]

def get_random_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0'
    }

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

# ADVANCED YT-DLP CONFIGURATION (BLOCK-PROOF)
def get_advanced_ydl_opts(platform='youtube'):
    """Advanced yt-dlp options to bypass YouTube blocks"""
    
    base_opts = {
        'quiet': True,
        'skip_download': True,
        'noplaylist': True,
        'extract_flat': False,
        'geo_bypass': True,
        'geo_bypass_country': 'US',
        'user_agent': random.choice(USER_AGENTS),
        'prefer_insecure': False,
        'no_warnings': False,
        'ignoreerrors': True,
        'retries': 3,
        'fragment_retries': 5,
        'extractor_retries': 3,
        'sleep_interval': 0,
        'max_sleep_interval': 1,
        'sleep_interval_subtitles': 0,
        'http_chunk_size': 10485760  # 10MB chunks
    }
    
    if platform == 'youtube':
        # YouTube specific advanced options
        youtube_opts = {
            'format': 'best[height<=?1080]/best',
            'writeinfojson': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'youtube_include_dash_manifest': True,
            'mark_watched': False,
            'extract_comments': False,
            'age_limit': 99,
            'playlist_items': '1'
        }
        base_opts.update(youtube_opts)
        
        # Cookie file if exists
        cookie_file = 'cookies_youtube.txt'
        if os.path.exists(cookie_file):
            base_opts['cookiefile'] = cookie_file
            
    elif platform in ['insta', 'facebook', 'pinterest']:
        cookie_file = f'cookies_{platform}.txt'
        if os.path.exists(cookie_file):
            base_opts['cookiefile'] = cookie_file
    
    return base_opts

@app.route('/get_info', methods=['POST'])
def get_info():
    video_url = request.json.get('url')
    if not video_url:
        return jsonify({'error': 'No URL provided.'}), 400

    # URL preprocessing and platform detection
    original_url = video_url
    
    # Convert shorts/youtu.be to standard format
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
    
    # Platform detection
    if "youtube.com" in video_url or "youtu.be" in video_url:
        platform = 'youtube'
    elif "instagram.com" in video_url:
        platform = 'insta'
    elif "facebook.com" in video_url or "fb.watch" in video_url:
        platform = 'facebook'
    elif "pinterest.com" in video_url:
        platform = 'pinterest'
    else:
        platform = 'other'

    print(f"Processing {platform} URL: {video_url}")

    # Get advanced options for platform
    ydl_opts = get_advanced_ydl_opts(platform)
    
    # Multiple extraction attempts with different strategies
    extraction_strategies = [
        ydl_opts,  # Primary strategy
        {**ydl_opts, 'user_agent': random.choice(USER_AGENTS)},  # Different UA
        {**ydl_opts, 'geo_bypass_country': 'GB'},  # Different country
        {**ydl_opts, 'prefer_insecure': True, 'http_chunk_size': 1048576}  # Fallback
    ]
    
    for attempt, opts in enumerate(extraction_strategies):
        try:
            print(f"Extraction attempt {attempt + 1} for {platform}")
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                # Add small delay to avoid rate limiting
                if attempt > 0:
                    time.sleep(random.uniform(0.5, 2.0))
                
                info = ydl.extract_info(video_url, download=False)
                
                if not info:
                    print(f"No info extracted on attempt {attempt + 1}")
                    continue
                    
                if 'entries' in info and isinstance(info['entries'], list):
                    info = info['entries'][0] if info['entries'] else {}
                
                if not info:
                    print(f"Empty info after entries processing on attempt {attempt + 1}")
                    continue

                print(f"Successfully extracted info on attempt {attempt + 1}")
                
                # Build response
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

                # Get dimensions
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

                # Process formats based on platform
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
                    
                    # Sort formats
                    video_formats = sorted(video_formats, key=lambda x: int(x['resolution']) if x['resolution'].isdigit() else 0, reverse=True)
                    audio_formats = sorted(audio_formats, key=lambda x: float(x['abr']) if x['abr'] else 0, reverse=True)
                    
                    resp['audio_formats'] = audio_formats
                    resp['video_formats'] = video_formats
                
                else:
                    # Non-YouTube platform processing (Instagram, Facebook, Pinterest)
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
            print(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt == len(extraction_strategies) - 1:  # Last attempt
                return jsonify({'error': f'All extraction attempts failed. Last error: {str(e)}'}), 400
            continue
    
    return jsonify({'error': 'Failed to extract video info after all attempts.'}), 400

# ADVANCED DOWNLOAD WITH RETRY & FALLBACK
@app.route('/download_file', methods=['POST'])
def download_file():
    try:
        data = request.json
        file_url = data.get('url')
        file_type = data.get('type', 'video')
        filename = data.get('filename', 'download.mp4')
        
        print(f"Advanced download request - URL: {file_url[:100]}...")
        print(f"Filename: {filename}")
        
        if not file_url:
            return jsonify({'error': 'No URL provided'}), 400
        
        # Multiple download attempts with different strategies
        download_strategies = [
            get_random_headers(),  # Random headers
            {**get_random_headers(), 'Range': 'bytes=0-'},  # Range request
            {**get_random_headers(), 'Connection': 'close'},  # Close connection
        ]
        
        for attempt, headers in enumerate(download_strategies):
            try:
                print(f"Download attempt {attempt + 1}")
                
                # Add delay between attempts
                if attempt > 0:
                    time.sleep(random.uniform(1.0, 3.0))
                
                # Add YouTube-specific headers if it's a YouTube URL
                if 'googlevideo.com' in file_url or 'youtube.com' in file_url:
                    headers.update({
                        'Origin': 'https://www.youtube.com',
                        'Referer': 'https://www.youtube.com/',
                    })
                
                response = requests.get(
                    file_url, 
                    headers=headers, 
                    stream=True, 
                    timeout=45,
                    allow_redirects=True
                )
                
                print(f"Download response status: {response.status_code}")
                
                if response.status_code == 200:
                    # Success! Process the download
                    total_size = response.headers.get('content-length')
                    if total_size:
                        print(f"File size: {sizeof_fmt(int(total_size))}")
                    
                    file_ext = filename.split('.')[-1] if '.' in filename else 'mp4'
                    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_ext}')
                    tmp_file_path = tmp_file.name
                    
                    print("Writing file to temporary location...")
                    downloaded_size = 0
                    
                    for chunk in response.iter_content(chunk_size=16384):  # Larger chunks
                        if chunk:
                            tmp_file.write(chunk)
                            downloaded_size += len(chunk)
                    
                    tmp_file.close()
                    print(f"Download completed successfully. Size: {sizeof_fmt(downloaded_size)}")
                    
                    # Cleanup function
                    def cleanup_file():
                        try:
                            if os.path.exists(tmp_file_path):
                                os.unlink(tmp_file_path)
                                print("Temporary file cleaned up")
                        except Exception as e:
                            print(f"Cleanup error: {e}")
                    
                    response_obj = send_file(
                        tmp_file_path, 
                        as_attachment=True, 
                        download_name=filename,
                        mimetype='application/octet-stream'
                    )
                    
                    import atexit
                    atexit.register(cleanup_file)
                    
                    return response_obj
                
                elif response.status_code == 403:
                    print(f"Attempt {attempt + 1}: Forbidden (403) - trying next strategy")
                    continue
                elif response.status_code == 429:
                    print(f"Attempt {attempt + 1}: Rate limited (429) - waiting longer")
                    time.sleep(random.uniform(5.0, 10.0))
                    continue
                else:
                    print(f"Attempt {attempt + 1}: Status {response.status_code}")
                    continue
                    
            except requests.exceptions.Timeout:
                print(f"Attempt {attempt + 1}: Timeout")
                continue
            except requests.exceptions.ConnectionError:
                print(f"Attempt {attempt + 1}: Connection error")
                continue
            except Exception as e:
                print(f"Attempt {attempt + 1}: Error {str(e)}")
                continue
        
        # All attempts failed
        return jsonify({'error': 'All download attempts failed. File may be geo-restricted or temporarily unavailable.'}), 400
        
    except Exception as e:
        print(f"Download function error: {str(e)}")
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

# ADVANCED STREAMING with Anti-Detection
@app.route('/stream_media')
def stream_media():
    try:
        file_url = request.args.get('url')
        if not file_url:
            return abort(400)
        
        print(f"Advanced streaming request for: {file_url[:100]}...")
        
        # Multiple streaming attempts
        for attempt in range(3):
            try:
                headers = get_random_headers()
                
                # YouTube-specific headers
                if 'googlevideo.com' in file_url or 'youtube.com' in file_url:
                    headers.update({
                        'Origin': 'https://www.youtube.com',
                        'Referer': 'https://www.youtube.com/',
                    })
                
                if attempt > 0:
                    time.sleep(random.uniform(0.5, 2.0))
                
                response = requests.get(
                    file_url, 
                    headers=headers, 
                    stream=True, 
                    timeout=15,
                    allow_redirects=True
                )
                
                print(f"Stream attempt {attempt + 1} status: {response.status_code}")
                
                if response.status_code == 200:
                    def generate():
                        try:
                            for chunk in response.iter_content(chunk_size=16384):
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
                            'Cache-Control': 'no-cache, no-store, must-revalidate',
                            'Pragma': 'no-cache',
                            'Expires': '0'
                        }
                    )
                elif response.status_code in [403, 429]:
                    continue  # Try next attempt
                else:
                    return abort(response.status_code)
                    
            except Exception as e:
                print(f"Stream attempt {attempt + 1} error: {e}")
                continue
        
        return abort(503)  # Service unavailable after all attempts
                       
    except Exception as e:
        print(f"Stream media error: {e}")
        return abort(500)

# Keep existing proxy routes for compatibility
@app.route('/proxy_download')
def proxy_download():
    file_url = request.args.get('url')
    if not file_url or not file_url.startswith('http'):
        return abort(400)
    
    headers = get_random_headers()
    
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
    
    headers = get_random_headers()
    
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

# ADVANCED MERGE with Retry Logic
@app.route('/merge', methods=['POST'])
def merge_video_audio():
    try:
        video_url = request.json.get('video_url')
        audio_url = request.json.get('audio_url')

        print(f"Advanced merge request - Video: {video_url[:100] if video_url else 'None'}...")
        print(f"Advanced merge request - Audio: {audio_url[:100] if audio_url else 'None'}...")

        for link in (video_url, audio_url):
            if not (link and link.startswith('http')):
                return jsonify({'error': 'Invalid URL'}), 400

        # Download with retry logic
        def download_with_retry(url, filename, max_attempts=3):
            for attempt in range(max_attempts):
                try:
                    headers = get_random_headers()
                    if 'googlevideo.com' in url:
                        headers.update({
                            'Origin': 'https://www.youtube.com',
                            'Referer': 'https://www.youtube.com/',
                        })
                    
                    if attempt > 0:
                        time.sleep(random.uniform(1.0, 3.0))
                    
                    r = requests.get(url, stream=True, headers=headers, timeout=45)
                    
                    if r.status_code == 200:
                        with open(filename, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=16384):
                                if chunk:
                                    f.write(chunk)
                        return True
                    else:
                        print(f"Download attempt {attempt + 1} failed with status {r.status_code}")
                        
                except Exception as e:
                    print(f"Download attempt {attempt + 1} error: {e}")
                    
            return False

        with tempfile.TemporaryDirectory() as td:
            video_path = os.path.join(td, 'video.mp4')
            audio_path = os.path.join(td, 'audio.m4a')
            output_path = os.path.join(td, 'merged.mp4')

            print("Downloading video stream with retry...")
            if not download_with_retry(video_url, video_path):
                return jsonify({'error': 'Failed to download video after multiple attempts'}), 400

            print("Downloading audio stream with retry...")
            if not download_with_retry(audio_url, audio_path):
                return jsonify({'error': 'Failed to download audio after multiple attempts'}), 400

            print("Starting advanced FFmpeg merge...")
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', audio_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-movflags', 'faststart',
                '-avoid_negative_ts', 'make_zero',
                output_path
            ]
            
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            if result.returncode != 0:
                print(f"FFmpeg error: {result.stderr.decode()}")
                return jsonify({'error': 'ffmpeg failed to merge'}), 500

            print("Advanced merge completed successfully")
            return send_file(output_path, as_attachment=True, download_name='merged_video.mp4')
            
    except Exception as e:
        print(f"Advanced merge error: {str(e)}")
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
        print(f"Updated cookies for {platform}")
        return jsonify({'status': f'{platform} cookies updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("Starting Advanced YouTube-Proof Downloader...")
    print("Features: Anti-detection, Retry logic, Geo-bypass, Header rotation")
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=True)
