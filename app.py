import os
import tempfile
import subprocess
import requests
from flask import Flask, request, jsonify, send_file, abort, Response
from flask_cors import CORS
import yt_dlp
import threading
import time
import random
import glob
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)

# ENHANCED USER AGENTS FOR ALL PLATFORMS
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

# SUPER ENHANCED YT-DLP CONFIG FOR ALL PLATFORMS
def get_enhanced_ydl_opts(platform='youtube'):
    """Enhanced yt-dlp options for all platforms with special YouTube optimizations"""
    
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
        'retries': 5,
        'fragment_retries': 10,
        'extractor_retries': 5,
        'sleep_interval': 0,
        'max_sleep_interval': 2,
        'sleep_interval_subtitles': 0,
        'http_chunk_size': 10485760,  # 10MB chunks
        'socket_timeout': 30,
    }
    
    if platform == 'youtube':
        # SUPER ENHANCED YOUTUBE CONFIG (Like yt1d.com)
        youtube_opts = {
            'format': 'best[height<=?2160]/best',
            'writeinfojson': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'youtube_include_dash_manifest': True,
            'mark_watched': False,
            'extract_comments': False,
            'age_limit': 99,
            'playlist_items': '1',
            'extract_chapters': False,
            'extract_series': False,
            # YouTube anti-throttling
            'extractor_args': {
                'youtube': {
                    'skip': ['dash', 'hls'],
                    'player_client': ['android', 'web'],
                    'player_skip': ['js'],
                }
            }
        }
        base_opts.update(youtube_opts)
        
        cookie_file = 'cookies_youtube.txt'
        if os.path.exists(cookie_file):
            base_opts['cookiefile'] = cookie_file
            print(f"Using YouTube cookies: {cookie_file}")
            
    elif platform == 'insta':
        insta_opts = {
            'http_headers': {
                'User-Agent': 'Instagram 219.0.0.12.117 Android',
            }
        }
        base_opts.update(insta_opts)
        cookie_file = 'cookies_insta.txt'
        if os.path.exists(cookie_file):
            base_opts['cookiefile'] = cookie_file
            print(f"Using Instagram cookies: {cookie_file}")
            
    elif platform == 'facebook':
        fb_opts = {
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X)',
            }
        }
        base_opts.update(fb_opts)
        cookie_file = 'cookies_facebook.txt'
        if os.path.exists(cookie_file):
            base_opts['cookiefile'] = cookie_file
            print(f"Using Facebook cookies: {cookie_file}")
            
    elif platform == 'pinterest':
        pinterest_opts = {
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.pinterest.com/',
            }
        }
        base_opts.update(pinterest_opts)
        cookie_file = 'cookies_pinterest.txt'
        if os.path.exists(cookie_file):
            base_opts['cookiefile'] = cookie_file
            print(f"Using Pinterest cookies: {cookie_file}")
    
    return base_opts

