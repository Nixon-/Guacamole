import json
import os
import random
from collections import deque
from pathlib import Path

import numpy as np

from guacamole.c4.client import GameClient
from guacamole.c4.game import GameToken, GameStateController


class QClient(GameClient):

    def __init__(self, controller: GameStateController, token: GameToken, exploration=0.05, learning_rate=0.05,
                 discount_factor=1.00, save_path=None):
        super().__init__(controller, token)
        self._policy = dict()
        self.exploration, self.alpha, self.gamma = exploration, learning_rate, discount_factor
        self._action_sequence = deque()
        self.save_path = save_path

    def load(self):
        if not Path(self.save_path).exists():
            return
        with open(self.save_path, 'r') as mf:
            for entry in json.load(mf):
                state = np.array(entry['state'], dtype=np.int8)
                self._policy[tuple(tuple(x) for x in state)] = list(entry['values'])

    def save(self):
        saveable_state = [{
            'state': [[int(x) for x in col] for col in key],
            'values': values}
            for key, values in self._policy.items()
        ]
        os.makedirs(os.path.split(self.save_path)[0], exist_ok=True)
        with open(self.save_path, 'w') as mf:
            json.dump(saveable_state, fp=mf)

    def provide_action(self) -> int:
        state = self.controller.encode()
        if random.random() < self.exploration:
            action = random.randint(0, self.controller.size() - 1)
            self._action_sequence.append((state, action))
            return action

        if state not in self._policy:
            self._policy[state] = [random.random() for _ in range(self.controller.size())]
        values = self._policy[state]
        action = max(range(self.controller.size()), key=lambda i: values[i])
        self._action_sequence.append((state, action))
        return action

    def bad_move(self):
        state, action = self._action_sequence.popleft()
        if state not in self._policy:
            self._policy[state] = [random.random() for _ in range(self.controller.size())]

        self._policy[state][action] = -1

    def lost(self):
        self._update_with_reward(-1)

    def won(self):
        self._update_with_reward(1)

    def tie(self):
        self._action_sequence.clear()

    def _update_with_reward(self, reward: float):

        state, action = self._action_sequence.popleft()
        if state not in self._policy:
            self._policy[state] = [random.random() for _ in range(self.controller.size())]

        self._policy[state][action] += (1 - self.alpha) * self._policy[state][action] + self.alpha * reward

        max_prev = self.gamma * max(self._policy[state])
        while len(self._action_sequence) > 0:
            state, action = self._action_sequence.popleft()
            if state not in self._policy:
                self._policy[state] = [random.random() for _ in range(self.controller.size())]

            self._policy[state][action] = (1 - self.alpha) * self._policy[state][action] + self.alpha * max_prev
            max_prev = self.gamma * max(self._policy[state])