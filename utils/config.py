import json
import os
import asyncio

class Config:
    def __init__(self, config_path):
        self.config_path = config_path
        self._config = {}
        self._lock = asyncio.Lock()
        self.load()

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    self._config = json.load(f)
            except Exception as e:
                print(f"Error loading config: {e}")
                self._config = {}
        else:
            self._config = {}

    async def save(self):
        async with self._lock:
            try:
                with open(self.config_path, "w") as f:
                    json.dump(self._config, f, indent=4)
            except Exception as e:
                print(f"Error saving config: {e}")

    def get(self, key, default=None):
        return self._config.get(key, default)

    async def set(self, key, value):
        self._config[key] = value
        await self.save()
