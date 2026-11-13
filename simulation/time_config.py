import os
import json
from typing import Dict, Any, List, Optional

DEFAULT_TIME_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "time_config.json")

DEFAULT_TIME_CONFIG_DICT: Dict[str, Any] = {
    "customer_patience": {
        "waiting_order_initial": 20.0,
        "waiting_food_initial": 30.0,
        "decay_rate_per_tick": 1.0
    },
    "eating_duration": {
        "base_time": 20.0,
        "extra_time_per_two_seats": 7.0,
        "std_dev_ratio": 0.15,
        "min_time": 5.0
    },
    "staff_durations_and_speeds": {
        "walking_speed_meters_per_minute": 30.0,
        "waiter": {
            "default_speed": 1.0,
            "default_capacity": 4,
            "order_taking_duration": 1.0,
            "table_service_duration": 1.0,
            "table_cleaning_duration": 2.0,
            "food_cooling_grace_period": 5.0
        },
        "chef": {
            "default_speed": 1.0,
            "default_capacity": 8,
            "carrying_capacity": 2,
            "default_efficiency": 1.0,
            "station_prep_duration": 1.0,
            "plating_and_counter_drop_duration": 1.0,
            "stage_transfer_duration": 1.0
        }
    },
    "cooking_mechanics": {
        "gamma_distribution_alpha": 25.0,
        "station_load_penalty_factor": 0.02,
        "default_station_batch_factor": 0.95,
        "batch_yields": {
            "Patates": 4,
            "Sogan_Halkasi": 7,
            "Fried_Basket": {
                "Patates": 2,
                "Sogan_Halkasi": 3
            },
            "Doner": 1
        }
    },
    "menu_categories": {
        "main_dishes": ["Burger", "Doner", "Sucuk", "Kofte", "Toast"],
        "appetizers": ["Patates", "Sogan_Halkasi", "Fried_Basket"],
        "beverages": ["Kola", "Ayran", "Su", "Salgam"]
    },
    "order_probabilities": {
        "main_dish": {
            "first_prob": 1.0,
            "second_prob": 0.20
        },
        "appetizer": {
            "first_prob": 0.40,
            "second_prob": 0.20
        },
        "beverage": {
            "first_prob": 0.95,
            "second_prob": 0.40
        }
    },
    "menu_recipes": {
        "Burger": {
            "category": "main_dish",
            "stages": [
                {"station_type": "GRILL", "time": 10.0},
                {"station_type": "PREP", "time": 2.0}
            ]
        },
        "Doner": {
            "category": "main_dish",
            "stages": [
                {"station_type": "DONER", "time": 1.0},
                {"station_type": "PREP", "time": 1.0}
            ]
        },
        "Sucuk": {
            "category": "main_dish",
            "stages": [
                {"station_type": "GRILL", "time": 4.0},
                {"station_type": "PREP", "time": 1.0}
            ]
        },
        "Kofte": {
            "category": "main_dish",
            "stages": [
                {"station_type": "GRILL", "time": 10.0},
                {"station_type": "PREP", "time": 1.0}
            ]
        },
        "Toast": {
            "category": "main_dish",
            "stages": [
                {"station_type": "TOASTER", "time": 7.0}
            ]
        },
        "Patates": {
            "category": "appetizer",
            "stages": [
                {"station_type": "FRYER", "time": 5.0}
            ]
        },
        "Sogan_Halkasi": {
            "category": "appetizer",
            "stages": [
                {"station_type": "FRYER", "time": 5.0}
            ]
        },
        "Fried_Basket": {
            "category": "appetizer",
            "stages": [
                {"station_type": "FRYER", "time": 5.0}
            ]
        },
        "Kola": {
            "category": "beverage",
            "stages": []
        },
        "Ayran": {
            "category": "beverage",
            "stages": []
        },
        "Su": {
            "category": "beverage",
            "stages": []
        },
        "Salgam": {
            "category": "beverage",
            "stages": []
        }
    },
    "arrival_schedule": {
        "open_hour_tick": 540,
        "close_hour_tick": 1320,
        "intervals": [
            {"start_tick": 540, "end_tick": 660, "interval_minutes": 30.0, "description": "09:00 - 11:00 (30 dk'da bir)"},
            {"start_tick": 660, "end_tick": 720, "interval_minutes": 20.0, "description": "11:00 - 12:00 (20 dk'da bir)"},
            {"start_tick": 720, "end_tick": 840, "interval_minutes": 5.0, "description": "12:00 - 14:00 (5 dk'da bir - Öğle Piki)"},
            {"start_tick": 840, "end_tick": 960, "interval_minutes": 20.0, "description": "14:00 - 16:00 (20 dk'da bir)"},
            {"start_tick": 960, "end_tick": 1200, "interval_minutes": 15.0, "description": "16:00 - 20:00 (15 dk'da bir)"},
            {"start_tick": 1200, "end_tick": 1320, "interval_minutes": 10.0, "description": "20:00 - 22:00 (10 dk'da bir - Akşam Piki)"}
        ]
    },
    "takeout": {
        "peak_probability": 0.06,
        "normal_probability": 0.03,
        "courier_eta_min": 15.0,
        "courier_eta_max": 30.0
    }
}

