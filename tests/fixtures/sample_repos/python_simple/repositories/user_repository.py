"""User repository fixture."""

from models.user import User


class UserRepository:
    """Reads users from storage."""

    def find_user(self, user_id: int) -> dict[str, object]:
        user = User(id=user_id, name="Ada")
        return user.to_dict()
