from tinydb import TinyDB, Query
from datetime import datetime

db = TinyDB('db.json')
streams_table = db.table('streams')
logs_table = db.table('logs')

def update_stream(name, url, m3u8, channel):
    streams_table.upsert({
        'name': name,
        'url': url,
        'm3u8': m3u8,
        'channel': channel,
        'fetched_at': datetime.utcnow().isoformat()
    }, Query().name == name)

def delete_stream(name):
    streams_table.remove(Query().name == name)

def get_stream(name):
    result = streams_table.get(Query().name == name)
    return result['m3u8'] if result else None

def get_all_streams():
    return {entry['name']: entry for entry in streams_table.all()}

def log_access(name, ip, cf_ip=None):
    logs_table.insert({
        'channel': name,
        'ip': ip,
        'cf_ip': cf_ip or ip,
        'timestamp': datetime.utcnow().isoformat()
    })

def get_access_log():
    return logs_table.all()
