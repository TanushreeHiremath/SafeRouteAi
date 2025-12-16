from pymongo import MongoClient
from config import Config

# Connect to MongoDB
client = MongoClient(Config.MONGO_URI)

# Get database (never use truth-check on a database object)
db = client.get_default_database()

# If database is None, manually choose one
if db is None:
    db = client["saferoute_ai"]  # you can rename if needed

# Collections
users_col = db["users"]
feedback_col = db["feedback"]
crime_segments_col = db["crime_segments"]
