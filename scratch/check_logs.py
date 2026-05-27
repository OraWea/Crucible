import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Crucible.utils.db_manager import db_manager

logs = db_manager.get_logs(limit=50)
for log in logs:
    print(f"[{log['timestamp']}] [{log['level']}] [{log['module']}] {log['action']} - {log['detail']} (Duration: {log['duration']}s)")
