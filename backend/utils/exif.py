from PIL import Image
from PIL.ExifTags import TAGS
import io
from datetime import datetime


def extract_exif(image_bytes: bytes) -> dict:
    """Extract useful EXIF data and return cleaned dict."""
    result = {
        "date": None,
        "orientation": 1,
        "width": None,
        "height": None,
    }

    try:
        img = Image.open(io.BytesIO(image_bytes))
        result["width"] = img.width
        result["height"] = img.height

        exif_data = img.getexif()
        if not exif_data:
            return result

        tag_map = {v: k for k, v in TAGS.items()}

        # Orientation
        orientation_tag = tag_map.get("Orientation")
        if orientation_tag and orientation_tag in exif_data:
            result["orientation"] = exif_data[orientation_tag]

        # Date
        for date_tag_name in ["DateTimeOriginal", "DateTimeDigitized", "DateTime"]:
            date_tag = tag_map.get(date_tag_name)
            if date_tag and date_tag in exif_data:
                date_str = exif_data[date_tag]
                try:
                    dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                    result["date"] = dt.isoformat()
                    break
                except (ValueError, TypeError):
                    continue
    except Exception:
        pass

    return result


def strip_exif(image_bytes: bytes, keep_orientation: bool = True) -> bytes:
    """Remove EXIF data from image, optionally preserving orientation."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        orientation = 1

        if keep_orientation:
            exif_data = img.getexif()
            tag_map = {v: k for k, v in TAGS.items()}
            orientation_tag = tag_map.get("Orientation")
            if orientation_tag and orientation_tag in exif_data:
                orientation = exif_data[orientation_tag]

        # Apply orientation transform
        rotation_map = {
            3: 180,
            6: 270,
            8: 90,
        }
        if orientation in rotation_map:
            img = img.rotate(rotation_map[orientation], expand=True)

        # Save without EXIF
        output = io.BytesIO()
        img_format = img.format or "JPEG"
        if img_format.upper() == "MPO":
            img_format = "JPEG"
        img.save(output, format=img_format, quality=95)
        return output.getvalue()
    except Exception:
        return image_bytes
