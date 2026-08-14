import os
import numpy as np
try:
    from stable_baselines3.common.env_checker import check_env
    from stable_baselines3.common.vec_env import SubprocVecEnv, DummyVecEnv
    from sb3_contrib import MaskablePPO
    from sb3_contrib.common.wrappers import ActionMasker
except ImportError:
    check_env = None
    SubprocVecEnv = None
    DummyVecEnv = None
    MaskablePPO = None
    ActionMasker = None

from .gym_env import RestaurantGymEnv
from .behavior_cloning import collect_expert_data, train_bc_policy, get_expert_action

def mask_fn(env: RestaurantGymEnv) -> np.ndarray:
    return env.action_masks()

def _make_single_env(config_path: str, difficulty_level: int = 3, freeze_ml: bool = True):
    def _init():
        env = RestaurantGymEnv(config_path=config_path, difficulty_level=difficulty_level, freeze_ml=freeze_ml)
        if ActionMasker is not None:
            return ActionMasker(env, mask_fn)
        return env
    return _init

def make_vectorized_env(config_path: str = "config/default_layout.json", difficulty_level: int = 3, num_envs: int = 4, freeze_ml: bool = True):
    if num_envs <= 1 or SubprocVecEnv is None:
        base_env = RestaurantGymEnv(config_path=config_path, difficulty_level=difficulty_level, freeze_ml=freeze_ml)
        return ActionMasker(base_env, mask_fn) if ActionMasker is not None else base_env
    
    env_fns = [_make_single_env(config_path, difficulty_level, freeze_ml) for _ in range(num_envs)]
    return SubprocVecEnv(env_fns)

