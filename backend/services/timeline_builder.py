from models.schema import get_pool
from services.age_estimation import build_age_year_mapping, assign_era_buckets


async def build_timeline(user_id: int, username: str = "default") -> dict:
    """Build the full timeline from current data."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Get all user photos (not just face-detected ones)
        target_photos = await conn.fetch("""
            SELECT p.id as photo_id, p.stored_filename, p.exif_date,
                   p.width, p.height, p.original_filename
            FROM photos p
            WHERE p.user_id = $1
        """, user_id)

        if not target_photos:
            return {"eras": [], "total_photos": 0}

        photo_map = {}
        for row in target_photos:
            photo_map[row["photo_id"]] = {
                "photo_id": row["photo_id"],
                "stored_filename": row["stored_filename"],
                "exif_date": row["exif_date"],
                "width": row["width"],
                "height": row["height"],
                "original_filename": row["original_filename"],
                "url": f"/data/{username}/uploads/{row['stored_filename']}",
            }

        # Get user tags
        tag_rows = await conn.fetch(
            "SELECT t.photo_id, t.year FROM tags t JOIN photos p ON t.photo_id = p.id WHERE p.user_id = $1",
            user_id,
        )
        tagged_photos = [{"photo_id": r["photo_id"], "year": r["year"]} for r in tag_rows]

        # Get age estimates
        age_rows = await conn.fetch("""
            SELECT ae.photo_id, ae.estimated_age, p.exif_date
            FROM age_estimates ae
            JOIN photos p ON ae.photo_id = p.id
            WHERE p.user_id = $1
        """, user_id)
        age_estimates = [
            {"photo_id": r["photo_id"], "estimated_age": r["estimated_age"], "exif_date": r["exif_date"]}
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

        # Add "Undated" section for photos without a year
        dated_ids = set(photo_years.keys())
        undated_photos = []
        for pid, pdata in photo_map.items():
            if pid not in dated_ids:
                photo_data = pdata.copy()
                photo_data["estimated_year"] = None
                photo_data["tagged_year"] = None
                undated_photos.append(photo_data)

        if undated_photos:
            era_response.append({
                "label": "Undated",
                "era_start": 9999,
                "era_end": 9999,
                "photos": undated_photos,
            })

        # Clear and rebuild timeline_entries for this user
        await conn.execute(
            "DELETE FROM timeline_entries WHERE photo_id IN (SELECT id FROM photos WHERE user_id = $1)",
            user_id,
        )
        sort_order = 0
        for era in era_response:
            for photo in era["photos"]:
                await conn.execute(
                    """INSERT INTO timeline_entries
                       (photo_id, estimated_year, era_label, era_start, era_end, sort_order)
                       VALUES ($1, $2, $3, $4, $5, $6)
                       ON CONFLICT (photo_id) DO UPDATE SET
                           estimated_year = $2, era_label = $3,
                           era_start = $4, era_end = $5, sort_order = $6""",
                    photo["photo_id"],
                    photo.get("estimated_year") or 0,
                    era["label"],
                    era["era_start"],
                    era["era_end"],
                    sort_order,
                )
                sort_order += 1

        total = sum(len(e["photos"]) for e in era_response)
        undated_count = len(undated_photos) if undated_photos else 0
        return {
            "eras": era_response,
            "total_photos": total,
            "undated_count": undated_count,
        }