@app.route('/get_info', methods=['POST'])
def get_info():
    video_url = request.json.get('url')
    if not video_url:
        return jsonify({'error': 'No URL provided.'}), 400

    original_url = video_url
    
    # Enhanced URL preprocessing for ALL PLATFORMS
    if "youtube.com/shorts/" in video_url:
        import re
        match = re.search(r'youtube.com/shorts/([a-zA-Z0-9_-]+)', video_url)
        if match:
            video_id = match.group(1)
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            print(f"Converted Shorts URL: {video_url}")
    elif "youtu.be/" in video_url:
        import re
        match = re.search(r'youtu.be/([a-zA-Z0-9_-]+)', video_url)
        if match:
            video_id = match.group(1)
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            print(f"Converted youtu.be URL: {video_url}")

    # Platform detection with enhanced logic
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

    print(f"Processing {platform.upper()} URL: {video_url}")

    # Enhanced extraction with multiple attempts for ALL PLATFORMS
    extraction_strategies = []
    
    if platform == 'youtube':
        # Special YouTube strategies (like yt1d.com)
        strategies = [
            get_enhanced_ydl_opts('youtube'),
            {**get_enhanced_ydl_opts('youtube'), 'user_agent': USER_AGENTS[1]},
            {**get_enhanced_ydl_opts('youtube'), 'geo_bypass_country': 'GB'},
            {**get_enhanced_ydl_opts('youtube'), 'extractor_args': {'youtube': {'player_client': ['android']}}},
            {**get_enhanced_ydl_opts('youtube'), 'format': 'worst'},  # Fallback
        ]
        extraction_strategies.extend(strategies)
    else:
        # Other platforms strategies
        extraction_strategies.extend([
            get_enhanced_ydl_opts(platform),
            {**get_enhanced_ydl_opts(platform), 'user_agent': random.choice(USER_AGENTS)},
            {**get_enhanced_ydl_opts(platform), 'geo_bypass_country': 'GB'},
        ])
    
    for attempt, opts in enumerate(extraction_strategies):
        try:
            print(f"[{platform.upper()}] Extraction attempt {attempt + 1}")
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                if attempt > 0:
                    delay = random.uniform(0.5, 2.0)
                    print(f"Adding delay: {delay:.1f}s")
                    time.sleep(delay)
                
                info = ydl.extract_info(video_url, download=False)
                
                if not info:
                    print(f"No info extracted on attempt {attempt + 1}")
                    continue
                    
                if 'entries' in info and isinstance(info['entries'], list):
                    info = info['entries'][0] if info['entries'] else {}
                
                if not info:
                    print(f"Empty info after processing on attempt {attempt + 1}")
                    continue

                print(f"✅ Successfully extracted info on attempt {attempt + 1}")
                
                # Build enhanced response
                resp = {
                    'title': info.get('title', ''),
                    'thumbnail': info.get('thumbnail', ''),
                    'duration': int(info.get('duration') or 0),
                    'formats': info.get('formats', []),
                    'formats_raw': info.get('formats', []),
                    'width': None,
                    'height': None,
                    'aspect_ratio': None,
                    'uploader': info.get('uploader', ''),
                    'view_count': info.get('view_count', 0),
                    'like_count': info.get('like_count', 0),
                    'upload_date': info.get('upload_date', ''),
                }

                # Enhanced dimension detection
                width = info.get('width')
                height = info.get('height')
                formats = resp['formats']

                if not width or not height:
                    best_format = None
                    for f in formats:
                        if 'width' in f and 'height' in f and f.get('url'):
                            if not best_format or (f.get('width', 0) * f.get('height', 0)) > (best_format.get('width', 0) * best_format.get('height', 0)):
                                best_format = f
                    if best_format:
                        width = best_format['width']
                        height = best_format['height']

                if width and height:
                    resp['width'] = width
                    resp['height'] = height
                    resp['aspect_ratio'] = f"{width}:{height}"

                # Enhanced format processing for ALL PLATFORMS
                if platform == 'youtube':
                    # SUPER ENHANCED YOUTUBE FORMAT PROCESSING
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
                            'quality': f.get('quality'),
                            'protocol': f.get('protocol'),
                        }
                        
                        if f.get('vcodec', 'none') == 'none' and f.get('acodec', 'none') != 'none':
                            audio_formats.append(out)
                        elif f.get('vcodec', 'none') != 'none':
                            video_formats.append(out)
                    
                    # Enhanced sorting
                    video_formats = sorted(video_formats, key=lambda x: (
                        int(x['resolution']) if x['resolution'].isdigit() else 0,
                        x.get('fps', 0) or 0,
                        x.get('tbr', 0) or 0
                    ), reverse=True)
                    
                    audio_formats = sorted(audio_formats, key=lambda x: (
                        float(x['abr']) if x['abr'] else 0,
                        x.get('tbr', 0) or 0
                    ), reverse=True)
                    
                    resp['audio_formats'] = audio_formats
                    resp['video_formats'] = video_formats
                    
                    print(f"YouTube: Found {len(video_formats)} video formats, {len(audio_formats)} audio formats")
                
                else:
                    # ENHANCED NON-YOUTUBE PLATFORM PROCESSING (Facebook, Instagram, Pinterest)
                    best_muxed = None
                    best_video = None
                    best_audio = None

                    for f in formats:
                        if not f.get('url'):
                            continue
                            
                        # Mixed format (video + audio)
                        if f.get('vcodec', 'none') != 'none' and f.get('acodec', 'none') != 'none':
                            if not best_muxed or (f.get('height', 0) * f.get('width', 0)) > (best_muxed.get('height', 0) * best_muxed.get('width', 0)):
                                best_muxed = f
                        
                        # Video only
                        if f.get('vcodec', 'none') != 'none':
                            if not best_video or (f.get('height', 0) * f.get('width', 0)) > (best_video.get('height', 0) * best_video.get('width', 0)):
                                best_video = f
                        
                        # Audio only
                        if f.get('acodec', 'none') != 'none' and f.get('vcodec', 'none') == 'none':
                            if not best_audio or (f.get('abr', 0) or 0) > (best_audio.get('abr', 0) or 0):
                                best_audio = f

                    if best_muxed:
                        size_val = best_muxed.get('filesize') or best_muxed.get('filesize_approx')
                        resp['video_muxed'] = {
                            'resolution': str(best_muxed.get('height', '')) + "p" if best_muxed.get('height') else "HD",
                            'extension': best_muxed.get('ext'),
                            'filesize': sizeof_fmt(size_val) if size_val else "Unknown",
                            'filesize_bytes': size_val,
                            'url': best_muxed.get('url'),
                            'tbr': best_muxed.get('tbr'),
                            'fps': best_muxed.get('fps'),
                            'width': best_muxed.get('width'),
                            'height': best_muxed.get('height'),
                        }

                    if best_video and (not best_muxed or best_video['url'] != best_muxed['url']):
                        size_val = best_video.get('filesize') or best_video.get('filesize_approx')
                        resp['video_only'] = {
                            'resolution': str(best_video.get('height', '')) + "p" if best_video.get('height') else "HD",
                            'extension': best_video.get('ext'),
                            'filesize': sizeof_fmt(size_val) if size_val else "Unknown",
                            'filesize_bytes': size_val,
                            'url': best_video.get('url'),
                            'tbr': best_video.get('tbr'),
                            'fps': best_video.get('fps'),
                            'width': best_video.get('width'),
                            'height': best_video.get('height'),
                        }

                    if best_audio:
                        size_val = best_audio.get('filesize') or best_audio.get('filesize_approx')
                        resp['audio'] = {
                            'extension': best_audio.get('ext'),
                            'filesize': sizeof_fmt(size_val) if size_val else "Unknown",
                            'filesize_bytes': size_val,
                            'url': best_audio.get('url'),
                            'abr': best_audio.get('abr'),
                            'tbr': best_audio.get('tbr'),
                        }
                    
                    print(f"{platform.upper()}: Processed formats successfully")

                return jsonify(resp)
                
        except Exception as e:
            print(f"[{platform.upper()}] Attempt {attempt + 1} failed: {str(e)}")
            if attempt == len(extraction_strategies) - 1:
                return jsonify({'error': f'All extraction attempts failed. Platform: {platform}. Error: {str(e)}'}), 400
            continue
    
    return jsonify({'error': f'Failed to extract {platform} info after all attempts.'}), 400

