import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE_PATH = os.environ.get(
    "NEXUS_DATABASE",
    os.path.join(BASE_DIR, "nexus.db"),
)

JSON_SORT_KEYS = False
