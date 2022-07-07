from loguru import logger

logger.add(
    sink='./logs/error.log',
    level='ERROR',
    format='{time} | {level} | {message}'
)
