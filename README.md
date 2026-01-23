# Oral Health Monitoring System V1

An intelligent oral health monitoring system based on video analysis with strict A/B/C data stream isolation architecture.

## Core Features

### Data Stream Isolation Architecture
- **B Stream (Base Layer)**: Read-only raw video repository, Write-Once constraint
- **A Stream (Application Layer)**: Business application layer for keyframes and structured data
- **C Stream (Copy/Training Layer)**: Training sandbox layer (V1 interface reserved)

### Key Functionalities
1. **Dual-Track Keyframe Extraction**
   - Rule-triggered frames: OpenCV-based anomaly detection
   - Uniform sampling: Timeline-based distribution
   - Smart merge and deduplication, max 25 frames

2. **Video Processing Pipeline**
   - Video validation (≤30s, ≤100MB)
   - File hash deduplication
   - Keyframe extraction and caching
   - Thumbnail generation

3. **User Profile System**
   - Quick Check tracking
   - Full oral baseline mapping (7 zones)
   - Historical timeline

4. **LLM Health Report**
   - Generate reports based on EvidencePack
   - Qianwen multimodal API integration
   - Custom prompt support

## System Architecture

```
Oral Video → Ingestion → B Stream Storage (Write-Once)
                              ↓
                    Dual-Track Extraction
                  (Rule + Uniform Sampling)
                              ↓
              A Stream Keyframes + Metadata
                              ↓
                    EvidencePack Generation
                              ↓
                  Qianwen LLM Report Generation
```

## Quick Start

### 1. Requirements
- Python 3.10+
- PostgreSQL 15+
- OpenCV
- Qianwen API Key

### 2. Install Dependencies

```bash
# Navigate to project
cd oral_algorithm

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
# Copy environment template
cp .env.example .env

# Edit .env file and configure:
# - QIANWEN_API_KEY: Qianwen API key (REQUIRED)
# - DB_PASSWORD: Database password
# - JWT_SECRET_KEY: JWT secret (change in production)
```

### 4. Start Database

```bash
# Use Docker Compose to start PostgreSQL
docker-compose up -d

# Wait for database to be ready
sleep 5
```

### 5. Initialize Database

```bash
# Run database initialization script
python migrations/init_db.py init
```

### 6. Start Application

```bash
# Development mode (auto-reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 7. Access API Documentation

Open browser and visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Usage Examples

### 1. Upload Quick Check Video

```bash
curl -X POST "http://localhost:8000/api/v1/upload/quick-check" \
  -F "video_file=@test_video.mp4" \
  -F "user_id=user_12345" \
  -F "user_text=My teeth feel uncomfortable today"
```

**Response:**
```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "completed",
  "message": "Video processing completed",
  "estimated_time": null
}
```

### 2. Upload Baseline Video

```bash
curl -X POST "http://localhost:8000/api/v1/upload/baseline" \
  -F "video_file=@zone1.mp4" \
  -F "user_id=user_12345" \
  -F "zone_id=1"
