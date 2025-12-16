from dataclasses import dataclass
from datetime import datetime
from bson import ObjectId

@dataclass
class User:
    id: ObjectId
    email: str
    name: str
    password_hash: bytes
    created_at: datetime