# SUPER ENHANCED YOUTUBE DIRECT DOWNLOAD (Like yt1d.com)
@app.route('/youtube_download', methods=['POST'])
def youtube_download():
    try:
        data = request.json
        video_url = data.get('url')
        format_id = data.get('format_id', 'best')
        audio_only = data.get('audio_only', False)
        
        if not video_url:
            return jsonify({'error': 'No URL provided'}), 400

        print(f"🚀 SUPER YOUTUBE DOWNLOAD: {video_url}")
        print(f"Format: {format_id}, Audio only: {audio_only}")

        # Enhanced yt-dlp configuration for download
        ydl_opts = {
            'quiet': True,
            'no_warnings': False,
            'format': format_id if format_id != 'best' else 'best',
            'outtmpl': os.path.join(tempfile.gettempdir(), '%(title)s.%(ext)s'),
            'retries': 5,
            'fragment_retries': 10,
            'socket_timeout': 30,
            'user_agent': random.choice(USER_AGENTS),
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

        # Cookie support
        cookie_file = 'cookies_youtube.txt'
        if os.path.exists(cookie_file):
            ydl_opts['cookiefile'] = cookie_file

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Get info first for filename
            info = ydl.extract_info(video_url, download=False)
            if 'entries' in info:
                info = info['entries'][0]
            
            title = info.get('title', 'video')
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()[:50]
            
            print(f"Downloading: {safe_title}")
            
            # Clear temp directory of old files
            temp_dir = tempfile.gettempdir()
            old_files = glob.glob(os.path.join(temp_dir, '*'))
            
            # Download the video
            ydl.download([video_url])
            
            # Find the downloaded file
            new_files = glob.glob(os.path.join(temp_dir, '*'))
            downloaded_files = list(set(new_files) - set(old_files))
            
            # Alternative search methods
            if not downloaded_files:
                patterns = [
                    os.path.join(temp_dir, f"*{safe_title[:20]}*"),
                    os.path.join(temp_dir, f"{safe_title}.*"),
                    os.path.join(temp_dir, "*.mp4"),
                    os.path.join(temp_dir, "*.webm"),
                    os.path.join(temp_dir, "*.mp3"),
                    os.path.join(temp_dir, "*.m4a"),
                ]
                
                for pattern in patterns:
                    files = glob.glob(pattern)
                    if files:
                        # Get the most recent file
                        downloaded_files = [max(files, key=os.path.getctime)]
                        break
            
            if downloaded_files:
                file_path = downloaded_files[0]
                if os.path.exists(file_path):
                    file_ext = os.path.splitext(file_path)[1][1:] or ('mp3' if audio_only else 'mp4')
                    filename = f"{safe_title}.{file_ext}"
                    
                    print(f"✅ Download successful: {filename} ({sizeof_fmt(os.path.getsize(file_path))})")
                    
                    # Cleanup function
                    def cleanup():
                        time.sleep(30)  # Wait longer before cleanup
                        try:
                            if os.path.exists(file_path):
                                os.remove(file_path)
                                print(f"🧹 Cleaned up: {file_path}")
                        except Exception as e:
                            print(f"Cleanup error: {e}")
                    
                    threading.Thread(target=cleanup).start()
                    
                    return send_file(file_path, as_attachment=True, download_name=filename)
            
            return jsonify({'error': 'Downloaded file not found'}), 500

    except Exception as e:
        print(f"❌ YouTube download error: {str(e)}")
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

# ENHANCED DOWNLOAD FOR ALL PLATFORMS
@app.route('/download_file', methods=['POST'])
def download_file():
    try:
        data = request.json
        file_url = data.get('url')
        file_type = data.get('type', 'video')
        filename = data.get('filename', 'download.mp4')
        
        print(f"🔽 Enhanced download request - URL: {file_url[:100]}...")
        print(f"Filename: {filename}")
        
        if not file_url:
            return jsonify({'error': 'No URL provided'}), 400
        
        # Enhanced download strategies for different platforms
        download_strategies = []
        
        if 'googlevideo.com' in file_url or 'youtube.com' in file_url:
            # YouTube-specific strategies
            strategies = [
                {**get_random_headers(), 'Origin': 'https://www.youtube.com', 'Referer': 'https://www.youtube.com/'},
                {**get_random_headers(), 'Range': 'bytes=0-', 'Origin': 'https://www.youtube.com'},
                {**get_random_headers(), 'Connection': 'close', 'Origin': 'https://www.youtube.com'},
            ]
            download_strategies.extend(strategies)
        else:
            # Other platforms
            download_strategies.extend([
                get_random_headers(),
                {**get_random_headers(), 'Range': 'bytes=0-'},
                {**get_random_headers(), 'Connection': 'close'},
            ])
        
        for attempt, headers in enumerate(download_strategies):
            try:
                print(f"📥 Download attempt {attempt + 1}")
                
                if attempt > 0:
                    delay = random.uniform(1.0, 3.0)
                    print(f"⏳ Adding delay: {delay:.1f}s")
                    time.sleep(delay)
                
                response = requests.get(
                    file_url, 
                    headers=headers, 
                    stream=True, 
                    timeout=60,
                    allow_redirects=True
                )
                
                print(f"📊 Download response status: {response.status_code}")
                
                if response.status_code == 200:
                    total_size = response.headers.get('content-length')
                    if total_size:
                        print(f"📦 File size: {sizeof_fmt(int(total_size))}")
                    
                    file_ext = filename.split('.')[-1] if '.' in filename else 'mp4'
                    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_ext}')
                    tmp_file_path = tmp_file.name
                    
                    print("💾 Writing file to temporary location...")
                    downloaded_size = 0
                    
                    for chunk in response.iter_content(chunk_size=32768):  # Larger chunks for speed
                        if chunk:
                            tmp_file.write(chunk)
                            downloaded_size += len(chunk)
                    
                    tmp_file.close()
                    print(f"✅ Download completed successfully. Size: {sizeof_fmt(downloaded_size)}")
                    
                    def cleanup_file():
                        time.sleep(30)
                        try:
                            if os.path.exists(tmp_file_path):
                                os.unlink(tmp_file_path)
                                print("🧹 Temporary file cleaned up")
                        except Exception as e:
                            print(f"Cleanup error: {e}")
                    
                    response_obj = send_file(
                        tmp_file_path, 
                        as_attachment=True, 
                        download_name=filename,
                        mimetype='application/octet-stream'
                    )
                    
                    threading.Thread(target=cleanup_file).start()
                    return response_obj
                
                elif response.status_code == 403:
                    print(f"🚫 Attempt {attempt + 1}: Forbidden (403)")
                    continue
                elif response.status_code == 429:
                    print(f"⏸️ Attempt {attempt + 1}: Rate limited (429)")
                    time.sleep(random.uniform(5.0, 10.0))
                    continue
                else:
                    print(f"❌ Attempt {attempt + 1}: Status {response.status_code}")
                    continue
                    
            except requests.exceptions.Timeout:
                print(f"⏰ Attempt {attempt + 1}: Timeout")
                continue
            except requests.exceptions.ConnectionError:
                print(f"🔌 Attempt {attempt + 1}: Connection error")
                continue
            except Exception as e:
                print(f"❌ Attempt {attempt + 1}: Error {str(e)}")
                continue
        
        return jsonify({'error': 'All download attempts failed. File may be geo-restricted.'}), 400
        
    except Exception as e:
        print(f"💥 Download function error: {str(e)}")
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

