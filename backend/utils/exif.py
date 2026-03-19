from PIL import Image, ImageOps
from PIL.ExifTags import TAGS
import io
from datetime import datetime

# Human-readable orientation labels
ORIENTATION_LABELS = {
    1: "Normal",
    2: "Mirrored horizontal",
    3: "Rotated 180°",
    4: "Mirrored vertical",
    5: "Mirrored horizontal + rotated 270°",
    6: "Rotated 270° (camera held right)",
    7: "Mirrored horizontal + rotated 90°",
    8: "Rotated 90° (camera held left)",
}


def extract_exif(image_bytes: bytes) -> dict:
    """Extract useful EXIF data and return cleaned dict."""
    result = {
        "date": None,
        "orientation": 1,
        "orientation_label": "Normal",
        "had_exif": False,
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

        result["had_exif"] = True
        tag_map = {v: k for k, v in TAGS.items()}

        # Orientation
        orientation_tag = tag_map.get("Orientation")
        if orientation_tag and orientation_tag in exif_data:
            orientation = exif_data[orientation_tag]
            result["orientation"] = orientation
            result["orientation_label"] = ORIENTATION_LABELS.get(orientation, f"Unknown ({orientation})")

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


def strip_exif(image_bytes: bytes) -> bytes:
    """Remove EXIF data from image, applying orientation correction first."""
    try:
        img = Image.open(io.BytesIO(image_bytes))

        # Use Pillow's built-in EXIF transpose — handles all 8 orientations
        # including mirroring (orientations 2, 4, 5, 7)
        img = ImageOps.exif_transpose(img)

        # Save without EXIF
        output = io.BytesIO()
        img_format = img.format or "JPEG"
        if img_format.upper() == "MPO":
            img_format = "JPEG"
        img.save(output, format=img_format, quality=95)
        return output.getvalue()
    except Exception:
        return image_bytes
