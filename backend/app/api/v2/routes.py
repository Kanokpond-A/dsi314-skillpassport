from fastapi import APIRouter
import json
from scoring.logic_020 import calculate_fit_score
from core.config import PARSED_DATA_PATH, IMPORT_LOG_PATH
from core.logging import get_logger

router = APIRouter()
logger = get_logger("ucb.v2")