# SUPER ENHANCED STREAMING (Works for all platforms including YouTube Shorts)
@app.route('/stream_media')
def stream_media():
    try:
        file_url = request.args.get('url')
        if not file_url:
            return abort(400)
        
        print(f"🎬 Enhanced streaming request for: {file_url[:100]}...")
        
        streaming_strategies = []
        
        if 'googlevideo.com' in file_url or 'youtube.com' in file_url:
            # YouTube streaming strategies
            strategies = [
                {**get_random_headers(), 'Origin': 'https://www.youtube.com', 'Referer': 'https://www.youtube.com/'},
                {**get_random_headers(), 'Range': 'bytes=0-1023', 'Origin': 'https://www.youtube.com'},
                {**get_random_headers(), 'Connection': 'keep-alive', 'Origin': 'https://www.youtube.com'},
            ]
            streaming_strategies.extend(strategies)
        else:
            # Other platforms
            streaming_strategies.extend([
                get_random_headers(),
                {**get_random_headers(), 'Range': 'bytes=0-1023'},
                {**get_random_headers(), 'Connection': 'keep-alive'},
            ])
        
        for attempt, headers in enumerate(streaming_strategies):
            try:
                if attempt > 0:
                    delay = random.uniform(0.5, 2.0)
                    time.sleep(delay)
                
                response = requests.get(
                    file_url, 
                    headers=headers, 
                    stream=True, 
                    timeout=20,
                    allow_redirects=True
                )
                
                print(f"📡 Stream attempt {attempt + 1} status: {response.status_code}")
                
                if response.status_code in [200, 206]:  # Accept partial content too
                    def generate():
                        try:
                            for chunk in response.iter_content(chunk_size=32768):
                                if chunk:
                                    yield chunk
                        except Exception as e:
                            print(f"🚨 Streaming error: {e}")
                            return
                    
                    content_type = response.headers.get('Content-Type', 'video/mp4')
                    print(f"🎭 Streaming content type: {content_type}")
                    
                    return Response(
                        generate(), 
                        content_type=content_type,
                        headers={
                            'Accept-Ranges': 'bytes',
                            'Cache-Control': 'no-cache, no-store, must-revalidate',
                            'Pragma': 'no-cache',
                            'Expires': '0',
                            'Access-Control-Allow-Origin': '*',
                        }
                    )
                elif response.status_code in [403, 429]:
                    continue
                else:
                    print(f"❌ Stream status: {response.status_code}")
                    continue
                    
            except Exception as e:
                print(f"🚨 Stream attempt {attempt + 1} error: {e}")
                continue
        
        return abort(503)
                       
    except Exception as e:
        print(f"💥 Stream media error: {e}")
        return abort(500)

