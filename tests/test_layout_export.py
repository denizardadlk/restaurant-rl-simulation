import json
import os
import pytest
from simulation.grid import RestaurantGrid
from simulation.engine import SimulationEngine

def test_exported_layout_compatibility(tmp_path):
    # Dummy layout JSON mimicking the output of our layout_editor.js
    layout_data = {
        "grid_size": {"width": 12, "height": 12},
        "kitchen_zone": {"x": 8, "y": 0, "w": 4, "h": 12},
        "tables": [
            {"id": "T1", "x": 1, "y": 1, "capacity": 4},
            {"id": "T2", "x": 1, "y": 5, "capacity": 2}
        ],
        "stations": [
            {"id": "S_OVEN_1", "type": "OVEN", "capacity": 2, "x": 9, "y": 0},
            {"id": "S_GRILL_2", "type": "GRILL", "capacity": 4, "x": 9, "y": 2}
        ],
        "waiters": [
            {"id": "W1", "x": 0, "y": 0, "speed": 1.0}
        ],
        "chefs": [
            {"id": "C1", "x": 8, "y": 0, "capacity": 2, "efficiency": 1.0}
        ]
    }
    
    # Save the dummy layout to a temporary file
    temp_config = tmp_path / "test_layout.json"
    with open(temp_config, "w", encoding="utf-8") as f:
        json.dump(layout_data, f)
        
    # 1. Test Grid Loading
    grid = RestaurantGrid(str(temp_config))
    assert grid.width == 12
    assert grid.height == 12
    assert len(grid.tables) == 2
    assert len(grid.stations) == 2
    assert len(grid.waiters) == 1
    assert len(grid.chefs) == 1
    assert grid.tables["T1"].capacity == 4
    
    # 2. Test SimulationEngine Initialization
    engine = SimulationEngine(str(temp_config))
    engine.reset()
    assert engine.tick == 0
    assert len(engine.grid.stations) == 2
    
    # Run a single step to ensure no immediate crash
    engine.step()
    assert engine.tick == 1
