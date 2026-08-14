import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import numpy as np

def get_expert_action(env):
    """
    Acts as an LPT expert (Longest Processing Time) and translates the decision 
    into the discrete action integer used by the RL environment.
    """
    engine = env.unwrapped.engine
    if len(engine.order_queue) == 0:
        return 0
        
    # RL action space only sees up to env.max_queue_size orders
    visible_queue = engine.order_queue[:env.unwrapped.max_queue_size]
    
    # Sort indices of visible queue by theoretical_time descending (LPT)
    queue = list(enumerate(visible_queue))
    queue.sort(key=lambda x: x[1].theoretical_time if hasattr(x[1], 'theoretical_time') else x[1].stages[x[1].current_stage_idx]["time"], reverse=True)
    
    station_ids = list(engine.grid.stations.keys())
    num_stations = len(station_ids)
    
    for i, order in queue:
        req_station = order.stages[order.current_stage_idx]["station_type"]
        for j, s_id in enumerate(station_ids):
            station = engine.grid.stations[s_id]
            if station.type == req_station and not station.is_full and not getattr(station, 'is_broken', False):
                # Found a valid station! Now check if there is a free chef
                chef_available = False
                for chef in engine.grid.chefs.values():
                    if not chef.is_full:
                        chef_available = True
                        break
                        
                if chef_available:
                    # Return the RL integer action for this assignment
                    return 1 + (i * num_stations) + j
                    
    return 0 # No-Op if nothing can be assigned

def collect_expert_data(env, expert_func, num_episodes=50):
    """
    Collects state-action pairs from the environment using an expert function.
    """
    states = []
    actions = []
    
    for i in range(num_episodes):
        obs, _ = env.reset(seed=42 + i, options={"difficulty_level": 1})
        done = False
        while not done:
            action = expert_func(env)
            # Only record if the expert actually took an action (not a No-Op, unless queue is empty)
            if action > 0 or len(env.unwrapped.engine.order_queue) == 0:
                states.append(obs)
                actions.append(action)
            
            obs, reward, terminated, truncated, _ = env.step(action)
            done = terminated or truncated
            
    return np.array(states), np.array(actions)

def train_bc_policy(model, states, actions, epochs=10, batch_size=64, learning_rate=1e-3):
    """
    Fine-tunes the Stable Baselines 3 model policy using Behavior Cloning (Supervised Learning).
    """
    device = model.device
    policy = model.policy
    
    tensor_states = torch.tensor(states, dtype=torch.float32).to(device)
    tensor_actions = torch.tensor(actions, dtype=torch.long).to(device)
    
    dataset = TensorDataset(tensor_states, tensor_actions)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    
    optimizer = optim.Adam(policy.parameters(), lr=learning_rate)
    criterion = nn.CrossEntropyLoss()
    
    policy.train()
    print(f"Starting Behavior Cloning for {epochs} epochs...")
    for epoch in range(epochs):
        total_loss = 0.0
        for batch_states, batch_actions in dataloader:
            optimizer.zero_grad()
            
            # Forward pass through SB3 policy
            # get_distribution returns a Categorical distribution for discrete actions
            dist = policy.get_distribution(batch_states)
            logits = dist.distribution.logits
            
            loss = criterion(logits, batch_actions)
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            
        print(f"BC Epoch {epoch+1}/{epochs} - Loss: {total_loss/len(dataloader):.4f}")
    
    print("Behavior Cloning complete!")
