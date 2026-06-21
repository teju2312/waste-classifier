"""
classifier/ml_model.py

OOP Concepts used here:
- Singleton Pattern    : WasteClassifier loads all models only once (lazy init, class-level cache)
- Encapsulation        : model loading, preprocessing, gating, prediction all hidden inside the class
- Abstraction          : views only call .predict(image) — no TF/numpy/GCS details exposed
- Single Responsibility: this class ONLY handles ML prediction, nothing else

Pipeline (4 layers, runs in order, stops at first rejection):
    Layer 0 -> Blank/corrupted image check        (pixel std deviation)
    Layer 1 -> ImageNet/MobileNetV2 relevance gate (rejects clearly unrelated objects)
    Layer 2 -> Autoencoder reconstruction gate     (rejects anything not matching trained waste patterns)
    Final   -> Binary Organic vs Recyclable classifier (only runs if all gates passed)
"""

import os
import json
import logging

import numpy as np
import tensorflow as tf
from tensorflow.keras.applications.mobilenet_v2 import (
    preprocess_input,
    decode_predictions,
)

logger = logging.getLogger(__name__)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))      # .../classifier
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)                    # .../waste_classifier
LOCAL_MODELS_DIR = os.path.join(PROJECT_ROOT, 'models')

USE_GCS = os.getenv('USE_GCS', 'False') == 'True'
GCS_BUCKET_NAME = os.getenv('GCS_BUCKET_NAME')
GCP_PROJECT_ID = os.getenv('GCP_PROJECT_ID', 'noted-casing-499709-d9')
# Where downloaded models get cached inside the running container.
GCS_MODEL_CACHE_DIR = '/tmp/models'

MODEL_FILENAMES = [
    'waste_classifier.keras',
    'waste_autoencoder.keras',
    'class_names.json',
]

WASTE_RELEVANT_CLASSES = {
    "banana", "orange", "lemon", "pineapple", "strawberry", "fig",
    "pomegranate", "corn", "cucumber", "zucchini", "broccoli",
    "cauliflower", "mushroom", "artichoke", "bell_pepper", "cabbage",
    "head_cabbage", "custard_apple", "jackfruit", "granny_smith",
    "eggnog", "hotdog", "pizza", "burrito", "guacamole", "potpie",
    "trifle", "ice_cream", "ice_lolly", "french_loaf", "bagel",
    "pretzel", "meat_loaf", "carbonara",
    "water_bottle", "pop_bottle", "wine_bottle", "beer_bottle",
    "beer_glass", "pill_bottle", "plastic_bag", "paper_towel",
    "carton", "cardboard", "envelope", "tin_can", "can_opener",
    "soup_bowl", "milk_can", "ashcan", "trash_can", "wastebin",
    "barrel", "bucket", "crate", "packet", "bottlecap", "Petri_dish",
    "coffee_mug", "cup", "drink_pitcher", "frying_pan", "strainer",
    "paper_plate", "napkin", "rubber_eraser", "sponge", "tray",
}


def _ensure_models_available_locally():
    """
    Returns the local directory path where model files can be loaded from.
    """
    if not USE_GCS:
        return LOCAL_MODELS_DIR

    logger.info("USE_GCS is True - starting model download check...")
    os.makedirs(GCS_MODEL_CACHE_DIR, exist_ok=True)
    logger.info(f"Cache directory ensured: {GCS_MODEL_CACHE_DIR}")

    from google.cloud import storage

    logger.info(f"Creating GCS client for project {GCP_PROJECT_ID}...")
    client = storage.Client(project=GCP_PROJECT_ID)
    logger.info("GCS client created. Getting bucket reference...")
    bucket = client.bucket(GCS_BUCKET_NAME)
    logger.info(f"Bucket reference obtained: {GCS_BUCKET_NAME}")

    for filename in MODEL_FILENAMES:
        local_path = os.path.join(GCS_MODEL_CACHE_DIR, filename)
        if os.path.exists(local_path):
            logger.info(f"{filename} already cached, skipping download.")
            continue

        blob = bucket.blob(f'models/{filename}')
        logger.info(f"Starting download of {filename} from GCS bucket {GCS_BUCKET_NAME}...")
        blob.download_to_filename(local_path)
        logger.info(f"Finished downloading and cached {filename} to {local_path}")

    return GCS_MODEL_CACHE_DIR


