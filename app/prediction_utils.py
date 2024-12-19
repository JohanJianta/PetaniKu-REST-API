import torch
import torch.nn as nn
from torch.nn.functional import softmax
import torchvision
from torchvision import transforms
import cv2
import numpy as np
from PIL import Image
from io import BytesIO
from ultralytics import YOLO

class PredictionUtils:
    def __init__(self):
        # Initialize the device (use GPU if available, otherwise use CPU)
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Load and define the classification model architecture
        self.classification_model = self._load_model('./saved_model/GoogleNet_StateDict.pth')
        self.data_transform = transforms.Compose([
            transforms.Resize((100, 100)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])

        # Load the detection model
        self.detection_model = YOLO("./saved_model/YOLO_Rice_Leaf_Detection_V2.torchscript", task='detect')
        
        # Define configurations
        self.confidence_threshold = 0.7
        self.class_indices = {'swap1': 0, 'swap2': 1, 'swap3': 2, 'swap4': 3}
        self.level_map = {'swap1': 1, 'swap2': 2, 'swap3': 3, 'swap4': 4}
        self.thresholds = {'Transplanted': 4, 'Direct Seeded': 3}
        self.age_to_growth_stage = {
            range(0, 1): 'Tillering',
            range(1, 2): 'Panicle Initiation',
            range(2, 3): 'Flowering',
            range(3, 4): 'Grain Filling'
        }
        self.nitrogen_values = {
            'Tillering': {'Dry': {'Transplanted': 30, 'Direct Seeded': 30}, 
                          'Wet': {'Transplanted': 23, 'Direct Seeded': 23}},
            'Panicle Initiation': {'Dry': {'Transplanted': 35, 'Direct Seeded': 35}, 
                                   'Wet': {'Transplanted': 27, 'Direct Seeded': 27}},
            'Flowering': {'Dry': {'Transplanted': 20, 'Direct Seeded': 20}, 
                          'Wet': {'Transplanted': 15, 'Direct Seeded': 15}},
            'Grain Filling': {'Dry': {'Transplanted': 15, 'Direct Seeded': 15}, 
                              'Wet': {'Transplanted': 10, 'Direct Seeded': 10}}
        }

    def _load_model(self, model_path):
        """
        Load the model with predefined architecture.
        """
        model = torchvision.models.densenet121(weights=None)
        model.classifier = nn.Sequential(
            nn.Dropout(0.5, inplace=True),
            nn.Linear(1024, 16, bias=False),
            nn.BatchNorm1d(16),
            nn.ReLU(inplace=True),
            nn.Linear(16, 4)
        )
        model.load_state_dict(torch.load(model_path, weights_only=True))
        return model.to(self.device).eval()

    def _predict_LCC(self, image_files):
        """
        Predict the LCC reading for each image.
        """
        image_inputs = []
        for file in image_files:
            image_pil = Image.open(BytesIO(file.read())).convert('RGB')
            image_np = cv2.cvtColor(np.array(image_pil), cv2.COLOR_RGB2BGR)
            image_inputs.append(image_np)

        leaf_detections = self.detection_model(image_inputs)

        lcc_readings = []
        for index, detection in enumerate(leaf_detections):
            for box in detection.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                confidence = box.conf[0]

                if confidence < self.confidence_threshold:
                    continue

                cropped_leaf = image_inputs[index][y1:y2, x1:x2]
                # cv2.imwrite(f"./app/cropped_img/img-{index}.jpg", cropped_leaf)   # for testing only
                cropped_leaf_pil = Image.fromarray(cv2.cvtColor(cropped_leaf, cv2.COLOR_BGR2RGB))

                image_tensor = self.data_transform(cropped_leaf_pil).unsqueeze(0).to(self.device)
                with torch.no_grad():
                    output = self.classification_model(image_tensor)
                    probabilities = softmax(output, dim=1)
                    max_prob, predicted_idx = torch.max(probabilities, 1)
                    
                if max_prob.item() < self.confidence_threshold:
                    continue
                
                class_name = list(self.class_indices.keys())[predicted_idx.item()]
                lcc_readings.append(class_name)
                break

            if len(lcc_readings) == index:
                lcc_readings.append('Uncertain')

        return lcc_readings

    def _get_growth_stage(self, paddy_age):
        """
        Determine the growth stage based on paddy age (months).
        """
        for age_range, stage in self.age_to_growth_stage.items():
            if paddy_age in age_range:
                return stage
        return 'Grain Filling'  # Default stage for ages beyond 4th month

    def _calculate_nitrogen(self, season, planting_type, paddy_age, lcc_readings):
        """
        Calculate the amount of nitrogen required.
        """
        growth_stage = self._get_growth_stage(paddy_age)
        threshold = self.thresholds[planting_type]
        
        levels = [self.level_map.get(reading, 0) for reading in lcc_readings]  # Default 0 for 'Uncertain'

        uncertainty = sum(level == 0 for level in levels)
        if uncertainty >= len(levels) / 2:
            return None, None
        
        below_threshold = sum(level < threshold for level in levels)
        nitrogen_value = self.nitrogen_values[growth_stage][season][planting_type]

        if not below_threshold >= (len(levels) - uncertainty) / 2:
            nitrogen_value = 0.5 * nitrogen_value  # Maintenance dose
        
        return levels, nitrogen_value

    def _calculate_fertilizer(self, nitrogen_required, area, fertilizer_content=0.46, sack_weight=50):
        """
        Calculate the amount of urea and fertilizer sacks required.
        """
        total_nitrogen = nitrogen_required * area
        urea_required = total_nitrogen / fertilizer_content
        num_sacks = urea_required / sack_weight
        return urea_required, num_sacks

    def predict_nutrition(self, image_paths, current_season, planting_type, paddy_age, field_area):
        """
        Predict nutrition requirements.
        """
        lcc_readings = self._predict_LCC(image_paths)

        levels, nitrogen = self._calculate_nitrogen(current_season, planting_type, paddy_age, lcc_readings)
        if not levels or not nitrogen:
            raise ValueError('Gambar harus berupa daun padi')
        
        urea, sacks = self._calculate_fertilizer(nitrogen, field_area)
        return levels, nitrogen, urea, sacks

    def predict_yields(self, field_area):
        """
        Predict rice yields.
        """
        # Placeholder for yield prediction logic
        return 6
