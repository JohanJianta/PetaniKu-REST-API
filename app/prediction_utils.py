import cv2
import torch
import torch.nn as nn
from torch.nn.functional import softmax
import torchvision
from torchvision import transforms
from PIL import Image
from .leaf_segmentation import LeafSegmentation


class PredictionUtils:
    def __init__(self):
        # Initialize the leaf segmenter
        self.segmenter = LeafSegmentation()

        # Initialize the device (use GPU if available, otherwise use CPU)
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        # Load and define the classification model architecture
        self.classification_model = self._load_model('./saved_model/GoogleNet_StateDict.pth')
        self.data_transform = transforms.Compose([
            transforms.Resize((100, 100)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])

        # Define configurations
        self.confidence_threshold = 0.7
        self.class_indices = {'swap1': 0, 'swap2': 1, 'swap3': 2, 'swap4': 3}
        self.level_map = {'swap1': 1, 'swap2': 2, 'swap3': 3, 'swap4': 4}
        self.thresholds = {'Transplanted': 4, 'Direct Seeded': 3}
        self.age_to_growth_stage = {
            range(0, 4): 'Tillering',
            range(4, 8): 'Panicle Initiation',
            range(8, 12): 'Flowering',
            range(12, 16): 'Grain Filling'
        }
        self.nitrogen_values = {
            'Tillering': {'Dry': 25, 'Wet': 18},
            'Panicle Initiation': {'Dry': 30, 'Wet': 23},
            'Flowering': {'Dry': 20, 'Wet': 13},
            'Grain Filling': {'Dry': 15, 'Wet': 8}
        }
        self.lcc_yield_baseline = {
            'Transplanted': {1: 3.0, 2: 4.0, 3: 5.0, 4: 6.0},
            'Direct Seeded': {1: 4.0, 2: 5.0, 3: 6.0, 4: 6.0}
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

    def _predict_LCC(self, image_file):
        """
        Predict the LCC reading for each image.
        """
        segmented_images = [self.segmenter.segment(file) for file in image_file]

        lcc_readings = []
        for image in segmented_images:
            image_pil = Image.fromarray(image)
            image_tensor = self.data_transform(image_pil).unsqueeze(0).to(self.device)
            with torch.no_grad():
                output = self.classification_model(image_tensor)
                probabilities = softmax(output, dim=1)
                max_prob, predicted_idx = torch.max(probabilities, 1)

            if max_prob.item() < self.confidence_threshold:
                lcc_readings.append('Uncertain')
                continue

            class_name = list(self.class_indices.keys())[predicted_idx.item()]
            lcc_readings.append(class_name)

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
        nitrogen_value = self.nitrogen_values[growth_stage][season]

        if not below_threshold >= (len(levels) - uncertainty) / 2:
            nitrogen_value = 0.5 * nitrogen_value  # Maintenance dose

        return levels, nitrogen_value

    def _calculate_urea(self, nitrogen_required, field_area, fertilizer_content=0.46):
        """
        Calculate the weight of urea required.
        """
        total_nitrogen = nitrogen_required * field_area
        urea_required = total_nitrogen / fertilizer_content
        return urea_required

    def predict_nutrition(self, image_paths, current_season, planting_type, paddy_age, field_area):
        """
        Predict nutrition requirements.
        """
        lcc_readings = self._predict_LCC(image_paths)

        levels, nitrogen = self._calculate_nitrogen(current_season, planting_type, paddy_age, lcc_readings)
        if not levels or not nitrogen:
            raise ValueError('Gambar harus berupa daun padi')

        urea_required = self._calculate_urea(nitrogen, field_area)
        return levels, urea_required

    def predict_yield(self, field_area, lcc_levels, planting_type='Direct Seeded'):
        optimal_nitrogen_level = self.thresholds.get(planting_type, 0)
        valid_levels = [level for _, level in lcc_levels if level > 0]
        average_level = round(sum(valid_levels) / len(valid_levels)) if valid_levels else optimal_nitrogen_level

        planting_baseline = self.lcc_yield_baseline.get(planting_type, {})
        max_yield_per_hectare = planting_baseline.get(average_level, 0)
        max_yield = max_yield_per_hectare * field_area

        yield_deduction = sum(
            (max_yield_per_hectare - planting_baseline.get(level, 0)) * area
            for area, level in lcc_levels
            if level > 0 and level != average_level
        )
        current_yield = max_yield - yield_deduction
        return current_yield
