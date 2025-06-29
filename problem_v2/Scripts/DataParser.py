import os
import cv2
import numpy as np
import json
from typing import List, Dict, Tuple
import glob

class YOLODataParser:
    def __init__(self, base_path: str):
        self.base_path = base_path
        self.labels_path = os.path.join(base_path, 'export', 'yolopv2_run', 'labels')
        self.lane_path = os.path.join(base_path, 'export', 'yolopv2_run', 'lane')
        self.drivable_path = os.path.join(base_path, 'export', 'yolopv2_run', 'drivable')
        
    def parse_yolo_labels(self, label_file: str) -> List[Dict]:
        """Parse YOLO format labels: class_id center_x center_y width height"""
        vehicles = []
        
        if not os.path.exists(label_file):
            return vehicles
            
        with open(label_file, 'r') as f:
            lines = f.readlines()
            
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            parts = line.split()
            if len(parts) >= 5:
                class_id = int(parts[0])
                center_x = float(parts[1])
                center_y = float(parts[2])
                width = float(parts[3])
                height = float(parts[4])
                
                vehicles.append({
                    'class_id': class_id,
                    'center_x': center_x,
                    'center_y': center_y,
                    'width': width,
                    'height': height,
                    'bbox': {
                        'x1': center_x - width/2,
                        'y1': center_y - height/2,
                        'x2': center_x + width/2,
                        'y2': center_y + height/2
                    }
                })
        
        return vehicles
    
    def extract_lane_points(self, lane_mask_path: str) -> List[List[Tuple[int, int]]]:
        """Extract lane line points from segmentation mask"""
        if not os.path.exists(lane_mask_path):
            return []
            
        mask = cv2.imread(lane_mask_path, cv2.IMREAD_GRAYSCALE)
        if mask is None:
            return []
        
        # Find contours of lane markings
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        lane_lines = []
        for contour in contours:
            if cv2.contourArea(contour) > 100:  # Filter small noise
                # Simplify contour to key points
                epsilon = 0.02 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                points = [(int(pt[0][0]), int(pt[0][1])) for pt in approx]
                lane_lines.append(points)
        
        return lane_lines
    
    def extract_drivable_area(self, drivable_mask_path: str) -> List[Tuple[int, int]]:
        """Extract drivable area boundary points"""
        if not os.path.exists(drivable_mask_path):
            return []
            
        mask = cv2.imread(drivable_mask_path, cv2.IMREAD_GRAYSCALE)
        if mask is None:
            return []
        
        # Find the largest contour (main drivable area)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return []
        
        # Get the largest contour
        largest_contour = max(contours, key=cv2.contourArea)
        
        # Simplify contour
        epsilon = 0.01 * cv2.arcLength(largest_contour, True)
        approx = cv2.approxPolyDP(largest_contour, epsilon, True)
        
        points = [(int(pt[0][0]), int(pt[0][1])) for pt in approx]
        return points
    
    def get_frame_number(self, filename: str) -> int:
        """Extract frame number from filename"""
        if 'frame' in filename:
            # Extract from frame00001.png format
            num_str = filename.split('frame')[1].split('.')[0]
            return int(num_str)
        elif 'input_' in filename:
            # Extract from input_1000.txt format
            num_str = filename.split('input_')[1].split('.')[0]
            return int(num_str)
        return 0
    
    def process_all_frames(self) -> Dict:
        """Process all frames and return complete dataset"""
        dataset = {
            'frames': {},
            'metadata': {
                'total_frames': 0,
                'fps': 30,  # Assume 30 FPS
                'image_width': 1280,  # Standard dimensions
                'image_height': 720
            }
        }
        
        # Get all label files
        label_files = glob.glob(os.path.join(self.labels_path, '*.txt'))
        
        for label_file in label_files:
            filename = os.path.basename(label_file)
            frame_num = self.get_frame_number(filename)
            
            # Parse vehicles
            vehicles = self.parse_yolo_labels(label_file)
            
            # Get corresponding lane and drivable masks
            lane_mask = os.path.join(self.lane_path, f'frame{frame_num:05d}.png')
            drivable_mask = os.path.join(self.drivable_path, f'frame{frame_num:05d}.png')
            
            lane_lines = self.extract_lane_points(lane_mask)
            drivable_area = self.extract_drivable_area(drivable_mask)
            
            dataset['frames'][frame_num] = {
                'vehicles': vehicles,
                'lane_lines': lane_lines,
                'drivable_area': drivable_area,
                'timestamp': frame_num / 30.0  # Convert to seconds
            }
        
        dataset['metadata']['total_frames'] = len(dataset['frames'])
        return dataset
    
    def save_unity_data(self, output_path: str):
        """Save processed data in Unity-friendly JSON format"""
        dataset = self.process_all_frames()
        
        # Convert numpy types to native Python types for JSON serialization
        def convert_types(obj):
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {key: convert_types(value) for key, value in obj.items()}
            elif isinstance(obj, list):
                return [convert_types(item) for item in obj]
            return obj
        
        dataset = convert_types(dataset)
        
        with open(output_path, 'w') as f:
            json.dump(dataset, f, indent=2)
        
        print(f"Unity data saved to: {output_path}")
        print(f"Total frames processed: {dataset['metadata']['total_frames']}")
        
        # Print sample data for verification
        if dataset['frames']:
            sample_frame = next(iter(dataset['frames'].values()))
            print(f"Sample frame contains:")
            print(f"- {len(sample_frame['vehicles'])} vehicles")
            print(f"- {len(sample_frame['lane_lines'])} lane lines")
            print(f"- Drivable area with {len(sample_frame['drivable_area'])} points")

if __name__ == "__main__":
    parser = YOLODataParser("../")
    parser.save_unity_data("../WebGL/unity_scene_data.json")