import pytest
import numpy as np
from simulation.gym_env import RestaurantGymEnv

def test_subtick_multi_assignment():
    env = RestaurantGymEnv(config_path="config/default_layout.json", difficulty_level=3, freeze_ml=True, debug_mode=True)
    obs, info = env.reset(seed=42)
    
    initial_tick = env.engine.tick
    mask = env.action_masks()
    
    valid_actions = np.where(mask[1:] > 0)[0] + 1
    
    if len(valid_actions) > 0:
        # Take a valid assignment
        first_act = int(valid_actions[0])
        obs, reward, term, trunc, info = env.step(first_act)
        
        assert env.debug_stats["actions_valid_assign"] >= 1
        assert env.debug_stats["total_steps"] >= 1
        
    # Take No-Op
    tick_before_noop = env.engine.tick
    obs, reward, term, trunc, info = env.step(0)
    
    # After No-Op, simulation clock MUST have advanced
    assert env.engine.tick >= tick_before_noop
    assert env.debug_stats["actions_noop"] >= 1

def test_debug_stats_tracking():
    env = RestaurantGymEnv(config_path="config/default_layout.json", difficulty_level=1, freeze_ml=True, debug_mode=True)
    env.reset(seed=123)
    
    for _ in range(20):
        mask = env.action_masks()
        valid = np.where(mask > 0)[0]
        act = int(np.random.choice(valid))
        obs, reward, term, trunc, info = env.step(act)
        if term:
            break
            
    stats = env.debug_stats
    assert stats["total_steps"] > 0
    assert "completed_bonus" in stats["reward_breakdown"]
    assert "station_busy_ticks" in stats