# ENHANCED PROXY ROUTES (Compatibility)
@app.route('/proxy_download')
def proxy_download():
    file_url = request.args.get('url')
    if not file_url or not file_url.startswith('http'):
        return abort(400)
    
    headers = get_random_headers()
    if 'googlevideo.com' in file_url:
        headers.update({'Origin': 'https://www.youtube.com', 'Referer': 'https://www.youtube.com/'})
    
    try:
        r = requests.get(file_url, stream=True, headers=headers, timeout=45)
        if r.status_code != 200:
            return abort(r.status_code)
        
        def generate():
            for chunk in r.iter_content(chunk_size=16384):
                yield chunk
                
        return Response(generate(), content_type=r.headers.get('Content-Type', 'application/octet-stream'))
    except Exception as e:
        print(f"❌ Proxy download error: {e}")
        return abort(500)

@app.route('/proxy_media')
def proxy_media():
    file_url = request.args.get('url')
    if not file_url or not file_url.startswith('http'):
        return abort(400)
    
    headers = get_random_headers()
    if 'googlevideo.com' in file_url:
        headers.update({'Origin': 'https://www.youtube.com', 'Referer': 'https://www.youtube.com/'})
    
    try:
        r = requests.get(file_url, stream=True, headers=headers, timeout=20)
        if r.status_code not in [200, 206]:
            return abort(r.status_code)
        
        def generate():
            for chunk in r.iter_content(chunk_size=16384):
                yield chunk
                
        content_type = r.headers.get('Content-Type', 'application/octet-stream')
        return Response(generate(), content_type=content_type)
    except Exception as e:
        print(f"❌ Proxy media error: {e}")
        return abort(500)

