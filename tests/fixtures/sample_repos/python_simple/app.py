"""Small Python fixture application."""

from fastapi import FastAPI
from services.user_service import UserService

app = FastAPI()
service = UserService()


@app.get("/users/{user_id}")
def get_user(user_id: int) -> dict[str, object]:
    """Fetch a user by identifier."""
    return service.get_user(user_id)
