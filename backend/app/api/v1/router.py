from fastapi import APIRouter
from app.api.v1 import auth, users, presentations, designs, articles, obyektivka, commerce, jobs

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(users.router)

api_router.include_router(commerce.router)
api_router.include_router(jobs.router)
api_router.include_router(presentations.router)
api_router.include_router(designs.router)
api_router.include_router(articles.router)
api_router.include_router(obyektivka.router)
