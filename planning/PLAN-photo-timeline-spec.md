# PLAN-photo-timeline — Implementation Spec

## Architecture
```
┌─────────────────────────────┐
│  Svelte + GSAP Frontend     │
│  (Timeline UI, Upload, Tag) │
└──────────┬──────────────────┘
           │ REST API
┌──────────▼──────────────────┐
│  Python Backend (FastAPI)    │
│  - Upload handler            │
│  - DeepFace processing       │
│  - Timeline data API         │
└──────────┬──────────────────┘
           │
┌──────────▼──────────────────┐
│  Docker Volume (/data)       │
│  uploads/ processed/ embed/  │
└─────────────────────────────┘
```

## Tech Stack
- **Backend:** Python, FastAPI, DeepFace (ArcFace), SQLite, Docker
- **Frontend:** Svelte, GSAP (ScrollTrigger/ScrollSmoother)
- **Storage:** Docker volume, local only

## User Flow
1. Upload up to 100 photos
2. AI detects faces, clusters them, presents largest cluster
3. User confirms "this is me"
4. User tags min 8 (recommended 15) photos with years
5. AI estimates ages, trusts EXIF dates, interpolates the rest
6. Photos grouped into ~5-year eras on vertical scrollable timeline
7. Dark museum-style UI, full-bleed sections, mini-map navigation

## Task Breakdown

### Task 1: Project Scaffolding (~2h)
- Docker Compose: Python backend + Svelte frontend + shared volume
- FastAPI boilerplate with CORS
- Svelte project with GSAP dependency
- `/data/uploads/`, `/data/processed/`, `/data/embeddings/` volume structure

### Task 2: Upload Endpoint (~3h)
- `POST /api/photos/upload` — accepts multiple images
- MIME + magic byte validation
- Strip filename → UUID rename
- Size limit 20MB per file, 100 files max
- Extract EXIF date + orientation, strip rest
- Store metadata in SQLite

### Task 3: Face Detection & Clustering (~4h)
- `POST /api/photos/process` — triggers batch processing
- DeepFace face detection on all uploads
- Extract face embeddings (ArcFace backend)
- Cluster embeddings (DBSCAN or agglomerative clustering)
- Store: face crops, embeddings, cluster assignments
- Concurrency limit (2-3 parallel), 30s timeout per image
- WebSocket or SSE for progress updates to frontend

### Task 4: Identity Confirmation UI (~3h)
- Frontend shows detected face clusters after processing
- Largest cluster highlighted: "Is this you?"
- User confirms → cluster marked as target person
- Other clusters ignored for v1

### Task 5: Year Tagging UI (~3h)
- Show target person's photos (face crops + full image)
- User assigns year to each tagged photo
- Accuracy indicator: "⭐⭐⭐☆☆ — tag 7 more for better results"
- Minimum 8 required, recommend 15
- `POST /api/photos/{id}/tag` — stores year assignment

### Task 6: Age Estimation & Timeline Placement (~4h)
- DeepFace age estimation on all target person photos
- Build age-to-year mapping from user tags (anchor points)
- EXIF dates trusted as-is when present
- Interpolate untagged photos using: age estimate + anchor curve
- Assign each photo to an era bucket (~5-year groups)
- `GET /api/timeline` — returns photos grouped by era with estimated years

### Task 7: Timeline UI (~6h)
- Svelte + GSAP ScrollTrigger + ScrollSmoother
- Dark background, full-bleed photo sections per era
- Photos fade/scale in on scroll
- Vertical mini-map on the side for navigation
- Era labels with year ranges
- Click photo → detail view with exact year estimate
- Responsive (desktop-first, but scrollable on mobile)

### Task 8: Data Management (~2h)
- "Delete all data" button — wipes uploads, embeddings, DB
- Re-process button (re-run pipeline after adding more tags)
- Export timeline as JSON

## File Structure
```
photo-timeline/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt (pinned)
│   ├── main.py (FastAPI app)
│   ├── routers/
│   │   ├── upload.py
│   │   ├── process.py
│   │   ├── tag.py
│   │   └── timeline.py
│   ├── services/
│   │   ├── face_detection.py
│   │   ├── age_estimation.py
│   │   ├── clustering.py
│   │   └── timeline_builder.py
│   ├── models/
│   │   └── schema.py (SQLite models)
│   └── utils/
│       ├── exif.py
│       └── validation.py
├── frontend/
│   ├── Dockerfile
│   ├── package.json (pinned)
│   ├── src/
│   │   ├── App.svelte
│   │   ├── routes/
│   │   │   ├── Upload.svelte
│   │   │   ├── Identify.svelte
│   │   │   ├── Tag.svelte
│   │   │   └── Timeline.svelte
│   │   ├── components/
│   │   │   ├── PhotoGrid.svelte
│   │   │   ├── FaceCluster.svelte
│   │   │   ├── AccuracyMeter.svelte
│   │   │   ├── TimelineSection.svelte
│   │   │   └── MiniMap.svelte
│   │   └── lib/
│   │       └── gsap-setup.js
└── data/ (Docker volume)
```

## Dependencies
- **Backend:** FastAPI, uvicorn, deepface, scikit-learn (clustering), Pillow, python-multipart, SQLite (stdlib)
- **Frontend:** Svelte (SvelteKit), GSAP (ScrollTrigger, ScrollSmoother)

## Key Decisions
- Upload all → AI clusters faces → user confirms identity → tags with years
- Batch async processing with progress indicator
- Largest face cluster assumed as user, confirm
- Hybrid timeline: era groups + exact year on detail
- Other faces excluded in v1
- EXIF dates trusted as-is
- Min 8 tagged photos, recommend 15, show accuracy indicator
- Local Docker deployment only for v1, no auth

## Security
- Validate MIME + magic bytes on upload
- UUID filenames (strip originals)
- Strip EXIF after extraction
- Pin all dependency versions
- Process queue with concurrency limit + timeout
- "Delete all data" function from day 1
- Face embeddings are biometric data — document for future GDPR/BIPA compliance

## Repo
- https://github.com/inputoutputcode/lumalife.git

## Total Estimated Effort: ~27 hours
