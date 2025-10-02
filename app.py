from contextlib import asynccontextmanager
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from fastapi import APIRouter, FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.background import BackgroundTasks
import uvicorn
import asyncio
from datetime import datetime
from services import YandexComputeService
from config import settings

URL_SECRET = settings.URL_SECRET

# Handler для ежедневной ротации файла
file_handler = TimedRotatingFileHandler(
    'secret_app.log',
    when='midnight',
    interval=1,
    backupCount=7
)
file_handler.suffix = "%Y-%m-%d.log"

# Формат сообщений
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
file_handler.setFormatter(formatter)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        file_handler,
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Server start time for uptime tracking
SERVER_START_TIME = datetime.now()

# Глобальная переменная для задачи
background_task = None


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """Lifespan handler to start background tasks if enabled."""
    global background_task
    
    logger.info("Starting background auto-start task")
    background_task = asyncio.create_task(auto_start_background_task())
    
    yield  # приложение запускается здесь
    
    # Завершение фоновой задачи при остановке сервера
    if background_task:
        background_task.cancel()
        try:
            await background_task
        except asyncio.CancelledError:
            logger.info("Background auto-start task stopped")


# Initialize services
compute_service = YandexComputeService()

# Create secret app first
secret_app = FastAPI()

# Mount static files
static_path = Path("static")
static_path.mkdir(exist_ok=True)
secret_app.mount("/static", StaticFiles(directory="static"), name="static")


# Define routes for secret_app
@secret_app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main dashboard HTML page."""
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error("index.html not found in static directory")
        return "<h1>Dashboard not found</h1><p>Please ensure static/index.html exists</p>"


@secret_app.get("/api/instances")
async def list_instances(page_size: int = 50, page_token: str = None):
    """
    Get list of compute instances from Yandex Cloud.
    
    Args:
        page_size: Number of instances per page (default: 50)
        page_token: Token for pagination (optional)
    
    Returns:
        JSON with instances list and pagination token
    """
    logger.info(f"Fetching instances - page_size: {page_size}, page_token: {page_token}")
    
    try:
        result = compute_service.list_instances(page_size, page_token)
        logger.info(f"Successfully fetched {len(result.get('instances', []))} instances")
        return result
    except Exception as e:
        logger.error(f"Error fetching instances: {str(e)}", exc_info=True)
        return {"error": str(e), "instances": [], "nextPageToken": None}


@secret_app.get("/api/status")
async def get_status():
    """Get API status and health check."""
    logger.info("Health check requested")
    
    uptime = datetime.now() - SERVER_START_TIME
    uptime_str = f"{uptime.days}d {uptime.seconds // 3600}h {(uptime.seconds % 3600) // 60}m"
    
    return {
        "status": "healthy",
        "folder_id": settings.FOLDER_ID,
        "service": "yandex-compute-api",
        "version": "1.0.0",
        "uptime": uptime_str,
        "started_at": SERVER_START_TIME.isoformat()
    }


@secret_app.post("/api/instances/{instance_id}/start")
async def start_instance(instance_id: str):
    """Start a stopped instance."""
    logger.info(f"Start request for instance: {instance_id}")
    
    try:
        result = compute_service.start_instance(instance_id)
        return {
            "success": True,
            "operation_id": result.get("id"),
            "instance_id": instance_id,
            "message": "Instance start operation initiated"
        }
    except Exception as e:
        logger.error(f"Failed to start instance {instance_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@secret_app.post("/api/instances/{instance_id}/stop")
async def stop_instance(instance_id: str):
    """Stop a running instance."""
    logger.info(f"Stop request for instance: {instance_id}")
    
    try:
        result = compute_service.stop_instance(instance_id)
        return {
            "success": True,
            "operation_id": result.get("id"),
            "instance_id": instance_id,
            "message": "Instance stop operation initiated"
        }
    except Exception as e:
        logger.error(f"Failed to stop instance {instance_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@secret_app.post("/api/auto-start")
async def trigger_auto_start():
    """Manually trigger auto-start for all stopped instances."""
    logger.info("Manual auto-start triggered")
    
    try:
        result = compute_service.auto_start_stopped_instances()
        return result
    except Exception as e:
        logger.error(f"Auto-start failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def auto_start_background_task():
    """Background task that runs every minute to auto-start stopped instances."""
    while True:
        try:
            await asyncio.sleep(60)  # 1 minute
            logger.info("Running scheduled auto-start check")
            compute_service.auto_start_stopped_instances()
        except Exception as e:
            logger.error(f"Background auto-start failed: {e}")


# Create main app with lifespan
app = FastAPI(
    title="Yandex Compute API",
    description="API for managing Yandex Cloud Compute instances",
    version="1.0.0",
    lifespan=lifespan
)

# Create router for yc
yc_router = APIRouter(prefix="/yapi")


@app.exception_handler(404)
async def custom_404_handler(request: Request, exc):
    return FileResponse("static/404.html")


@yc_router.get("/", response_class=HTMLResponse)
async def default_root():
    """Просто возвращает заглушку default.html"""
    try:
        with open("static/default.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Default Page</h1><p>Welcome! Use the secret URL.</p>"


@yc_router.get("/robots.txt", response_class=PlainTextResponse)
async def robots():
    return "User-agent: *\nDisallow: /\n"


# Mount secret_app to the router
yc_router.mount(f"/{URL_SECRET}", secret_app)

# Include router in main app
app.include_router(yc_router)


if __name__ == "__main__":
    logger.info("Starting Yandex Compute API server...")
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=5777,
        reload=True,
        log_level="info"
    )