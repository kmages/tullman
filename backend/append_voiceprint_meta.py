from admin_ui import admin_bp, VOICEPRINT_TXT
from flask import jsonify
import os, datetime

@admin_bp.route("/admin/api/voiceprint_meta", methods=["GET"])
def api_voiceprint_meta():
    try:
        mtime = os.path.getmtime(VOICEPRINT_TXT)
        iso = datetime.datetime.fromtimestamp(mtime).isoformat(timespec="seconds")
        return jsonify({"ok": True, "mtime_iso": iso, "mtime": mtime})
    except Exception:
        return jsonify({"ok": True, "mtime_iso": None, "mtime": None})
