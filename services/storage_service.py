import os
import shutil
import logging
import cv2

logger = logging.getLogger('retina_xai.storage')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
UPLOADS_DIR = os.path.join(STATIC_DIR, 'uploads')
GENERATED_DIR = os.path.join(STATIC_DIR, 'generated')
SAMPLES_DIR = os.path.join(STATIC_DIR, 'samples')

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(GENERATED_DIR, exist_ok=True)
os.makedirs(SAMPLES_DIR, exist_ok=True)

class StorageService:
    """
    Storage layer abstraction.
    Separates database metadata from file/image storage.
    Defaults to local static filesystem storage (compatible with current AI pipeline)
    and allows future plug-and-play cloud storage (e.g. S3, Cloudinary).
    """
    def __init__(self):
        self.provider = os.environ.get('STORAGE_PROVIDER', 'local').lower()

    def get_upload_path(self, filename):
        return os.path.join(UPLOADS_DIR, filename)

    def get_generated_path(self, filename):
        return os.path.join(GENERATED_DIR, filename)

    def get_sample_path(self, filename):
        return os.path.join(SAMPLES_DIR, filename)

    def save_upload(self, file_storage, filename):
        """Saves an incoming uploaded file."""
        abs_path = self.get_upload_path(filename)
        file_storage.save(abs_path)
        rel_path = f"static/uploads/{filename}"
        return abs_path, rel_path

    def copy_sample(self, sample_name, target_filename):
        """Copies a preloaded sample case to the uploads folder for processing."""
        sample_abs = self.get_sample_path(sample_name)
        target_abs = self.get_upload_path(target_filename)
        if not os.path.exists(sample_abs):
            raise FileNotFoundError(f"Sample image {sample_name} not found.")
        shutil.copyfile(sample_abs, target_abs)
        rel_path = f"static/uploads/{target_filename}"
        return target_abs, rel_path

    def save_cv2_image(self, img_bgr, filename, folder='generated'):
        """Saves an OpenCV BGR image array to disk."""
        target_dir = GENERATED_DIR if folder == 'generated' else UPLOADS_DIR
        abs_path = os.path.join(target_dir, filename)
        cv2.imwrite(abs_path, img_bgr)
        rel_path = f"static/{folder}/{filename}"
        return abs_path, rel_path

    def delete_file(self, abs_path):
        """Safely removes a file, e.g. when image validation fails."""
        if abs_path and os.path.exists(abs_path):
            try:
                os.remove(abs_path)
            except Exception as e:
                logger.warning(f"Failed to delete file {abs_path}: {e}")

storage_service = StorageService()
