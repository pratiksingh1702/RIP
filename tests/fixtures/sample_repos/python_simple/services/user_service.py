"""User service fixture."""

from repositories.user_repository import UserRepository


class UserService:
    """Coordinates user lookups."""

    def __init__(self) -> None:
        self.repository = UserRepository()

    def get_user(self, user_id: int) -> dict[str, object]:
        return self.repository.find_user(user_id)

    def unused_helper(self) -> str:
        return "unused"
