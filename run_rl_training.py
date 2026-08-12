import os
from simulation.gym_env import RestaurantGymEnv
from simulation.rl_agent import OrderSchedulerRLAgent
from simulation.scheduler_baselines import FIFOScheduler, SPTScheduler

def evaluate_baseline(env: RestaurantGymEnv, scheduler, name: str, n_episodes: int = 2):
    total_rewards = 0.0
    total_completed = 0
    total_churned = 0
    
    for _ in range(n_episodes):
        obs, info = env.reset()
        done = False
        episode_reward = 0.0
        
        while not done:
            sim_actions = scheduler.step()
            env._apply_manual_actions(sim_actions)
            # Advance environment with No-Op (0) since we manually applied actions
            obs, reward, terminated, truncated, info = env.step(0) 
            episode_reward += reward
            done = terminated or truncated
            
        total_rewards += episode_reward
        total_completed += info["completed"]
        total_churned += info["churned"]
        
    res = {
        "name": name,
        "mean_reward": total_rewards / n_episodes,
        "mean_completed": total_completed / n_episodes,
        "mean_churned": total_churned / n_episodes
    }
    print(f"--- Baseline: {name} ---")
    print(f"Mean Reward: {res['mean_reward']:.2f}")
    print(f"Mean Completed Orders: {res['mean_completed']:.2f}")
    print(f"Mean Churned Customers: {res['mean_churned']:.2f}\n")
    return res

def main():
    import sys
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    elif os.path.exists(os.path.join(base_dir, "config", "custom_layout.json")):
        config_path = os.path.join(base_dir, "config", "custom_layout.json")
    else:
        config_path = os.path.join(base_dir, "config", "default_layout.json")

    print(f"Initializing Environment with layout: {config_path}...")
    env = RestaurantGymEnv(config_path)
    
    print("\n==============================================")
    print("1. EVALUATING BASELINES (FIFO & SPT)")
    print("==============================================\n")
    
    fifo_scheduler = FIFOScheduler(env.engine)
    fifo_res = evaluate_baseline(env, fifo_scheduler, "FIFO (First-In-First-Out)", n_episodes=2)
    
    spt_scheduler = SPTScheduler(env.engine)
    spt_res = evaluate_baseline(env, spt_scheduler, "SPT (Shortest Processing Time)", n_episodes=2)
    
    print("\n==============================================")
    print("2. TRAINING RL AGENT (PPO)")
    print("==============================================\n")
    
    rl_agent = OrderSchedulerRLAgent(env)
    rl_agent.train(total_timesteps=20000) 
    
    print("\n==============================================")
    print("3. EVALUATING TRAINED RL AGENT")
    print("==============================================\n")
    
    rl_results = rl_agent.evaluate(n_episodes=2)
    if rl_results:
        print(f"--- RL Agent: PPO ---")
        print(f"Mean Reward: {rl_results['mean_reward']:.2f}")
        print(f"Mean Completed Orders: {rl_results['mean_completed']:.2f}")
        print(f"Mean Churned Customers: {rl_results['mean_churned']:.2f}\n")
        
    print("==============================================")
    print("YENİ SİPARİŞ SİSTEMİ KARŞILAŞTIRMA ÖZETİ")
    print("==============================================")
    print(f"{'Algoritma':<30} | {'Tamamlanan Sipariş':<20} | {'Churned Müşteri':<18} | {'Ödül Skoru':<12}")
    print("-" * 88)
    print(f"{fifo_res['name']:<30} | {fifo_res['mean_completed']:<20.2f} | {fifo_res['mean_churned']:<18.2f} | {fifo_res['mean_reward']:<12.2f}")
    print(f"{spt_res['name']:<30} | {spt_res['mean_completed']:<20.2f} | {spt_res['mean_churned']:<18.2f} | {spt_res['mean_reward']:<12.2f}")
    if rl_results:
        print(f"{'RL Agent (PPO)':<30} | {rl_results['mean_completed']:<20.2f} | {rl_results['mean_churned']:<18.2f} | {rl_results['mean_reward']:<12.2f}")
    print("==============================================\n")

if __name__ == "__main__":
    main()
