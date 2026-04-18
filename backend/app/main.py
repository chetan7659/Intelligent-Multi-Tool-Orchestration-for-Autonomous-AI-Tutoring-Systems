from contextlib import asynccontextmanager
import time
from collections import defaultdict
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.config import settings
from app.database import init_db
from app.api.routes import router


# ── Standardized error response builder ───────────────────────────────────────

ERROR_CODE_MAP = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMIT_EXCEEDED",
    500: "INTERNAL_SERVER_ERROR",
}


def error_response(status_code: int, message: str, details=None) -> JSONResponse:
    """Build a consistent JSON error envelope."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": message,
            "error_code": ERROR_CODE_MAP.get(status_code, "UNKNOWN_ERROR"),
            "details": details,
        },
    )


# ── Rate-limiter state (simple in-memory, per-IP) ─────────────────────────────

_rate_store: dict = defaultdict(list)
RATE_LIMIT = 60          # requests per window
RATE_WINDOW_SECS = 60    # window size in seconds


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[startup] EduOrchestrator v3 starting...")
    try:
        await init_db()
        print("[startup] Database ready")
    except Exception as e:
        print(f"[startup] DB warning (ok in dev without DB): {e}")

    from app.tools.registry import registry
    print(f"[startup] {len(registry.names())} tools registered")

    yield
    print("[shutdown] Shutting down")


app = FastAPI(
    title="EduOrchestrator API v3",
    description="Intelligent middleware orchestrator — 20 educational tools via LangGraph + HuggingFace",
    version="3.0.0",
    lifespan=lifespan,
)


# ── Global Exception Handlers ────────────────────────────────────────────────

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Catches all HTTPException raises (400, 401, 404, 500, etc.)
    and formats them into the standardized {error, error_code, details} envelope."""
    return error_response(
        status_code=exc.status_code,
        message=str(exc.detail),
        details=None,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Catches Pydantic / FastAPI 422 validation errors and remaps them
    to a 400 Bad Request with human-readable messages."""
    errors = []
    for err in exc.errors():
        field = " → ".join(str(loc) for loc in err.get("loc", []))
        errors.append(f"{field}: {err.get('msg', 'invalid')}")
    return error_response(
        status_code=400,
        message="Invalid input parameters",
        details=errors,
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Last-resort handler for unhandled exceptions — prevents raw
    tracebacks from leaking to the client."""
    print(f"[ERROR] Unhandled exception on {request.method} {request.url}: {exc}")
    return error_response(
        status_code=500,
        message="An unexpected internal error occurred",
        details=str(exc) if settings.DEBUG else None,
    )


# ── Rate-limiter middleware ───────────────────────────────────────────────────

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Simple in-memory per-IP rate limiter.
    Returns 429 if the client exceeds RATE_LIMIT requests within RATE_WINDOW_SECS."""
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()

    # Prune timestamps outside the current window
    _rate_store[client_ip] = [t for t in _rate_store[client_ip] if now - t < RATE_WINDOW_SECS]

    if len(_rate_store[client_ip]) >= RATE_LIMIT:
        return error_response(
            status_code=429,
            message="Too many requests. Please slow down.",
            details=f"Rate limit: {RATE_LIMIT} requests per {RATE_WINDOW_SECS}s",
        )

    _rate_store[client_ip].append(now)
    response = await call_next(request)
    return response


# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