```

**Response:**
```json
{
  "session_id": "session_abc456",
  "status": "completed",
  "message": "Baseline video processing completed",
  "baseline_progress": "1/7"
}
```

### 3. Get User Profile

```bash
curl -X GET "http://localhost:8000/api/v1/user/user_12345/profile"
```

**Response:**
```json
{
  "user_id": "user_12345",
  "baseline_completed": false,
  "baseline_zones": [
    {
      "zone_id": 1,
      "session_id": "session_abc",
      "completed_at": "2025-01-23T10:00:00Z"
    }
  ],
  "total_quick_checks": 5,
  "last_check_date": "2025-01-23T09:00:00Z",
  "created_at": "2025-01-15T08:00:00Z"
}
```

### 4. Get Evidence Pack

```bash
curl -X GET "http://localhost:8000/api/v1/session/{session_id}/evidence-pack"
```

**Response:**
```json
{
  "session_id": "session_abc",
  "user_id": "user_12345",
  "session_type": "quick_check",
  "created_at": "2025-01-23T10:00:00Z",
  "total_frames": 15,
  "frames": [
    {
      "frame_id": "frame_001",
      "timestamp": "00:05",
      "meta_tags": {
        "side": "upper",
        "tooth_type": "posterior",
        "region": "occlusal",
        "detected_issues": ["dark_deposit"]
      },
      "image_url": "/data/a_stream/session_abc/frame_001.jpg",
      "anomaly_score": 0.85,
      "extraction_strategy": "rule_triggered"
    }
  ]
}
```

### 5. Generate Health Report

```bash
curl -X POST "http://localhost:8000/api/v1/session/{session_id}/report"
```

**Response:**
```json
{
  "report_id": "report_xyz123",
  "session_id": "session_abc",
  "report_text": "Based on your oral video analysis, we detected...",
  "llm_model": "qwen-max",
  "tokens_used": 1500,
  "generated_at": "2025-01-23T10:05:00Z"
}
```

## Project Structure

```
oral_health_system/
├── app/
│   ├── api/              # API routes (reserved)
│   ├── core/             # Core business logic
│   │   ├── ingestion.py           # Video ingestion
│   │   ├── keyframe_extractor.py  # Dual-track extraction ⭐ CORE
│   │   ├── evidence_pack.py       # Evidence pack generator
│   │   ├── profile_manager.py     # User profile manager
│   │   └── llm_client.py          # LLM report generator
│   ├── models/           # Data models
│   │   ├── database.py            # SQLAlchemy ORM
│   │   ├── evidence_pack.py       # Pydantic models
│   │   └── schemas.py             # API schemas
│   ├── services/         # External services
│   │   ├── qianwen_vision.py      # Qianwen API wrapper
│   │   └── storage.py             # File storage service
│   ├── utils/            # Utility functions
│   │   ├── video.py               # Video processing (OpenCV)
│   │   └── hash.py                # File hash calculation
│   ├── config.py         # Configuration management
│   └── main.py           # FastAPI main app ⭐ ENTRY
├── data/                 # Data storage
│   ├── a_stream/         # A Stream: Keyframes
│   ├── b_stream/         # B Stream: Raw videos
│   └── c_stream/         # C Stream: Training data (reserved)
├── migrations/           # Database migrations
│   ├── init_schema.sql   # Table structure definition
│   └── init_db.py        # Initialization script
├── .env.example          # Environment variable template
├── requirements.txt      # Python dependencies
├── docker-compose.yml    # Docker configuration
└── README.md             # This document
```

## Database Schema

### Core Tables

**B Stream:**
- `b_raw_videos`: Raw videos (Write-Once)

**A Stream:**
- `a_sessions`: Session records
- `a_keyframes`: Keyframe table
- `a_evidence_packs`: Evidence pack table
- `a_user_profiles`: User profiles
- `a_reports`: LLM reports

**C Stream (reserved):**
- `c_training_snapshots`: Training snapshots
- `c_annotations`: Annotation table

See `migrations/init_schema.sql` for details.

## Tech Stack

- **Web Framework**: FastAPI
- **Database**: PostgreSQL + SQLAlchemy
- **Video Processing**: OpenCV
- **Image Processing**: Pillow
- **AI Service**: Qianwen Multimodal API
- **Data Validation**: Pydantic

## Development

### Run Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black app/
flake8 app/
```

### Database Management

```bash
# Reset database (DANGER!)
python migrations/init_db.py drop
python migrations/init_db.py init
```

## Important Notes

1. **B Stream Protection**: Raw videos in B stream are write-once protected, enforced by database triggers
2. **API Key**: Qianwen API key must be configured for report generation
3. **Video Limits**:
   - Max duration: 30 seconds
   - Max file size: 100MB
   - Supported format: MP4
4. **Keyframe Count**: Final output 5-25 frames

## FAQ

### Q: Video upload failed?
A: Check if video exceeds 30s or 100MB limit

### Q: Database connection failed?
A: Ensure PostgreSQL is running, check `.env` database config

### Q: Report generation failed?
A: Check if Qianwen API key is correctly configured

### Q: How to view logs?
A: Check console output, or configure `LOG_FILE` environment variable

## License

MIT License

## Contact

For questions, please contact the development team.

---

## Core Algorithm: Dual-Track Keyframe Extraction

The system uses a sophisticated dual-track algorithm:

1. **Track 1 - Rule-Triggered Frames**:
   - HSV color space analysis
   - Black deposit detection (dark regions)
   - Yellow plaque detection (yellow regions)
   - Red gum inflammation detection
   - Anomaly score ≥ threshold → priority frame