class WasteClassifier:
    """
    Singleton class responsible for loading all three models (ImageNet
    gate, autoencoder, binary classifier) and running an uploaded image
    through the full 4-layer pipeline.
    """

    _instance = None

    _imagenet_model = None
    _autoencoder = None
    _classifier = None
    _class_names = None

    IMG_SIZE = (224, 224)
    AE_IMG_SIZE = (96, 96)

    BLANK_STD_THRESHOLD = 10.0
    IMAGENET_CONFIDENCE_THRESHOLD = 0.05
    IMAGENET_TOP_K = 5
    AUTOENCODER_MSE_THRESHOLD = 0.0148

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_models()
        return cls._instance

    def _load_models(self):
        try:
            models_dir = _ensure_models_available_locally()

            # CRITICAL ENVIRONMENT FIX: Map Keras home cache directory to /tmp
            # This forces TensorFlow to store downloaded network weights files in the writable portion
            # of the Cloud Run filesystem if it falls back to internet fetching.
            os.environ['XDG_CACHE_HOME'] = '/tmp'
            os.environ['KERAS_HOME'] = '/tmp/.keras'

            if WasteClassifier._imagenet_model is None:
                logger.info("Loading ImageNet MobileNetV2 (Layer 1 gate)...")
                WasteClassifier._imagenet_model = tf.keras.applications.MobileNetV2(weights='imagenet')

            if WasteClassifier._autoencoder is None:
                ae_path = os.path.join(models_dir, 'waste_autoencoder.keras')
                logger.info(f"Loading autoencoder from {ae_path}...")
                WasteClassifier._autoencoder = tf.keras.models.load_model(ae_path)

            if WasteClassifier._classifier is None:
                clf_path = os.path.join(models_dir, 'waste_classifier.keras')
                logger.info(f"Loading classifier from {clf_path}...")
                WasteClassifier._classifier = tf.keras.models.load_model(clf_path)

            if WasteClassifier._class_names is None:
                names_path = os.path.join(models_dir, 'class_names.json')
                with open(names_path) as f:
                    WasteClassifier._class_names = json.load(f)

            logger.info("All models loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load models: {e}")
            raise RuntimeError(f"Failed to load one or more models: {e}")

    def _pil_to_array(self, image, target_size):
        img = image.convert('RGB').resize(target_size)
        return np.array(img, dtype=np.float32)

    def _check_blank(self, image):
        arr = self._pil_to_array(image, self.IMG_SIZE)
        std_value = float(np.std(arr))
        return std_value >= self.BLANK_STD_THRESHOLD, std_value

    def _check_imagenet_gate(self, image):
        arr = self._pil_to_array(image, (224, 224))
        batch = np.expand_dims(arr, axis=0)
        batch = preprocess_input(batch)

        preds = WasteClassifier._imagenet_model.predict(batch, verbose=0)
        top_preds = decode_predictions(preds, top=self.IMAGENET_TOP_K)[0]

        matched = None
        for _, name, conf in top_preds:
            if name.lower() in WASTE_RELEVANT_CLASSES and conf >= self.IMAGENET_CONFIDENCE_THRESHOLD:
                matched = (name, float(conf))
                break

        return matched is not None, matched

    def _check_autoencoder_gate(self, image):
        arr = self._pil_to_array(image, self.AE_IMG_SIZE) / 255.0
        batch = np.expand_dims(arr, axis=0)

        reconstructed = WasteClassifier._autoencoder.predict(batch, verbose=0)
        mse = float(np.mean(np.square(batch - reconstructed)))

        return mse <= self.AUTOENCODER_MSE_THRESHOLD, mse

    def _classify_final(self, image):
        arr = self._pil_to_array(image, self.IMG_SIZE)
        batch = np.expand_dims(arr, axis=0)
        batch = preprocess_input(batch)

        prob = float(WasteClassifier._classifier.predict(batch, verbose=0)[0][0])
        predicted_idx = 1 if prob >= 0.5 else 0
        label = WasteClassifier._class_names[str(predicted_idx)]
        confidence = prob if predicted_idx == 1 else (1 - prob)

        return label, confidence

    def predict(self, image):
        """
        Runs the image through all four layers and returns a result dict.
        Logs the reason for rejection at each layer to help diagnose
        false-rejection issues in production.
        """
        passed, std_value = self._check_blank(image)
        if not passed:
            logger.info(f"REJECTED at Layer 0 (blank check): std={std_value:.2f}, threshold={self.BLANK_STD_THRESHOLD}")
            return {
                'label': 'Not a valid image',
                'is_organic': False,
                'is_recyclable': False,
                'is_rejected': True,
                'raw_score': round(std_value, 4),
            }

        passed, matched = self._check_imagenet_gate(image)
        if not passed:
            logger.info("REJECTED at Layer 1 (ImageNet gate): no whitelist match found")
            return {
                'label': 'Not a valid image',
                'is_organic': False,
                'is_recyclable': False,
                'is_rejected': True,
                'raw_score': 0.0,
            }
        else:
            logger.info(f"PASSED Layer 1 (ImageNet gate): matched={matched}")

        passed, mse = self._check_autoencoder_gate(image)
        if not passed:
            logger.info(f"REJECTED at Layer 2 (autoencoder gate): mse={mse:.4f}, threshold={self.AUTOENCODER_MSE_THRESHOLD}")
            return {
                'label': 'Not a valid image',
                'is_organic': False,
                'is_recyclable': False,
                'is_rejected': True,
                'raw_score': round(mse, 4),
            }
        else:
            logger.info(f"PASSED Layer 2 (autoencoder gate): mse={mse:.4f}")

        label, confidence = self._classify_final(image)
        label_display = label.capitalize()
        logger.info(f"FINAL PREDICTION: {label_display}, confidence={confidence:.4f}")

        return {
            'label': label_display,
            'is_organic': label == 'organic',
            'is_recyclable': label == 'recyclable',
            'is_rejected': False,
            'raw_score': round(confidence, 4),
        }