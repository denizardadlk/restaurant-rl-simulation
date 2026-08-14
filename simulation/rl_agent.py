import os
import numpy as np
try:
    from stable_baselines3.common.env_checker import check_env
    from sb3_contrib import MaskablePPO
    from sb3_contrib.common.wrappers import ActionMasker
except ImportError:
    check_env = None
    MaskablePPO = None
    ActionMasker = None

from .gym_env import RestaurantGymEnv
from .behavior_cloning import collect_expert_data, train_bc_policy, get_expert_action

def mask_fn(env: RestaurantGymEnv) -> np.ndarray:
    return env.action_masks()

class OrderSchedulerRLAgent:
    def __init__(self, env: RestaurantGymEnv, model_path: str = "models/ppo_order_scheduler.zip"):
        if ActionMasker is not None:
            self.env = ActionMasker(env, mask_fn)
        else:
            self.env = env
        self.model = None
        self.model_path = model_path
        
        # Ensure models directory exists
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)

    def train(self, total_timesteps: int = 10000):
        if MaskablePPO is None:
            print("sb3-contrib is not installed. Cannot train RL Agent.", flush=True)
            return
            
        print(f"Training MaskablePPO Agent for {total_timesteps} timesteps...", flush=True)
        if self.model is None:
            self.model = MaskablePPO("MlpPolicy", self.env, verbose=1, n_steps=512, batch_size=64)
            self.model.learn(total_timesteps=total_timesteps)
        else:
            self.model.set_env(self.env)
            self.model.learn(total_timesteps=total_timesteps, reset_num_timesteps=False)
            
        self.model.save(self.model_path)
        print(f"Training complete. Model saved to {self.model_path}", flush=True)

    def train_curriculum(self, timesteps_per_phase: dict = None):
        if MaskablePPO is None:
            print("sb3-contrib is not installed. Cannot train RL Agent.")
            return
            
        if timesteps_per_phase is None:
            timesteps_per_phase = {1: 50000, 2: 100000, 3: 150000}
            
        print("\n--- Phase 0: Behavior Cloning Pre-training (LPT/MinPatience Warmstart) ---")
        # 1. Collect dataset from Difficulty Level 1 using Expert wrapper
        states, actions = collect_expert_data(self.env, get_expert_action, num_episodes=20)
        
        # Initialize model architecture
        self.model = MaskablePPO("MlpPolicy", self.env, verbose=0)
        
        # 2. Supervised Fine-Tuning
        train_bc_policy(self.model, states, actions, epochs=1, batch_size=128)
        
        for phase in [1, 2, 3]:
            print(f"\n--- Phase {phase}: Curriculum Training (Difficulty Level {phase}) ---")
            self.env.reset(options={"difficulty_level": phase})
            self.model.set_env(self.env)
            self.model.learn(total_timesteps=timesteps_per_phase[phase], reset_num_timesteps=False)
            
        self.model.save(self.model_path)
        print(f"Curriculum Training complete. Model saved to {self.model_path}")

    def load(self):
        if MaskablePPO is None:
            return False
        if os.path.exists(self.model_path):
            try:
                self.model = MaskablePPO.load(self.model_path, env=self.env)
                return True
            except Exception as e:
                print(f"[WARN] Kayıtlı model bu layout veya observation boyutuyla uyumlu değil: {e}")
                return False
        return False

    def evaluate(self, n_episodes: int = 1) -> dict:
        if self.model is None:
            return {}
            
        total_rewards = 0.0
        total_completed = 0
        total_churned = 0
        
        for i in range(n_episodes):
            obs, info = self.env.reset(seed=42 + i)
            done = False
            episode_reward = 0.0
            
            while not done:
                # Provide action masks during prediction
                action_masks = self.env.action_masks()
                action, _states = self.model.predict(obs, action_masks=action_masks, deterministic=True)
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
