from fastapi import APIRouter
from app.api.v1 import auth, users, bot, presentations, designs, articles, obyektivka

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(users.router)

api_router.include_router(bot.router)
api_router.include_router(presentations.router)
api_router.include_router(designs.router)
api_router.include_router(articles.router)
api_router.include_router(obyektivka.router)
