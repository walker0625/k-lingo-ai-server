## Wrigting, Speacking Scenario
import random
from pydantic import BaseModel
from db.model.scenario import ReadingQuest,ListeningQuest, QuestLevel, StageType
from common.ko_util import korean_to_english_pronunciation
## logger
from loguru import logger
