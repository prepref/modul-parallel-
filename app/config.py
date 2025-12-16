from dataclasses import dataclass
from typing import Literal, List

import os

from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

MessengerType = Literal["telegram"]

@dataclass
class BotConfig:
    token: str
    messenger: MessengerType

def load_bots_from_env() -> List[BotConfig]:
    """
    Загружает список ботов из переменных окружения:
    BOT_1=telegram:1234567:ABC
    BOT_2=email:imap:token
    """
    bots = []
    for key, value in os.environ.items():
        if key.startswith("BOT_"):
            try:
                messenger, token = value.split(":", 1)
                bots.append(BotConfig(token=token.strip(), messenger=messenger.strip()))
            except ValueError:
                continue
    
    return bots
    