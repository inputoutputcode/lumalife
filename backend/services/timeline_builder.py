from models.schema import get_db
from services.age_estimation import build_age_year_mapping, assign_era_buckets


async def build_timeline() -> dict:
    """Build the full timeline from current data."""
    db = await get_db()
    try:
        # Get all target person faces with their photos
        cursor = await db.execute("""
            SELECT DISTINCT f.photo_id, p.stored_filename, p.exif_date,
                   p.width, p.height, p.original_filename
            FROM faces f
            JOIN photos p ON f.photo_id = p.id
            WHERE f.is_target = 1
        """)
        target_photos = await cursor.fetchall()

        if not target_photos:
            return {"eras": [], "total_photos": 0}

        photo_map = {}
        for row in target_photos:
            photo_map[row[0]] = {
                "photo_id": row[0],
                "stored_filename": row[1],
                "exif_date": row[2],
                "width": row[3],
                "height": row[4],
                "original_filename": row[5],
                "url": f"/data/uploads/{row[1]}",
            }

        # Get user tags
        cursor = await db.execute("SELECT photo_id, year FROM tags")
        tag_rows = await cursor.fetchall()
        tagged_photos = [{"photo_id": r[0], "year": r[1]} for r in tag_rows]

        # Get age estimates
        cursor = await db.execute("""
            SELECT ae.photo_id, ae.estimated_age, p.exif_date
            FROM age_estimates ae
            JOIN photos p ON ae.photo_id = p.id
        """)
        age_rows = await cursor.fetchall()
        age_estimates = [
            {"photo_id": r[0], "estimated_age": r[1], "exif_date": r[2]}
            for r in age_rows
        ]

        # Build year mapping
        photo_years = build_age_year_mapping(tagged_photos, age_estimates)

        # Assign era buckets
        eras = assign_era_buckets(photo_years)

        # Build response with full photo data
        era_response = []
        for era in eras:
            era_photos = []
            for pid in era["photo_ids"]:
                if pid in photo_map:
                    photo_data = photo_map[pid].copy()
                    photo_data["estimated_year"] = photo_years.get(pid)

                    # Get tag if exists
                    tag = next((t for t in tagged_photos if t["photo_id"] == pid), None)
                    photo_data["tagged_year"] = tag["year"] if tag else None

                    era_photos.append(photo_data)

            # Sort photos within era by estimated year
            era_photos.sort(key=lambda p: p.get("estimated_year", 0))

            era_response.append({
                "label": era["label"],
                "era_start": era["era_start"],
                "era_end": era["era_end"],
                "photos": era_photos,
            })

        # Clear and rebuild timeline_entries
        await db.execute("DELETE FROM timeline_entries")
        sort_order = 0
        for era in era_response:
            for photo in era["photos"]:
                await db.execute(
                    """INSERT OR REPLACE INTO timeline_entries
                       (photo_id, estimated_year, era_label, era_start, era_end, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        photo["photo_id"],
                        photo.get("estimated_year", 0),
                        era["label"],
                        era["era_start"],
                        era["era_end"],
                        sort_order,
                    ),
                )
                sort_order += 1

        await db.commit()

        return {
            "eras": era_response,
            "total_photos": sum(len(e["photos"]) for e in era_response),
        }
    finally:
        await db.close()
