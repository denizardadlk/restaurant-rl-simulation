import pandas as pd
import numpy as np
import os
import pickle
from typing import Tuple, Optional
try:
    import lightgbm as lgb
except ImportError:
    # Fallback if lightgbm is not installed
    lgb = None
    from sklearn.ensemble import HistGradientBoostingRegressor

DEFAULT_MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "ml_cook_time_model.pkl")

class CookTimePredictor:
    def __init__(self, auto_load: bool = True, model_path: Optional[str] = None):
        self.model = None
        self.is_trained = False
        self.training_count = 0
        self.feature_columns = []
        self.model_path = model_path or DEFAULT_MODEL_PATH
        
        if lgb is not None:
            self.model = lgb.LGBMRegressor(
                n_estimators=50,
                learning_rate=0.08,
                min_child_samples=5,
                random_state=42,
                verbosity=-1,
                force_col_wise=True
            )
        else:
            self.model = HistGradientBoostingRegressor(max_iter=50, random_state=42)

        if auto_load and os.path.exists(self.model_path):
            self.load(self.model_path)

    def _preprocess(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Optional[pd.Series]]:
        # Convert categorical to dummy variables
        df_encoded = pd.get_dummies(df, columns=["dish_type", "station_type"])
        
        X = df_encoded.drop("actual_cook_time", axis=1) if "actual_cook_time" in df_encoded else df_encoded
        y = df_encoded["actual_cook_time"] if "actual_cook_time" in df_encoded else None
        
        # Keep track of columns used during training
        if not self.is_trained and y is not None:
            self.feature_columns = X.columns.tolist()
            
        # If predicting, ensure X has exactly the same columns as training
        if self.is_trained:
            for col in self.feature_columns:
                if col not in X.columns:
                    X[col] = 0
            X = X[self.feature_columns]
            
        return X, y

    def train(self, data: pd.DataFrame, auto_save: bool = True):
        if len(data) < 10:
            return  # Too little data
            
        X, y = self._preprocess(data)
        self.model.fit(X, y)
        self.is_trained = True
        self.training_count += len(data)

        if auto_save:
            self.save(self.model_path)

    def save(self, path: Optional[str] = None):
        """Saves the trained model and feature definitions to disk."""
        target_path = path or self.model_path
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        save_data = {
            "model": self.model,
            "is_trained": self.is_trained,
            "training_count": self.training_count,
            "feature_columns": self.feature_columns
        }
        with open(target_path, "wb") as f:
            pickle.dump(save_data, f)

    def load(self, path: Optional[str] = None) -> bool:
        """Loads a pre-trained model from disk."""
        target_path = path or self.model_path
        if not os.path.exists(target_path):
            return False
        try:
            with open(target_path, "rb") as f:
                save_data = pickle.load(f)
                self.model = save_data["model"]
                self.is_trained = save_data["is_trained"]
                self.training_count = save_data.get("training_count", 0)
                self.feature_columns = save_data.get("feature_columns", [])
            return True
        except Exception as e:
            print(f"[WARN] Failed to load ML model from {target_path}: {e}")
            return False

    def predict(self, features: dict, total_orders_so_far: int) -> float:
        """
        Predicts the cook time for a new order.
        Features must be recorded AT kitchen_start.
        """
        theoretical_time = features.get("theoretical_time", 15.0)
        
        # Cold start logic: if model is already trained and loaded from disk, use prediction immediately
        if not self.is_trained or (total_orders_so_far < 20 and self.training_count == 0):
            return theoretical_time
            
        df = pd.DataFrame([features])
        X, _ = self._preprocess(df)
        
        ml_prediction = float(self.model.predict(X)[0])
        
        # Blending during warmup only if newly training from scratch
        if self.training_count < 100 and total_orders_so_far < 100:
            alpha = (100 - total_orders_so_far) / 80.0
            return max(1.0, alpha * theoretical_time + (1 - alpha) * ml_prediction)
            
        return max(1.0, ml_prediction)

    def predict_with_uncertainty(self, features: dict, total_orders_so_far: int) -> tuple[float, float]:
        """
        Returns (predicted_time, uncertainty_std_dev)
        """
        predicted = self.predict(features, total_orders_so_far)
        theoretical = features.get("theoretical_time", 15.0)
        
        if not self.is_trained or (total_orders_so_far < 20 and self.training_count == 0):
            return predicted, theoretical * 0.2
            
        diff = abs(predicted - theoretical)
        uncertainty = (predicted * 0.1) + (diff * 0.5)
        
        return predicted, uncertainty
