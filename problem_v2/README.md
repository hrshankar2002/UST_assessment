# 3D Road Scene Simulation
## Project Overview

This project implements a complete pipeline that transforms fixed dash cam driving footages into an interactive 3D road scene simulation. 
It processes vehicle detection, lane segmentation, and drivable area data from dashcam footage to create a real-time 3D visualization of 
traffic scenarios.

## 🚗 What This Project Does

1. **Processes YOLOPv2 Output**: Takes multi-task learning results (vehicle detection, lane segmentation, drivable area detection)
2. **Extracts Scene Data**: Parses YOLO bounding boxes, lane line coordinates, and road boundaries
3. **Generates 3D Scene**: Creates an interactive 3D simulation using WebGL/Three.js
4. **Provides Playback Controls**: Allows users to replay, pause, and scrub through the driving scenario

## 📁 Project Structure

```
problem_v2/
├── README.md                          # This comprehensive guide
├── YOLOPv2/                          # YOLOPv2 implementation
│   ├── demo.py                       # Custom Tweaked main inference script
│   ├── requirements.txt              # Python dependencies
│   ├── utils/                        # Utility functions
│   └── data/weights                  # YOLO weights 
├── export/                           # YOLOPv2 generated outputs
│   ├── labels/                       # Vehicle detection files (15,720 files)
│   │   ├── input_1000.txt           # YOLO format: class_id x y w h
│   │   └── input_*.txt              # One file per frame
│   ├── lane/                         # Lane segmentation masks (1,321 files)
│   │   └── frame*.png               # Binary masks for lane lines
│   └── drivable/                     # Drivable area masks (1,321 files)
│       └── frame*.png               # Binary masks for road surface
├── Scripts/                          # Data processing pipeline
│   └── DataParser.py                # Main data parser 
├── WebGL/                            # Web-based 3D visualization
│   ├── index.html                   # Web interface with controls
│   ├── scene3d_fixed.js            # Three.js 3D scene implementation
│   └── unity_scene_data.json       # Processed scene data
└── data/                            # Original input video
    └── input.MP4                    # Source dashcam footage
```

## 📊 Data Processing Pipeline

### Input Data Sources

1. **Vehicle Detection Labels** (`export/labels/`)
   - Format: YOLO format text files
   - Content: `class_id center_x center_y width height`
   - Volume: 15,720 detection files
   - Normalized coordinates (0-1 range)

2. **Lane Segmentation Masks** (`export/lane/`)
   - Format: Binary PNG images
   - Content: White pixels indicate lane markings
   - Volume: 1,321 frame masks
   - Resolution: 1280x720 pixels

3. **Drivable Area Masks** (`export/drivable/`)
   - Format: Binary PNG images  
   - Content: White pixels indicate road surface
   - Volume: 1,321 frame masks
   - Resolution: 1280x720 pixels

### Processing Steps

1. **Data Parsing** (`Scripts/DataParser.py`)
   - Extracts vehicle bounding boxes from YOLO files
   - Processes lane masks using OpenCV contour detection
   - Generates road boundaries from drivable area masks
   - Converts 2D pixel coordinates to 3D world coordinates

2. **Coordinate Transformation**
   - Normalizes pixel coordinates to world space
   - Maps 2D image coordinates to 3D scene positions
   - Maintains proportional scaling for realistic visualization

3. **Data Serialization**
   - Exports processed data to JSON format
   - Ensures cross-platform compatibility
   - Optimizes for real-time rendering

### Output Format

```json
{
  "frames": {
    "frame_number": {
      "vehicles": [
        {
          "class_id": 3,
          "center_x": 0.245312,
          "center_y": 0.4,
          "width": 0.065625,
          "height": 0.0555556,
          "bbox": {
            "x1": 0.2124995,
            "y1": 0.3722222,
            "x2": 0.2781245,
            "y2": 0.42777780000000004
          }
        }
      ],
      "lane_lines": [
        [[1221, 405], [1220, 410], ...]
      ],
      "drivable_area": [
        [100, 300], [150, 300], ...
      ],
      "timestamp": 54.233333
    }
  },
  "metadata": {
    "total_frames": 1321,
    "fps": 30,
    "image_width": 1280,
    "image_height": 720
  }
}
```

## 🎮 3D Visualization Features

### WebGL Implementation

**Technology Stack:**
- Three.js for 3D rendering
- WebGL for hardware acceleration
- HTML5 Canvas for rendering surface

**Key Features:**
- Real-time 3D scene rendering
- Dynamic vehicle tracking and movement
- Procedural road surface generation
- Interactive camera controls
- Timeline scrubbing and playback controls

**Scene Components**

- Vehicles
- Lane Lines
- Road Surface
- Environment

### Interactive Controls

**Playback Controls:**
- Play/Pause/Restart buttons
- Variable speed control (0.1x - 3.0x)
- Timeline scrubber for precise navigation

**Display Options:**
- Toggle lane line visibility
- Toggle road surface display
- Real-time frame information
- Vehicle count display

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.7+ (for data processing)
- Modern web browser with WebGL support
- Local web server capability

### Step 1: Data Processing

1. **Install Dependencies**
   ```bash
   cd YOLOPv2/
   pip install -r requirements.txt
   ```

2. **Run YOLOPv2 Inference**
   ```bash
    cd YOLOPv2
    python demo.py \
      --weights data/weights/yolopv2.pt \
      --source ../data/input.MP4 \
      --img-size 640 \
      --conf-thres 0.3 \
      --iou-thres 0.45 \
      --save-txt \
      --project ../export \
      --name yolopv2_run \
      --exist-ok
   ```
3. **Process Data for 3D**
   ```bash
   cd ../Scripts
   python DataParser.py
   ```

   ### Step 2: WebGL

1. **Start Local Server**
   ```bash
   cd ../WebGL
   python -m http.server 8000
   ```

2. **Open Browser**
   - Navigate to `http://localhost:8000`
   - The simulation loads automatically
   - Use on-screen controls for interaction

