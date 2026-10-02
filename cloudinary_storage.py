import os
import mimetypes
import logging
from werkzeug.utils import secure_filename
from datetime import datetime
from flask import redirect, send_from_directory

logger = logging.getLogger(__name__)

MIME_MAP = {
    '.pdf': 'application/pdf',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.svg': 'image/svg+xml',
    '.bmp': 'image/bmp',
    '.txt': 'text/plain',
    '.html': 'text/html',
    '.htm': 'text/html',
    '.mp4': 'video/mp4',
    '.webm': 'video/webm',
    '.mp3': 'audio/mpeg',
    '.wav': 'audio/wav',
    '.doc': 'application/msword',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.xls': 'application/vnd.ms-excel',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.ppt': 'application/vnd.ms-powerpoint',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
}

# Try to import and configure cloudinary
_cloudinary_configured = False
try:
    import cloudinary
    import cloudinary.uploader
    import cloudinary.utils

    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME')
    api_key = os.environ.get('CLOUDINARY_API_KEY')
    api_secret = os.environ.get('CLOUDINARY_API_SECRET')
    cloudinary_url = os.environ.get('CLOUDINARY_URL')

    if cloudinary_url or (cloud_name and api_key and api_secret):
        if not cloudinary_url:
            cloudinary.config(
                cloud_name=cloud_name,
                api_key=api_key,
                api_secret=api_secret,
                secure=True
            )
        _cloudinary_configured = True
        logger.info("Cloudinary storage successfully configured.")
    else:
        logger.info("Cloudinary credentials not detected in environment. Using local uploads fallback.")
except Exception as e:
    logger.warning(f"Cloudinary initialization notice: {e}. Falling back to local storage.")
    _cloudinary_configured = False


def is_cloudinary_enabled():
    """Returns True if Cloudinary is configured and ready."""
    return _cloudinary_configured


import urllib.request
import urllib.parse
from flask import redirect, send_from_directory, Response, abort, stream_with_context

def detect_mime(head_bytes, filename_or_url=''):
    """Detects MIME type and extension from file header bytes and URL."""
    ext = os.path.splitext(urllib.parse.urlparse(filename_or_url).path)[1].lower()
    
    if head_bytes.startswith(b'%PDF'):
        return 'application/pdf', '.pdf'
    elif head_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png', '.png'
    elif head_bytes.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg', '.jpg'
    elif head_bytes.startswith(b'GIF87a') or head_bytes.startswith(b'GIF89a'):
        return 'image/gif', '.gif'
    elif head_bytes.startswith(b'RIFF') and b'WEBP' in head_bytes[:16]:
        return 'image/webp', '.webp'
    elif head_bytes.startswith(b'PK\x03\x04'):
        # ZIP / Office OpenXML
        if ext in ['.xlsx', '.xls']:
            return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', '.xlsx'
        elif ext in ['.pptx', '.ppt']:
            return 'application/vnd.openxmlformats-officedocument.presentationml.presentation', '.pptx'
        return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', '.docx'
    elif head_bytes.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):
        # Old binary Office (doc, xls, ppt)
        if ext in ['.xls']:
            return 'application/vnd.ms-excel', '.xls'
        elif ext in ['.ppt']:
            return 'application/vnd.ms-powerpoint', '.ppt'
        return 'application/msword', '.doc'
    
    if ext and ext in MIME_MAP:
        return MIME_MAP[ext], ext
        
    return 'application/octet-stream', ext or ''


def upload_document(file_obj, subfolder='documents', prefix=None, local_folder_path=None):
    """
    Uploads a file to Cloudinary if configured; otherwise saves locally.
    
    Args:
        file_obj: FileStorage object from request.files
        subfolder: Folder name in Cloudinary (e.g. 'notices', 'performance', 'permissions', 'logos')
        prefix: Optional prefix for filename
        local_folder_path: Path on local disk if fallback is used
        
    Returns:
        str: Either a full Cloudinary secure URL (https://res.cloudinary.com/...) or a local filename.
    """
    if not file_obj or not file_obj.filename:
        return None

    orig_name = secure_filename(file_obj.filename)
    timestamp = int(datetime.utcnow().timestamp())
    base_name = f"{prefix}_{timestamp}_{orig_name}" if prefix else f"{timestamp}_{orig_name}"

    if is_cloudinary_enabled():
        try:
            # Upload to Cloudinary with automatic resource detection and filename preservation
            file_obj.seek(0)
            upload_result = cloudinary.uploader.upload(
                file_obj,
                folder=f"genzcampus/{subfolder}",
                public_id=base_name,
                resource_type="auto",
                use_filename=True,
                unique_filename=False
            )
            secure_url = upload_result.get('secure_url')
            if secure_url:
                logger.info(f"Uploaded file to Cloudinary: {secure_url}")
                return secure_url
        except Exception as e:
            logger.error(f"Cloudinary upload failed ({e}). Falling back to local disk storage.")

    # Local fallback
    if local_folder_path:
        os.makedirs(local_folder_path, exist_ok=True)
        local_dest = os.path.join(local_folder_path, base_name)
        file_obj.seek(0)
        file_obj.save(local_dest)
        return base_name

    return None