class OrderSchedulerRLAgent:
    def __init__(self, env = None, config_path: str = "config/default_layout.json", num_envs: int = 4, difficulty_level: int = 3, model_path: str = "models/ppo_order_scheduler.zip", freeze_ml: bool = True, debug_mode: bool = False):
        self.config_path = config_path
        self.difficulty_level = difficulty_level
        self.num_envs = num_envs
        self.freeze_ml = freeze_ml
        self.model_path = model_path
        self.debug_mode = debug_mode
        
        if env is not None:
            if ActionMasker is not None and not isinstance(env, (ActionMasker, SubprocVecEnv, DummyVecEnv)):
                self.env = ActionMasker(env, mask_fn)
            else:
                self.env = env
        else:
            if self.debug_mode:
                # In debug mode, use single environment with debug tracking enabled
                self.raw_debug_env = RestaurantGymEnv(config_path=self.config_path, difficulty_level=self.difficulty_level, freeze_ml=self.freeze_ml, debug_mode=True)
                self.env = ActionMasker(self.raw_debug_env, mask_fn) if ActionMasker is not None else self.raw_debug_env
            else:
                self.raw_debug_env = None
                self.env = make_vectorized_env(config_path=self.config_path, difficulty_level=self.difficulty_level, num_envs=self.num_envs, freeze_ml=self.freeze_ml)
            
        self.model = None
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)

    def train(self, total_timesteps: int = 10000):
        if MaskablePPO is None:
            print("sb3-contrib is not installed. Cannot train RL Agent.", flush=True)
            return
            
        print(f"Training MaskablePPO Agent for {total_timesteps:,} timesteps across {1 if self.debug_mode else self.num_envs} envs...", flush=True)
        if self.model is None:
            self.model = MaskablePPO("MlpPolicy", self.env, verbose=1, n_steps=512, batch_size=128)
            self.model.learn(total_timesteps=total_timesteps)
        else:
            self.model.set_env(self.env)
            self.model.learn(total_timesteps=total_timesteps, reset_num_timesteps=False)
            
        self.model.save(self.model_path)
        print(f"Training complete. Model saved to {self.model_path}", flush=True)
        
        if self.debug_mode and self.raw_debug_env is not None:
            self.export_debug_report()

    def export_debug_report(self, output_path: str = "results/training_debug.md"):
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        stats = getattr(self.raw_debug_env, "debug_stats", {})
        if not stats:
            return
            
        tot_steps = max(1, stats.get("total_steps", 1))
        noop_cnt = stats.get("actions_noop", 0)
        valid_cnt = stats.get("actions_valid_assign", 0)
        invalid_cnt = stats.get("actions_invalid_assign", 0)
        
        noop_pct = (noop_cnt / tot_steps) * 100
        valid_pct = (valid_cnt / tot_steps) * 100
        invalid_pct = (invalid_cnt / tot_steps) * 100
        
        rw = stats.get("reward_breakdown", {})
        busy = stats.get("station_busy_ticks", {})
        full = stats.get("station_full_ticks", {})
        broken = stats.get("station_broken_ticks", {})
        churns = stats.get("churn_events", [])
        
        lines = [
            "# 🔍 RL Eğitim ve Simülasyon Detaylı Hata Ayıklama (Debug) Raporu\n",
            f"**Tarih:** {os.popen('date /t').read().strip() if os.name == 'nt' else ''} | **Yapılandırma:** `{self.config_path}` | **Zorluk Seviyesi:** {self.difficulty_level}\n",
            "---\n",
            "## 1. 🎯 Aksiyon Seçim Dağılımı ve Politika Eğilimleri\n",
            f"* **Toplam Alınan Karar Adımı:** `{tot_steps:,}`",
            f"* **Geçerli Sipariş Atamaları (`ASSIGN`):** `{valid_cnt:,}` (%{valid_pct:.2f})",
            f"* **Boşta Bekleme (`No-Op`):** `{noop_cnt:,}` (%{noop_pct:.2f})",
            f"* **Geçersiz/Engellenmiş Hamle Girişimleri:** `{invalid_cnt:,}` (%{invalid_pct:.2f})\n",
            "> [!NOTE]\n",
            f"> Ajan kararlarının %{valid_pct:.1f}'inde mutfağa aktif sipariş atamış, %{noop_pct:.1f}'inde ise mutfağın pişirmesini beklemiştir.\n",
            "---\n",
            "## 2. 💰 Ödül ve Ceza Dağılım Bileşenleri\n",
            "| Ödül/Ceza Kalemi | Toplam Puan | Etki Yönü | Açıklama |",
            "| :--- | :--- | :--- | :--- |",
            f"| **Tamamlanan Sipariş Bonusu** | `+{rw.get('completed_bonus', 0):.1f}` | Pozitif 🟢 | Masaya/kuryeye başarıyla teslim edilen siparişler |",
            f"| **Sub-tick Atama Bonusu** | `+{rw.get('subtick_assign_bonus', 0):.1f}` | Pozitif 🟢 | Aynı dakika içinde seri aşçı doldurma teşviki |",
            f"| **Müşteri Kaybı (Churn) Cezası** | `-{rw.get('churn_penalty', 0):.1f}` | Negatif 🔴 | Sabrı tükenip restorandan ayrılan müşteriler |",
            f"| **Kuyrukta Bekleme Cezası** | `-{rw.get('queue_wait_penalty', 0):.1f}` | Negatif 🔴 | Siparişlerin mutfağa alınmadan beklediği süre |",
            f"| **Soğuk Yemek Cezası (Group Sync)** | `-{rw.get('cold_food_penalty', 0):.1f}` | Negatif 🔴 | Aynı masanın diğer yemeklerini beklerken soğuyan tabaklar |",
            f"| **Kurye Gecikme Cezası** | `-{rw.get('courier_wait_penalty', 0):.1f}` | Negatif 🔴 | Paket servis kuryesinin kapıda bekletilme cezası |\n",
            "---\n",
            "## 3. 🍳 İstasyon Yükü ve Darboğaz Analizi\n",
            "| İstasyon ID | Meşgul Olduğu Adım | Tam Dolu Olduğu Adım | Arıza Yaşanan Adım | Durum Değerlendirmesi |",
            "| :--- | :--- | :--- | :--- | :--- |"
        ]
        
        for s_id in busy:
            b_cnt = busy.get(s_id, 0)
            f_cnt = full.get(s_id, 0)
            br_cnt = broken.get(s_id, 0)
            
            b_pct = (b_cnt / tot_steps) * 100
            f_pct = (f_cnt / tot_steps) * 100
            
            status = "Dengeli 🟢"
            if f_pct > 60:
                status = "KRİTİK DARBOĞAZ (Aşırı Yük) 🔴"
            elif f_pct > 35:
                status = "Yoğun 🟡"
                
            lines.append(f"| `{s_id}` | {b_cnt:,} (%{b_pct:.1f}) | {f_cnt:,} (%{f_pct:.1f}) | {br_cnt:,} | {status} |")
            
        lines.extend([
            "\n---\n",
            "## 4. ⚠️ Olay ve Anomali Kayıtları\n",
            f"* **Toplam Churn Olay Sayısı:** `{len(churns)}` kez müşteri sabır tükenmesi gerçekleşti.",
            f"* **Tamamlanan Sipariş Sayısı:** `{len(self.raw_debug_env.engine.completed_orders)}` sipariş.",
            f"* **Kalan Kuyruk Uzunluğu:** `{len(self.raw_debug_env.engine.order_queue)}` sipariş.\n"
        ])
        
        if churns:
            lines.append("### 🚨 Churn Olay Zaman Çizelgesi (Örnek İlk 10 Kayıt):")
            lines.append("| Simülasyon Dakikası (Tick) | Kaçan Müşteri Sayısı |")
            lines.append("| :--- | :--- |")
            for ch in churns[:10]:
                lines.append(f"| Dakika {ch['tick']} | {ch['churned_count']} Müşteri |")
                
        lines.append("\n---\n*Bu rapor Detaylı Debug Modu tarafından otomatik üretilmiştir.*")
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
            
        print(f"\n[DEBUG RAPORU OLUŞTURULDU] Rapor kaydedildi: {output_path}", flush=True)

    def train_curriculum(self, timesteps_per_phase: dict = None):
        if MaskablePPO is None:
            print("sb3-contrib is not installed. Cannot train RL Agent.")
            return
            
        if timesteps_per_phase is None:
            timesteps_per_phase = {1: 50000, 2: 100000, 3: 150000}
            
        print("\n--- Phase 0: Behavior Cloning Pre-training (LPT/MinPatience Warmstart) ---")
        eval_env = RestaurantGymEnv(config_path=self.config_path, difficulty_level=1, freeze_ml=self.freeze_ml)
        wrapped_eval = ActionMasker(eval_env, mask_fn) if ActionMasker is not None else eval_env
        states, actions = collect_expert_data(wrapped_eval, get_expert_action, num_episodes=20)
        
        self.model = MaskablePPO("MlpPolicy", self.env, verbose=0, n_steps=512, batch_size=128)
        train_bc_policy(self.model, states, actions, epochs=1, batch_size=128)
        
        for phase in [1, 2, 3]:
            print(f"\n--- Phase {phase}: Curriculum Training (Difficulty Level {phase}) ---")
            phase_env = make_vectorized_env(config_path=self.config_path, difficulty_level=phase, num_envs=self.num_envs, freeze_ml=self.freeze_ml)
            self.model.set_env(phase_env)
            self.model.learn(total_timesteps=timesteps_per_phase[phase], reset_num_timesteps=False)
            if hasattr(phase_env, "close"):
                phase_env.close()
            
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
        
        eval_base = RestaurantGymEnv(config_path=self.config_path, difficulty_level=self.difficulty_level, freeze_ml=self.freeze_ml)
        eval_env = ActionMasker(eval_base, mask_fn) if ActionMasker is not None else eval_base
        
        for i in range(n_episodes):
            obs, info = eval_env.reset(seed=42 + i)
            done = False
            episode_reward = 0.0
            
            while not done:
                action_masks = eval_env.action_masks()
                action, _states = self.model.predict(obs, action_masks=action_masks, deterministic=True)
                obs, reward, terminated, truncated, info = eval_env.step(action)
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
