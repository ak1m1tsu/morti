from rich.console import Console
from loguru import logger


logger.add(
    sink='./logs/error.log',
    level='ERROR',
    format='{time} | {level} | {message}'
)

console = Console()
