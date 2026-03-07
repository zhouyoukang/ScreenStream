#!/usr/bin/env python3
"""
Go1 RL Integration Module — 强化学习全链路虚拟开发
连接 Gymnasium RL 环境 ↔ Go1 Brain v2.0，全程不依赖实机

功能:
  1. Go1GymEnv — Gymnasium标准环境(MuJoCo 3.5.0)
  2. RLTrainer — PPO训练管线(Stable-Baselines3)
  3. RLPolicy  — 训练好的策略加载与推理
  4. BrainRLBehavior — 将RL策略接入Brain行为系统

用法:
  python go1_rl.py --test              # 运行全链路测试
  python go1_rl.py --train --steps 1M  # 训练新策略
  python go1_rl.py --eval <model.zip>  # 评估已有策略
  python go1_rl.py --info              # 显示环境信息

依赖: gymnasium, stable-baselines3, mujoco>=3.0, numpy, torch
参考: refs/quadruped-rl-locomotion (nimazareian, 123★)
"""

import os
import sys
import json
import time
import shutil
import tempfile
import argparse
import numpy as np
from pathlib import Path

# ─── 路径处理 (MuJoCo不支持中文路径) ───
_SCRIPT_DIR = Path(__file__).parent.resolve()
_RL_REF_DIR = _SCRIPT_DIR / "refs" / "quadruped-rl-locomotion"
_MODELS_DIR = _SCRIPT_DIR / "rl_models"
_TMP_ENV_DIR = None  # 延迟初始化

def _ensure_ascii_env():
    """将RL环境复制到ASCII路径(MuJoCo限制)"""
    global _TMP_ENV_DIR
    if _TMP_ENV_DIR and os.path.exists(_TMP_ENV_DIR):
        return _TMP_ENV_DIR
    
    ascii_safe = all(ord(c) < 128 for c in str(_RL_REF_DIR))
    if ascii_safe:
        _TMP_ENV_DIR = str(_RL_REF_DIR)
        return _TMP_ENV_DIR
    
    _TMP_ENV_DIR = os.path.join(tempfile.gettempdir(), "go1_rl_env")
    if os.path.exists(_TMP_ENV_DIR):
        shutil.rmtree(_TMP_ENV_DIR)
    shutil.copytree(str(_RL_REF_DIR), _TMP_ENV_DIR,
                    ignore=shutil.ignore_patterns('.git', 'models', 'recordings'))
    return _TMP_ENV_DIR


# ─── Go1 Gymnasium 环境包装器 ───
class Go1GymEnv:
    """Go1 MuJoCo Gymnasium环境的高级包装器"""
    
    def __init__(self, ctrl_type="torque", render_mode=None):
        env_dir = _ensure_ascii_env()
        if env_dir not in sys.path:
            sys.path.insert(0, env_dir)
        
        old_cwd = os.getcwd()
        os.chdir(env_dir)
        try:
            from go1_mujoco_env import Go1MujocoEnv
            self.env = Go1MujocoEnv(ctrl_type=ctrl_type, render_mode=render_mode)
        finally:
            os.chdir(old_cwd)
        
        self.ctrl_type = ctrl_type
        self.obs_shape = self.env.observation_space.shape
        self.action_shape = self.env.action_space.shape
        self._episode_reward = 0
        self._episode_steps = 0
        self._total_episodes = 0
    
    def reset(self):
        obs, info = self.env.reset()
        self._episode_reward = 0
        self._episode_steps = 0
        return obs, info
    
    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        self._episode_reward += reward
        self._episode_steps += 1
        if terminated or truncated:
            self._total_episodes += 1
            info["episode_reward"] = self._episode_reward
            info["episode_steps"] = self._episode_steps
        return obs, reward, terminated, truncated, info
    
    def close(self):
        self.env.close()
    
    @property
    def info(self):
        return {
            "ctrl_type": self.ctrl_type,
            "obs_shape": self.obs_shape,
            "action_shape": self.action_shape,
            "total_episodes": self._total_episodes,
            "mujoco_model": "Go1 (Unitree)",
        }