def serve_document(file_path_or_url, local_dir=None, download=False):
    """
    Serves a document either by opening inline in the browser or triggering a download.
    
    Args:
        file_path_or_url: The stored string in database (URL or local filename)
        local_dir: Local directory path if file is stored locally
        download: True to download as attachment, False to view inline in browser
    """
    if not file_path_or_url:
        abort(404)

    # Normalize URLs if protocol slashes were collapsed during URL path routing (e.g. https:/res.cloudinary.com)
    if file_path_or_url.startswith('https:/') and not file_path_or_url.startswith('https://'):
        file_path_or_url = 'https://' + file_path_or_url[7:]
    elif file_path_or_url.startswith('http:/') and not file_path_or_url.startswith('http://'):
        file_path_or_url = 'http://' + file_path_or_url[6:]
    elif 'res.cloudinary.com' in file_path_or_url and not (file_path_or_url.startswith('http://') or file_path_or_url.startswith('https://')):
        file_path_or_url = 'https://' + file_path_or_url.lstrip('/')

    # 1. Handle Remote / Cloudinary URLs
    if file_path_or_url.startswith('http://') or file_path_or_url.startswith('https://'):
        target_url = file_path_or_url
        if 'cloudinary.com' in target_url:
            target_url = target_url.replace('/upload/fl_attachment/', '/upload/')
            target_url = target_url.replace('/upload/fl_inline/', '/upload/')
            target_url = target_url.replace('/fl_attachment/', '/')
            target_url = target_url.replace('/fl_inline/', '/')

        # If user explicitly requested download
        if download:
            if 'cloudinary.com' in target_url and '/raw/' not in target_url:
                return redirect(target_url.replace('/upload/', '/upload/fl_attachment/'))
            
            try:
                req = urllib.request.Request(target_url, headers={'User-Agent': 'Mozilla/5.0'})
                remote_file = urllib.request.urlopen(req, timeout=10)
                head = remote_file.read(2048)
                mimetype, ext = detect_mime(head, target_url)
                base_name = os.path.basename(urllib.parse.urlparse(target_url).path) or "document"
                if ext and not base_name.lower().endswith(ext.lower()):
                    base_name = f"{base_name}{ext}"

                def generate_download():
                    yield head
                    while True:
                        chunk = remote_file.read(65536)
                        if not chunk:
                            break
                        yield chunk

                response = Response(stream_with_context(generate_download()), mimetype=mimetype or 'application/octet-stream')
                response.headers['Content-Disposition'] = f'attachment; filename="{base_name}"'
                return response
            except Exception as e:
                logger.error(f"Error streaming download: {e}")
                return redirect(target_url)

        # If user wants to VIEW (inline)
        # Check if it's already an image or PDF URL that the browser handles natively
        url_lower = target_url.lower()
        if any(url_lower.endswith(img_ext) for img_ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.pdf']):
            return redirect(target_url)

        # For raw Cloudinary files or URLs without clear extensions, inspect header bytes
        try:
            req = urllib.request.Request(target_url, headers={'User-Agent': 'Mozilla/5.0'})
            remote_file = urllib.request.urlopen(req, timeout=10)
            head = remote_file.read(2048)
            mimetype, ext = detect_mime(head, target_url)
            base_name = os.path.basename(urllib.parse.urlparse(target_url).path) or "document"
            if ext and not base_name.lower().endswith(ext.lower()):
                base_name = f"{base_name}{ext}"

            # If it's a PDF, Image, or plain text: stream it directly so browser displays it inline
            if mimetype and (mimetype.startswith('image/') or mimetype == 'application/pdf' or mimetype.startswith('text/')):
                def generate_inline():
                    yield head
                    while True:
                        chunk = remote_file.read(65536)
                        if not chunk:
                            break
                        yield chunk

                response = Response(stream_with_context(generate_inline()), mimetype=mimetype)
                response.headers['Content-Disposition'] = f'inline; filename="{base_name}"'
                response.headers['Content-Type'] = mimetype
                response.headers['X-Content-Type-Options'] = 'nosniff'
                return response

            # If it's an Office document (DOCX, PPTX, XLSX), use Google Docs Viewer so the user can view it directly online!
            if mimetype in [
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                'application/vnd.ms-powerpoint',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'application/vnd.ms-excel'
            ]:
                encoded_url = urllib.parse.quote(target_url, safe=':/')
                return redirect(f"https://docs.google.com/viewer?url={encoded_url}&embedded=false")

            # Default fallback for other files: stream inline
            def generate_generic():
                yield head
                while True:
                    chunk = remote_file.read(65536)
                    if not chunk:
                        break
                    yield chunk

            response = Response(stream_with_context(generate_generic()), mimetype=mimetype or 'application/octet-stream')
            response.headers['Content-Disposition'] = f'inline; filename="{base_name}"'
            return response

        except Exception as e:
            logger.error(f"Error inspecting/serving remote document: {e}")
            return redirect(target_url)

    # 2. Local file handling with explicit inline/attachment headers
    if local_dir:
        full_path = os.path.join(local_dir, file_path_or_url)
        if os.path.exists(full_path):
            ext = os.path.splitext(file_path_or_url)[1].lower()
            mimetype = MIME_MAP.get(ext) or mimetypes.guess_type(file_path_or_url)[0] or 'application/octet-stream'
            
            response = send_from_directory(local_dir, file_path_or_url, as_attachment=download, mimetype=mimetype)
            base_name = os.path.basename(file_path_or_url)
            if not download:
                response.headers['Content-Disposition'] = f'inline; filename="{base_name}"'
                response.headers['Content-Type'] = mimetype
                response.headers['X-Content-Type-Options'] = 'nosniff'
            else:
                response.headers['Content-Disposition'] = f'attachment; filename="{base_name}"'
            return response

    abort(404)
