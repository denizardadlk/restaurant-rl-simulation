import unittest
import os
from simulation.gym_env import RestaurantGymEnv
try:
    from stable_baselines3.common.env_checker import check_env
except ImportError:
    check_env = None

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "default_layout.json")

class TestGymEnv(unittest.TestCase):
    def test_gym_env_compliance(self):
        env = RestaurantGymEnv(CONFIG_PATH)
        if check_env is not None:
            # check_env runs assertions, throws exception if env is invalid
            check_env(env, warn=True)
        else:
            self.skipTest("stable-baselines3 not installed")

    def test_gym_env_reset_and_step(self):
        env = RestaurantGymEnv(CONFIG_PATH)
        obs, info = env.reset()
        
        self.assertIsNotNone(obs)
        self.assertEqual(len(obs), env.observation_space.shape[0])
        self.assertIn("tick", info)
        
        # Take a random valid action
        action = env.action_space.sample()
        next_obs, reward, terminated, truncated, next_info = env.step(action)
        
        self.assertEqual(len(next_obs), env.observation_space.shape[0])
        self.assertIsInstance(reward, float)
        self.assertIsInstance(terminated, bool)
        self.assertIsInstance(truncated, bool)

if __name__ == "__main__":
    unittest.main()
