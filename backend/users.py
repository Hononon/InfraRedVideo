import json
import os
from dataclasses import dataclass
from typing import Optional, Dict, Any

from werkzeug.security import generate_password_hash, check_password_hash


@dataclass(frozen=True)
class User:
    username: str
    password_hash: str


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _load_users(db_path: str) -> Dict[str, Any]:
    if not os.path.exists(db_path):
        return {"users": {}}
    with open(db_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_users(db_path: str, data: Dict[str, Any]) -> None:
    _ensure_parent(db_path)
    tmp = db_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, db_path)


def get_user(db_path: str, username: str) -> Optional[User]:
    data = _load_users(db_path)
    u = data.get("users", {}).get(username)
    if not u:
        return None
    return User(username=username, password_hash=u["password_hash"])


def create_user(db_path: str, username: str, password: str) -> User:
    username = (username or "").strip()
    if not username:
        raise ValueError("username 不能为空")
    if len(password or "") < 6:
        raise ValueError("password 至少 6 位")

    data = _load_users(db_path)
    users = data.setdefault("users", {})
    if username in users:
        raise ValueError("用户名已存在")

    u = User(username=username, password_hash=generate_password_hash(password))
    users[username] = {"password_hash": u.password_hash}
    _save_users(db_path, data)
    return u


def verify_user(db_path: str, username: str, password: str) -> bool:
    u = get_user(db_path, username)
    if not u:
        return False
    return check_password_hash(u.password_hash, password or "")

