#!/usr/bin/env python3
"""
Test script for smart panning vision module.
Run this inside the Docker container or with Python 3.12 + dependencies.

Usage:
    python test_vision.py <video_path> <aspect_ratio> [start] [end]

Example:
    python test_vision.py ./data/raw/abc123/video.mp4 9:16 0 30
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.services.vision import calculate_crop


def main():
    if len(sys.argv) < 3:
        print("Usage: python test_vision.py <video_path> <aspect_ratio> [start] [end]")
        print("Example: python test_vision.py video.mp4 9:16 0 30")
        sys.exit(1)
    
    video_path = Path(sys.argv[1])
    aspect_ratio = sys.argv[2]
    start = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
    end = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
    
    if not video_path.exists():
        print(f"Error: Video file not found: {video_path}")
        sys.exit(1)
    
    print(f"Testing vision.calculate_crop()...")
    print(f"  Video: {video_path}")
    print(f"  Aspect Ratio: {aspect_ratio}")
    print(f"  Time Range: {start}s - {end}s" if end > 0 else f"  Time Range: {start}s - end")
    print()
    
    try:
        target_w, target_h, crop_x, crop_y = calculate_crop(
            video_path=video_path,
            aspect_ratio=aspect_ratio,
            start=start,
            end=end
        )
        
        print("✓ Analysis Complete!")
        print(f"  Target Dimensions: {target_w}x{target_h}")
        print(f"  Crop Offset: ({crop_x}, {crop_y})")
        print()
        print("Smart panning is ready to use with these crop settings.")
        
    except Exception as e:
        print(f"✗ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