2. **Track 2 - Uniform Sampling**:
   - Timeline-based uniform distribution
   - Quality score calculation
   - Fill remaining slots up to max frames

3. **Merge & Deduplication**:
   - Priority frames take precedence
   - Remove duplicates by frame index
   - Sort by anomaly score
   - Limit to max 25 frames

## Data Flow Isolation

### B Stream (Base Layer)
- **Purpose**: Immutable raw video repository
- **Access**: Write-once, read-only
- **Protection**: Database trigger prevents updates
- **Storage**: `/data/b_stream/{user_id}/{file_hash}.mp4`

### A Stream (Application Layer)
- **Purpose**: Business data and keyframes
- **Access**: Read/write for application
- **Content**: Keyframes, metadata, evidence packs
- **Storage**: `/data/a_stream/{session_id}/frame_*.jpg`

### C Stream (Copy/Training Layer)
- **Purpose**: ML training and experimentation
- **Access**: Read/write for training
- **Rule**: Data must be copied from B stream
- **Status**: Interface reserved in V1

## Configuration Reference

### Required Environment Variables

```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your-password
DB_NAME=oral_health_db

# Qianwen API (REQUIRED)
QIANWEN_API_KEY=your-api-key-here
QIANWEN_VISION_MODEL=qwen-vl-max
QIANWEN_TEXT_MODEL=qwen-max

# Security
JWT_SECRET_KEY=change-this-in-production
```

### Optional Configuration

```bash
# Video processing
MAX_VIDEO_SIZE_MB=100
MAX_VIDEO_DURATION_SEC=30
MAX_KEYFRAMES=25
MIN_KEYFRAMES=5

# Keyframe extraction
UNIFORM_SAMPLE_COUNT=20
PRIORITY_FRAME_THRESHOLD=0.5
KEYFRAME_QUALITY=85

# Logging
LOG_LEVEL=INFO
LOG_FILE=
```

## API Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Root endpoint |
| GET | `/health` | Health check |
| POST | `/api/v1/upload/quick-check` | Upload quick check video |
| POST | `/api/v1/upload/baseline` | Upload baseline video |
| GET | `/api/v1/user/{user_id}/profile` | Get user profile |
| GET | `/api/v1/session/{session_id}/status` | Get session status |
| GET | `/api/v1/session/{session_id}/evidence-pack` | Get evidence pack |
| POST | `/api/v1/session/{session_id}/report` | Generate health report |
| GET | `/api/v1/session/{session_id}/report` | Get existing report |

## Troubleshooting

### Issue: Import errors when starting the app
**Solution**: Make sure you're in the project root directory and virtual environment is activated

### Issue: Database initialization fails
**Solution**:
1. Check PostgreSQL is running: `docker-compose ps`
2. Check database credentials in `.env`
3. Try: `docker-compose down && docker-compose up -d`

### Issue: Video processing takes too long
**Solution**: Video processing is synchronous in V1. For production, implement async task queue (Celery)

### Issue: Keyframes not extracted
**Solution**:
1. Check video format (must be MP4)
2. Check video duration (≤30s)
3. Check OpenCV installation: `python -c "import cv2; print(cv2.__version__)"`

## Next Steps

### Feature Enhancements
- [ ] Real Qianwen Vision API integration for meta tag generation
- [ ] User authentication system (JWT complete implementation)
- [ ] Async task queue (Celery) for long video processing
- [ ] File access signed URLs (prevent unauthorized access)
- [ ] WebSocket support for real-time progress updates

### Performance Optimization
- [ ] Redis caching layer
- [ ] Keyframe lazy loading
- [ ] Database query optimization
- [ ] Video streaming processing

### Production Deployment
- [ ] Nginx reverse proxy
- [ ] HTTPS configuration
- [ ] Monitoring and logging system (Prometheus + Grafana)
- [ ] Automatic backup strategy
- [ ] CI/CD pipeline

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## Version History

- **V1.0.0** (2025-01-23): Initial release
  - Dual-track keyframe extraction
  - A/B/C data stream isolation
  - Basic user profile system
  - Qianwen LLM integration
  - RESTful API with Swagger docs

---

**Built with ❤️ by the Oral Health Monitoring Team**