class TimeConfig:
    """
    Centralized Time & Mechanics Configuration.
    Allows inspecting and modifying customer patience, cook times, waiter speeds,
    chef efficiency, arrival schedules, takeout rates, and batch yield rules from a single file.
    """
    def __init__(self, data: Optional[Dict[str, Any]] = None, config_path: Optional[str] = None):
        self.config_path = config_path or DEFAULT_TIME_CONFIG_PATH
        self.raw_data: Dict[str, Any] = data or {}
        if not self.raw_data and os.path.exists(self.config_path):
            self.reload()
        elif not self.raw_data:
            self.raw_data = json.loads(json.dumps(DEFAULT_TIME_CONFIG_DICT))

    def reload(self):
        """Reloads the configuration from the JSON file on disk."""
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                # Merge with default fallback dictionary to avoid missing keys
                merged = json.loads(json.dumps(DEFAULT_TIME_CONFIG_DICT))
                self._deep_update(merged, loaded)
                self.raw_data = merged
        else:
            self.raw_data = json.loads(json.dumps(DEFAULT_TIME_CONFIG_DICT))

    def save(self, target_path: Optional[str] = None):
        """Saves current configuration to JSON file."""
        save_path = target_path or self.config_path
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(self.raw_data, f, indent=2, ensure_ascii=False)

    def _deep_update(self, base_dict: dict, update_dict: dict):
        for k, v in update_dict.items():
            if k == "menu_recipes":
                base_dict[k] = v
            elif isinstance(v, dict) and k in base_dict and isinstance(base_dict[k], dict):
                self._deep_update(base_dict[k], v)
            else:
                base_dict[k] = v

    # --- Convenience Property Accessors ---

    @property
    def customer_patience(self) -> Dict[str, float]:
        return self.raw_data.get("customer_patience", DEFAULT_TIME_CONFIG_DICT["customer_patience"])

    @property
    def eating_duration(self) -> Dict[str, Any]:
        return self.raw_data.get("eating_duration", DEFAULT_TIME_CONFIG_DICT["eating_duration"])

    @property
    def walking_speed(self) -> float:
        return float(self.raw_data.get("staff_durations_and_speeds", {}).get("walking_speed_meters_per_minute", 30.0))

    @property
    def waiter_config(self) -> Dict[str, Any]:
        return self.raw_data.get("staff_durations_and_speeds", {}).get("waiter", DEFAULT_TIME_CONFIG_DICT["staff_durations_and_speeds"]["waiter"])

    @property
    def chef_config(self) -> Dict[str, Any]:
        return self.raw_data.get("staff_durations_and_speeds", {}).get("chef", DEFAULT_TIME_CONFIG_DICT["staff_durations_and_speeds"]["chef"])

    @property
    def cooking_mechanics(self) -> Dict[str, Any]:
        return self.raw_data.get("cooking_mechanics", DEFAULT_TIME_CONFIG_DICT["cooking_mechanics"])

    @property
    def menu_recipes(self) -> Dict[str, Any]:
        return self.raw_data.get("menu_recipes", DEFAULT_TIME_CONFIG_DICT["menu_recipes"])

    @property
    def arrival_schedule(self) -> Dict[str, Any]:
        return self.raw_data.get("arrival_schedule", DEFAULT_TIME_CONFIG_DICT["arrival_schedule"])

    @property
    def menu_categories(self) -> Dict[str, List[str]]:
        return self.raw_data.get("menu_categories", DEFAULT_TIME_CONFIG_DICT.get("menu_categories", {}))

    @property
    def order_probabilities(self) -> Dict[str, Any]:
        return self.raw_data.get("order_probabilities", DEFAULT_TIME_CONFIG_DICT.get("order_probabilities", {}))

    @property
    def takeout(self) -> Dict[str, Any]:
        return self.raw_data.get("takeout", DEFAULT_TIME_CONFIG_DICT["takeout"])

_GLOBAL_TIME_CONFIG: Optional[TimeConfig] = None

def load_time_config(config_path: Optional[str] = None) -> TimeConfig:
    """Loads and returns a TimeConfig instance for the specified path."""
    return TimeConfig(config_path=config_path)

def get_time_config() -> TimeConfig:
    """Returns the cached global TimeConfig instance, loading it if not yet loaded."""
    global _GLOBAL_TIME_CONFIG
    if _GLOBAL_TIME_CONFIG is None:
        _GLOBAL_TIME_CONFIG = TimeConfig()
    return _GLOBAL_TIME_CONFIG
