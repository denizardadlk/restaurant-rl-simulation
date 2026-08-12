import os
try:
    from stable_baselines3 import PPO
    from stable_baselines3.common.env_checker import check_env
except ImportError:
    PPO = None
    check_env = None

from .gym_env import RestaurantGymEnv

class OrderSchedulerRLAgent:
    def __init__(self, env: RestaurantGymEnv):
        self.env = env
        self.model = None

    def train(self, total_timesteps: int = 10000):
        if PPO is None:
            print("Stable-Baselines3 is not installed. Cannot train RL Agent.")
            return
            
        print(f"Training PPO Agent for {total_timesteps} timesteps...")
        self.model = PPO("MlpPolicy", self.env, verbose=0)
        self.model.learn(total_timesteps=total_timesteps)
        print("Training complete.")

    def evaluate(self, n_episodes: int = 1) -> dict:
        if self.model is None:
            return {}
            
        total_rewards = 0.0
        total_completed = 0
        total_churned = 0
        
        for _ in range(n_episodes):
            obs, info = self.env.reset()
            done = False
            episode_reward = 0.0
            
            while not done:
                action, _states = self.model.predict(obs, deterministic=True)
                obs, reward, terminated, truncated, info = self.env.step(action)
                episode_reward += reward
                done = terminated or truncated
                
            total_rewards += episode_reward
            total_completed += info["completed"]
            total_churned += info["churned"]
            
        return {
            "mean_reward": total_rewards / n_episodes,
            "mean_completed": total_completed / n_episodes,
            "mean_churned": total_churned / n_episodes
        }
