from tinydb import TinyDB, Query
from config import DB_PATH

db = TinyDB(DB_PATH)
Stream = Query()

def init_db():
    pass  # TinyDB auto-creates the file

def update_stream(name, url, m3u8):
    db.upsert({'name': name, 'url': url, 'm3u8': m3u8}, Stream.name == name)

def get_stream(name):
    result = db.search(Stream.name == name)
    return result[0]['m3u8'] if result else None