# ─── RL 训练管线 ───
class RLTrainer:
    """PPO训练管线 — 全虚拟, 不依赖实机"""
    
    def __init__(self, ctrl_type="torque", n_envs=4, device="auto"):
        self.ctrl_type = ctrl_type
        self.n_envs = n_envs
        self.device = device
        self.model = None
    
    def train(self, total_timesteps=1_000_000, save_path=None, log_dir=None):
        from stable_baselines3 import PPO
        from stable_baselines3.common.vec_env import SubprocVecEnv
        from stable_baselines3.common.env_util import make_vec_env
        from stable_baselines3.common.callbacks import EvalCallback
        
        env_dir = _ensure_ascii_env()
        if env_dir not in sys.path:
            sys.path.insert(0, env_dir)
        
        old_cwd = os.getcwd()
        os.chdir(env_dir)
        try:
            from go1_mujoco_env import Go1MujocoEnv
            vec_env = make_vec_env(
                Go1MujocoEnv,
                env_kwargs={"ctrl_type": self.ctrl_type},
                n_envs=self.n_envs,
                seed=42,
                vec_env_cls=SubprocVecEnv,
            )
        finally:
            os.chdir(old_cwd)
        
        if save_path is None:
            _MODELS_DIR.mkdir(exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            save_path = str(_MODELS_DIR / f"go1_{self.ctrl_type}_{ts}")
        
        if log_dir is None:
            log_dir = str(_MODELS_DIR / "logs")
        
        eval_callback = EvalCallback(
            vec_env,
            best_model_save_path=save_path,
            log_path=log_dir,
            eval_freq=max(total_timesteps // 20, 5000),
            n_eval_episodes=5,
            deterministic=True,
        )
        
        self.model = PPO("MlpPolicy", vec_env, verbose=1,
                         tensorboard_log=log_dir, device=self.device)
        self.model.learn(total_timesteps=total_timesteps, callback=eval_callback)
        
        final_path = f"{save_path}/final_model"
        self.model.save(final_path)
        vec_env.close()
        
        return final_path
    
    def load(self, model_path):
        from stable_baselines3 import PPO
        self.model = PPO.load(model_path, device=self.device)
        return self.model


# ─── RL 策略加载与推理 ───
class RLPolicy:
    """加载训练好的PPO策略进行推理"""
    
    def __init__(self, model_path=None, device="cpu"):
        self.device = device
        self.model = None
        self.expected_obs_size = None
        if model_path:
            self.load(model_path)
    
    def load(self, model_path):
        from stable_baselines3 import PPO
        self.model = PPO.load(model_path, device=self.device)
        self.expected_obs_size = self.model.observation_space.shape[0]
        return self
    
    def predict(self, obs, deterministic=True):
        if self.model is None:
            raise RuntimeError("No model loaded")
        
        # 处理obs shape不匹配(旧模型45 vs 新环境48)
        if len(obs) != self.expected_obs_size:
            if len(obs) > self.expected_obs_size:
                # 截断多余的obs(通常是projected_gravity 3个值)
                obs = obs[:self.expected_obs_size]
            else:
                # 填充不足的obs
                obs = np.pad(obs, (0, self.expected_obs_size - len(obs)))
        
        action, _ = self.model.predict(obs, deterministic=deterministic)
        return action
    
    @property
    def info(self):
        if self.model is None:
            return {"loaded": False}
        return {
            "loaded": True,
            "expected_obs_size": self.expected_obs_size,
            "policy_type": self.model.policy.__class__.__name__,
        }


# ─── 预训练模型发现 ───
def find_pretrained_models():
    """扫描refs/中的预训练模型"""
    models = []
    
    # quadruped-rl-locomotion models
    rl_models = _RL_REF_DIR / "models"
    if rl_models.exists():
        for d in sorted(rl_models.iterdir()):
            if d.is_dir():
                for f in d.glob("*.zip"):
                    models.append({
                        "path": str(f),
                        "name": f"{d.name}/{f.name}",
                        "source": "quadruped-rl-locomotion",
                        "framework": "stable-baselines3",
                    })
    
    # rl_sar policy weights
    rl_sar = _SCRIPT_DIR / "refs" / "rl_sar" / "policy"
    if rl_sar.exists():
        for robot_dir in sorted(rl_sar.iterdir()):
            if robot_dir.is_dir():
                for f in robot_dir.rglob("*.pt"):
                    models.append({
                        "path": str(f),
                        "name": f"{robot_dir.name}/{f.name}",
                        "source": "rl_sar",
                        "framework": "pytorch",
                    })
    
    # GenLoco policies
    genloco = _SCRIPT_DIR / "refs" / "GenLoco" / "motion_imitation" / "data" / "policies"
    if genloco.exists():
        for f in genloco.glob("*.zip"):
            models.append({
                "path": str(f),
                "name": f.name,
                "source": "GenLoco",
                "framework": "tensorflow",
            })
    
    return models


# ─── 全链路测试 ───
def run_full_test(quiet=False):
    """全链路RL测试 — 环境创建→随机策略→预训练加载→推理"""
    results = {"tests": [], "pass": 0, "fail": 0}
    
    def test(name, fn):
        try:
            fn()
            results["tests"].append({"name": name, "status": "PASS"})
            results["pass"] += 1
            if not quiet:
                print(f"  PASS: {name}")
        except Exception as e:
            results["tests"].append({"name": name, "status": "FAIL", "error": str(e)})
            results["fail"] += 1
            if not quiet:
                print(f"  FAIL: {name} — {e}")
    
    env = None
    
    # T1: Create torque environment
    def t1():
        nonlocal env
        env = Go1GymEnv(ctrl_type="torque")
        assert env.obs_shape[0] > 0
        if not quiet:
            print(f"    obs={env.obs_shape}, action={env.action_shape}")
    test("T01 Create Go1 torque env", t1)
    
    # T2: Create position environment
    env_pos = None
    def t2():
        nonlocal env_pos
        env_pos = Go1GymEnv(ctrl_type="position")
        assert env_pos.obs_shape[0] > 0
    test("T02 Create Go1 position env", t2)
    
    # T3: Reset and step (torque)
    def t3():
        obs, _ = env.reset()
        total_r = 0
        for _ in range(50):
            obs, r, term, trunc, info = env.step(np.zeros(12))
            total_r += r
            if term or trunc:
                obs, _ = env.reset()
        if not quiet:
            print(f"    50 zero-action steps, reward={total_r:.2f}")
    test("T03 Step 50 (zero action)", t3)
    
    # T4: Random actions (torque)
    def t4():
        obs, _ = env.reset()
        total_r = 0
        for _ in range(100):
            obs, r, term, trunc, info = env.step(env.env.action_space.sample())
            total_r += r
            if term or trunc:
                obs, _ = env.reset()
        if not quiet:
            print(f"    100 random steps, reward={total_r:.2f}")
    test("T04 Step 100 (random)", t4)
    
    # T5: Random actions (position)
    def t5():
        obs, _ = env_pos.reset()
        total_r = 0
        for _ in range(100):
            obs, r, term, trunc, info = env_pos.step(env_pos.env.action_space.sample())
            total_r += r
            if term or trunc:
                obs, _ = env_pos.reset()
        if not quiet:
            print(f"    100 pos-ctrl steps, reward={total_r:.2f}")
    test("T05 Step 100 (position ctrl)", t5)
    
    # T6: Environment properties
    def t6():
        env.reset()
        env.step(np.zeros(12))
        h = env.env.is_healthy
        g = env.env.projected_gravity
        f = env.env.feet_contact_forces
        assert g.shape == (3,), f"gravity shape {g.shape}"
        assert f.shape == (4,), f"feet shape {f.shape}"
        if not quiet:
            print(f"    healthy={h}, gravity_norm={np.linalg.norm(g):.2f}, feet={f}")
    test("T06 Env properties (health/gravity/feet)", t6)
    
    # T7: Reward components
    def t7():
        env.reset()
        env.step(np.zeros(12))
        lr = env.env.linear_velocity_tracking_reward
        ar = env.env.angular_velocity_tracking_reward
        assert isinstance(lr, (float, np.floating))
        if not quiet:
            print(f"    lin_vel_rew={lr:.4f}, ang_vel_rew={ar:.4f}")
    test("T07 Reward components", t7)
    
    # T8: Find pretrained models
    def t8():
        models = find_pretrained_models()
        sb3_models = [m for m in models if m["framework"] == "stable-baselines3"]
        pt_models = [m for m in models if m["framework"] == "pytorch"]
        if not quiet:
            print(f"    total={len(models)}, sb3={len(sb3_models)}, pytorch={len(pt_models)}")
        assert len(models) > 0, "No pretrained models found"
    test("T08 Find pretrained models", t8)
    
    # T9: Load pretrained PPO
    policy = None
    def t9():
        nonlocal policy
        models = find_pretrained_models()
        sb3 = [m for m in models if m["framework"] == "stable-baselines3" and "torque" in m["name"]]
        assert len(sb3) > 0, "No SB3 torque models found"
        policy = RLPolicy(sb3[0]["path"], device="cpu")
        if not quiet:
            print(f"    loaded: {sb3[0]['name']}, obs_size={policy.expected_obs_size}")
    test("T09 Load pretrained PPO policy", t9)
    
    # T10: Run pretrained policy inference
    def t10():
        obs, _ = env.reset()
        total_r = 0
        steps = 0
        for _ in range(200):
            action = policy.predict(obs)
            obs, r, term, trunc, info = env.step(action)
            total_r += r
            steps += 1
            if term or trunc:
                break
        if not quiet:
            print(f"    PPO: {steps} steps, reward={total_r:.2f}")
    test("T10 PPO inference (obs-compat)", t10)
    
    # T11: Environment info
    def t11():
        info = env.info
        assert info["ctrl_type"] == "torque"
        assert info["mujoco_model"] == "Go1 (Unitree)"
        if not quiet:
            print(f"    {json.dumps(info, default=str)}")
    test("T11 Environment info", t11)
    
    # T12: RLTrainer creation (no actual training)
    def t12():
        trainer = RLTrainer(ctrl_type="torque", n_envs=1, device="cpu")
        assert trainer.ctrl_type == "torque"
        if not quiet:
            print(f"    trainer ready, device={trainer.device}")
    test("T12 RLTrainer creation", t12)
    
    # T13: Project inventory
    def t13():
        refs_dir = _SCRIPT_DIR / "refs"
        projects = [d.name for d in refs_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
        if not quiet:
            print(f"    {len(projects)} ref projects: {', '.join(sorted(projects))}")
        assert len(projects) >= 10, f"Expected >=10 projects, got {len(projects)}"
    test("T13 Project inventory (>=10 refs)", t13)
    
    # Cleanup
    if env:
        env.close()
    if env_pos:
        env_pos.close()
    
    if not quiet:
        print(f"\n{'='*50}")
        print(f"RL Integration: {results['pass']} PASS / {results['fail']} FAIL / {results['pass']+results['fail']} TOTAL")
    
    return results


# ─── CLI ───
def main():
    parser = argparse.ArgumentParser(description="Go1 RL Integration")
    parser.add_argument("--test", action="store_true", help="Run full test suite")
    parser.add_argument("--train", action="store_true", help="Train new policy")
    parser.add_argument("--steps", type=str, default="100K", help="Training steps (e.g. 100K, 1M)")
    parser.add_argument("--eval", type=str, help="Evaluate a model")
    parser.add_argument("--info", action="store_true", help="Show environment info")
    parser.add_argument("--models", action="store_true", help="List pretrained models")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()
    
    if args.info:
        env = Go1GymEnv()
        info = env.info
        info["refs"] = str(_RL_REF_DIR)
        env.close()
        if args.json:
            print(json.dumps(info, default=str))
        else:
            for k, v in info.items():
                print(f"  {k}: {v}")
    
    elif args.models:
        models = find_pretrained_models()
        if args.json:
            print(json.dumps(models, indent=2))
        else:
            for m in models:
                print(f"  [{m['framework']}] {m['source']}: {m['name']}")
            print(f"\n  Total: {len(models)} models")
    
    elif args.test:
        results = run_full_test()
        if args.json:
            print(json.dumps(results, indent=2))
    
    elif args.train:
        steps_str = args.steps.upper().replace("K", "000").replace("M", "000000")
        steps = int(steps_str)
        print(f"Training Go1 PPO policy for {steps:,} steps...")
        trainer = RLTrainer(device="cpu")
        path = trainer.train(total_timesteps=steps)
        print(f"Model saved: {path}")
    
    elif args.eval:
        policy = RLPolicy(args.eval, device="cpu")
        env = Go1GymEnv()
        
        n_episodes = 5
        rewards = []
        for ep in range(n_episodes):
            obs, _ = env.reset()
            ep_reward = 0
            steps = 0
            while True:
                action = policy.predict(obs)
                obs, r, term, trunc, info = env.step(action)
                ep_reward += r
                steps += 1
                if term or trunc:
                    break
            rewards.append(ep_reward)
            print(f"  Episode {ep+1}: {steps} steps, reward={ep_reward:.2f}")
        
        env.close()
        print(f"\n  Mean reward: {np.mean(rewards):.2f} ± {np.std(rewards):.2f}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
