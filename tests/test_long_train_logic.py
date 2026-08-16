import os
import pytest
from run_long_training import update_summary_report, extract_layout_info

def test_extract_layout_info():
    info = extract_layout_info("config/default_layout.json")
    assert info["grid_size"] == "10x10"
    assert info["table_count"] == 5
    assert info["total_capacity"] == 18
    assert info["station_count"] == 4
    assert info["waiter_count"] == 2
    assert info["chef_count"] == 2

def test_summary_report_generation(tmp_path):
    history = [
        {
            "epoch": 1,
            "cumulative_train_days": 50,
            "train_elapsed_sec": 45.2,
            "eval_metrics": {
                "eval_days": 10,
                "total_completed": 3100,
                "total_churned": 450,
                "mean_daily_completed": 310.0,
                "mean_daily_churn": 45.0,
                "mean_queue_wait_time": 8.5,
                "mean_food_cold_time": 42.1,
                "mean_reward_per_day": 2500.0,
                "eval_score": 2500.0
            },
            "is_best": True,
            "status_label": "🏆 YENİ EN İYİ (Skor: +2500.00)"
        }
    ]
    
    update_summary_report(history, "default_layout.json", "config/default_layout.json", 3, 1, 2500.0)
    assert os.path.exists("results/long_train_summary.md")
    assert os.path.exists("results/long_train_history.json")