# SUPER ENHANCED MERGE (Works with all platforms)
@app.route('/merge', methods=['POST'])
def merge_video_audio():
    try:
        video_url = request.json.get('video_url')
        audio_url = request.json.get('audio_url')

        print(f"🎬+🔊 SUPER MERGE - Video: {video_url[:100] if video_url else 'None'}...")
        print(f"🎬+🔊 SUPER MERGE - Audio: {audio_url[:100] if audio_url else 'None'}...")

        for link in (video_url, audio_url):
            if not (link and link.startswith('http')):
                return jsonify({'error': 'Invalid URL'}), 400

        def enhanced_download(url, filename, file_type="video"):
            for attempt in range(5):  # 5 attempts
                try:
                    headers = get_random_headers()
                    if 'googlevideo.com' in url:
                        headers.update({
                            'Origin': 'https://www.youtube.com',
                            'Referer': 'https://www.youtube.com/',
                        })
                    
                    if attempt > 0:
                        delay = random.uniform(1.0, 4.0)
                        print(f"⏳ {file_type} download attempt {attempt + 1}, delay: {delay:.1f}s")
                        time.sleep(delay)
                    
                    r = requests.get(url, stream=True, headers=headers, timeout=60)
                    
                    if r.status_code == 200:
                        print(f"📥 Downloading {file_type}...")
                        with open(filename, 'wb') as f:
                            downloaded = 0
                            for chunk in r.iter_content(chunk_size=32768):
                                if chunk:
                                    f.write(chunk)
                                    downloaded += len(chunk)
                        
                        print(f"✅ {file_type} downloaded: {sizeof_fmt(downloaded)}")
                        return True
                    else:
                        print(f"❌ {file_type} attempt {attempt + 1} failed with status {r.status_code}")
                        
                except Exception as e:
                    print(f"❌ {file_type} attempt {attempt + 1} error: {e}")
                    
            return False

        with tempfile.TemporaryDirectory() as td:
            video_path = os.path.join(td, 'video.mp4')
            audio_path = os.path.join(td, 'audio.m4a')
            output_path = os.path.join(td, 'merged.mp4')

            # Download both files with retry
            if not enhanced_download(video_url, video_path, "Video"):
                return jsonify({'error': 'Failed to download video after multiple attempts'}), 400

            if not enhanced_download(audio_url, audio_path, "Audio"):
                return jsonify({'error': 'Failed to download audio after multiple attempts'}), 400

            print("🔧 Starting enhanced FFmpeg merge...")
            
            # Enhanced FFmpeg command
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', audio_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', 'faststart',
                '-avoid_negative_ts', 'make_zero',
                '-fflags', '+genpts',
                output_path
            ]
            
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
            
            if result.returncode != 0:
                error_msg = result.stderr.decode()
                print(f"💥 FFmpeg error: {error_msg}")
                return jsonify({'error': f'FFmpeg merge failed: {error_msg[:200]}'}), 500

            if not os.path.exists(output_path):
                return jsonify({'error': 'Merged file not created'}), 500
                
            file_size = os.path.getsize(output_path)
            print(f"✅ Enhanced merge completed successfully ({sizeof_fmt(file_size)})")
            
            return send_file(output_path, as_attachment=True, download_name='merged_video.mp4')
            
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Merge timeout - files too large'}), 408
    except Exception as e:
        print(f"💥 Enhanced merge error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# COOKIE MANAGEMENT (Enhanced for all platforms)
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
        print(f"🍪 Updated cookies for {platform.upper()}")
        return jsonify({'status': f'{platform} cookies updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting SUPER ENHANCED ALL-PLATFORM DOWNLOADER...")
    print("✨ Features:")
    print("   📺 YouTube (Shorts + Long videos)")
    print("   📱 Instagram (Reels)")
    print("   📘 Facebook (Videos)")
    print("   📌 Pinterest (Videos)")
    print("   🛡️ Anti-detection with retry logic")
    print("   🔄 Header rotation and geo-bypass")
    print("   ⚡ Enhanced streaming and downloads")
    print("   🎬 Advanced merge capabilities")
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=True)
