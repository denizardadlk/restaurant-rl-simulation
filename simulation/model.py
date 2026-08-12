import pandas as pd
import numpy as np
import os
from typing import Tuple
try:
    import lightgbm as lgb
except ImportError:
    # Fallback if lightgbm is not installed
    lgb = None
    from sklearn.ensemble import HistGradientBoostingRegressor

class CookTimePredictor:
    def __init__(self):
        self.model = None
        self.is_trained = False
        self.training_count = 0
        
        if lgb is not None:
            self.model = lgb.LGBMRegressor(n_estimators=100, learning_rate=0.1, random_state=42)
        else:
            self.model = HistGradientBoostingRegressor(random_state=42)

    def _preprocess(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        # Convert categorical to dummy variables or use label encoding
        # For simplicity, we use one-hot encoding
        df_encoded = pd.get_dummies(df, columns=["dish_type", "station_type"])
        
        # Ensure all expected columns exist even if some categories are missing in a small batch
        expected_cols = [
            "theoretical_time", "station_load_at_start", "kitchen_load_at_start", 
            "chef_efficiency_at_start", "day_tick_at_start"
        ]
        
        X = df_encoded.drop("actual_cook_time", axis=1) if "actual_cook_time" in df_encoded else df_encoded
        y = df_encoded["actual_cook_time"] if "actual_cook_time" in df_encoded else None
        
        # Keep track of columns used during training
        if self.is_trained == False and y is not None:
            self.feature_columns = X.columns.tolist()
            
        # If predicting, ensure X has exactly the same columns as training
        if self.is_trained:
            for col in self.feature_columns:
                if col not in X.columns:
                    X[col] = 0
            X = X[self.feature_columns]
            
        return X, y

    def train(self, data: pd.DataFrame):
        if len(data) < 10:
            return # Too little data
            
        X, y = self._preprocess(data)
        self.model.fit(X, y)
        self.is_trained = True
        self.training_count += len(data)

    def predict(self, features: dict, total_orders_so_far: int) -> float:
        """
        Predicts the cook time for a new order.
        Features must be recorded AT kitchen_start.
        """
        theoretical_time = features.get("theoretical_time", 15.0)
        
        # Cold start logic
        if not self.is_trained or total_orders_so_far < 20:
            return theoretical_time
            
        df = pd.DataFrame([features])
        X, _ = self._preprocess(df)
        
        ml_prediction = float(self.model.predict(X)[0])
        
        # Blending during warmup
        if total_orders_so_far < 100:
            alpha = (100 - total_orders_so_far) / 80.0 # From 1.0 (at 20) to 0.0 (at 100)
            return alpha * theoretical_time + (1 - alpha) * ml_prediction
            
        return ml_prediction
