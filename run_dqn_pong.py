from Wrapper.layers import *
from Wrapper.wrappers import make_atari, wrap_deepmind, wrap_pytorch
import math, random
import gym
import numpy as np
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
import torch.optim as optim
import torch.autograd as autograd 
import torch.nn.functional as F
import sys
pthname_lst = [x for x in sys.argv if x.endswith(".pth")]
if(len(sys.argv) < 2 or len(pthname_lst) != 1):
    print("No model loaded, defaulting to model_pretrained.pth")
    pthname = "model_pretrained.pth"
else:
    pthname = pthname_lst[0]

USE_CUDA = torch.cuda.is_available()
from dqn import QLearner, compute_td_loss, ReplayBuffer

fileSaveName = "model_saveOVER1M.pth"

env_id = "PongNoFrameskip-v4"
env = make_atari(env_id)
env = wrap_deepmind(env)
env = wrap_pytorch(env)

num_frames = 2000000
batch_size = 32
gamma = 0.99
record_idx = 10000

replay_initial = 10000
replay_buffer = ReplayBuffer(100000)
model = QLearner(env, num_frames, batch_size, gamma, replay_buffer)
model.load_state_dict(torch.load(pthname, map_location='cpu'))

target_model = QLearner(env, num_frames, batch_size, gamma, replay_buffer)
target_model.copy_from(model)

optimizer = optim.Adam(model.parameters(), lr=0.00001)
if USE_CUDA:
    model = model.cuda()
    target_model = target_model.cuda()
    print("Using cuda")

epsilon_start = 1.0
epsilon_final = 0.01
epsilon_decay = 30000
epsilon_by_frame = lambda frame_idx: epsilon_final + (epsilon_start - epsilon_final) * math.exp(-1. * frame_idx / epsilon_decay)

losses = []
all_rewards = []

last_loss_index = 0
last_reward_index = 0

episode_reward = 0

state = env.reset()

for frame_idx in range(1000000, num_frames + 1):
    #print("Frame: " + str(frame_idx))

    epsilon = epsilon_by_frame(frame_idx)
    action = model.act(state, epsilon)
    
    next_state, reward, done, _ = env.step(action)
    replay_buffer.push(state, action, reward, next_state, done)
    
    state = next_state
    episode_reward += reward
    
    if done:
        state = env.reset()
        all_rewards.append((frame_idx, episode_reward))
        episode_reward = 0

    if len(replay_buffer) > replay_initial:
        loss = compute_td_loss(model, target_model, batch_size, gamma, replay_buffer)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        losses.append((frame_idx, loss.data.cpu().numpy()))

    if frame_idx % 10000 == 0 and len(replay_buffer) <= replay_initial:
        print('#Frame: %d, preparing replay buffer' % frame_idx)

    if frame_idx % 10000 == 0 and len(replay_buffer) > replay_initial:
        print('#Frame: %d, Loss: %f' % (frame_idx, np.mean(losses, 0)[1]))
        print('Last-10 average reward: %f' % np.mean(all_rewards[-10:], 0)[1])

    if frame_idx % 50000 == 0:
        target_model.copy_from(model)

    if frame_idx % 10000 == 0:
        torch.save(model.state_dict(), fileSaveName)
        with open("losses.txt", "a") as f:
            with open("rewards.txt", "a") as g:
                #print(len(all_rewards))
                while last_loss_index < len(losses):
                    x,y = losses[last_loss_index]

                    f.write(str(x) + "," + str(y) + "\n")
                    last_loss_index += 1
                while last_reward_index < len(all_rewards):
                    x,y = all_rewards[last_reward_index]
                    g.write(str(x) + "," + str(y) + "\n")
                    last_reward_index += 1




