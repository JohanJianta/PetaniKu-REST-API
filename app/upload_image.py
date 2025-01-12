import os
import cloudinary
import cloudinary.uploader

# Configuration
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
    secure=True
)


def upload_to_cloudinary(images):  # Upload an image
    secure_urls = []
    for image in images:
        # Reset byte's pointer before upload
        image.seek(0)

        try:
            upload_result = cloudinary.uploader.upload(image.read())
            secure_urls.append(upload_result["secure_url"])
        except Exception:
            # Add emtpy string if failed to upload
            secure_urls.append("")
    return secure_urls
