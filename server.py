# ==============================================================================
# NTTOOL KEY SERVER V2 - 2026 - FULL FEATURES
# ==============================================================================
import json
import os
import re
import secrets
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, request, jsonify

app = Flask(__name__)

# ==============================================================================
# CONFIG
# ==============================================================================
ADMIN_SECRET = "nttool_v9_admin_2026_x7k9m2a8f3b1c4d5e6f7g8h9i0j"
SALT = "NTTOOL_V9_SALT_2026_a7f3c9e1b5d2g4h6i8j0k1l2m3n4o5p6"
ADMIN_PHONE = "0325145463"

DATA_DIR = Path("server_data")
DATA_DIR.mkdir(exist_ok=True)

FREE_KEYS_FILE = DATA_DIR / "free_keys.json"
VIP_KEYS_FILE = DATA_DIR / "vip_keys.json"
BLACKLIST_FILE = DATA_DIR / "blacklist.json"
MEMBERS_FILE = DATA_DIR / "members.json"

# ==============================================================================
# HELPERS
# ==============================================================================
def load(filename, default):
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
    except: pass
    return default

def save(filename, data):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except: return False

def now_vn():
    return datetime.now()

def today_str():
    return datetime.now().strftime("%Y-%m-%d")

# ==============================================================================
# HOME
# ==============================================================================
@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "status": "ok",
        "server": "NTTOOL V9 V2",
        "version": "9.2",
        "time": now_vn().isoformat(),
    })

# ==============================================================================
# VERIFY KEY (FREE + VIP)
# ==============================================================================
@app.route("/api/verify_key", methods=["POST"])
def verify_key():
    try:
        body = request.get_json(force=True)
        device_id = (body.get("device_id") or "").strip()
        key = (body.get("key") or "").strip().upper()

        if not device_id or not key:
            return jsonify({"success": False, "message": "Thiếu thông tin"}), 200

        bl = load(BLACKLIST_FILE, {})
        if device_id in bl:
            return jsonify({"success": False, "message": "Thiết bị bị khóa"}), 200

        # CHECK VIP KEY TRƯỚC (không cần format)
        vip_db = load(VIP_KEYS_FILE, {})
        if key in vip_db:
            info = vip_db[key]
            exp_time = datetime.fromisoformat(info["expires_at"])
            if now_vn() > exp_time:
                return jsonify({"success": False, "message": "Key VIP hết hạn"}), 200

            if not info.get("used"):
                info["used"] = True
                info["activated_at"] = now_vn().isoformat()
                info["device_id"] = device_id
                save(VIP_KEYS_FILE, vip_db)

            return jsonify({
                "success": True,
                "key_type": "VIP",
                "max_logic": 100,
                "is_vip": True,
                "expires_at": info["expires_at"]
            }), 200

        # CHECK FREE KEY FORMAT
        if not re.match(r"^[0-9A-F]{8}$", key):
            return jsonify({"success": False, "message": "Key không đúng định dạng"}), 200

        free_db = load(FREE_KEYS_FILE, {})
        today = today_str()
        day_db = free_db.get(today, {})

        if key not in day_db:
            return jsonify({"success": False, "message": "Key FREE không tồn tại"}), 200

        if day_db[key].get("device_id") != device_id:
            return jsonify({"success": False, "message": "Key không thuộc thiết bị này"}), 200

        exp = now_vn().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

        return jsonify({
            "success": True,
            "key_type": "FREE",
            "max_logic": 50,
            "is_vip": False,
            "expires_at": exp.isoformat(),
        }), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 200

# ==============================================================================
# CREATE FREE KEY
# ==============================================================================
@app.route("/api/create_free_key", methods=["POST"])
def create_free_key():
    try:
        body = request.get_json(force=True)
        device_id = (body.get("device_id") or "").strip()
        if not device_id:
            return jsonify({"success": False, "message": "Thiếu device_id"}), 200

        bl = load(BLACKLIST_FILE, {})
        if device_id in bl:
            return jsonify({"success": False, "message": "Thiết bị bị khóa"}), 200

        new_key = secrets.token_hex(4).upper()

        free_db = load(FREE_KEYS_FILE, {})
        today = today_str()
        if today not in free_db:
            free_db[today] = {}
        free_db[today][new_key] = {
            "device_id": device_id,
            "created_at": now_vn().isoformat(),
        }

        for old_day in sorted(free_db.keys(), reverse=True)[7:]:
            del free_db[old_day]

        save(FREE_KEYS_FILE, free_db)

        exp = now_vn().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

        return jsonify({
            "success": True,
            "key": new_key,
            "expires_at": exp.isoformat(),
        }), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 200

# ==============================================================================
# CHECK KILL
# ==============================================================================
@app.route("/api/check_kill", methods=["GET"])
def check_kill():
    try:
        device_id = (request.args.get("device_id") or "").strip()
        if not device_id:
            return jsonify({"kill": False}), 200

        bl = load(BLACKLIST_FILE, {})
        if device_id in bl:
            return jsonify({
                "kill": True,
                "reason": "Admin đã thu hồi tool"
            }), 200

        return jsonify({"kill": False}), 200

    except Exception as e:
        return jsonify({"kill": False, "error": str(e)}), 200

# ==============================================================================
# HEARTBEAT
# ==============================================================================
@app.route("/api/heartbeat", methods=["POST"])
def heartbeat():
    try:
        body = request.get_json(force=True)
        device_id = (body.get("device_id") or "").strip()
        if not device_id:
            return jsonify({"ok": False, "reason": "Thiếu device_id"}), 200

        try:
            members_db = load(MEMBERS_FILE, {})
            now = now_vn().isoformat()
            if device_id not in members_db:
                members_db[device_id] = {
                    "device_id": device_id,
                    "member_name": body.get("member_name", "?"),
                    "phone": body.get("phone", "?"),
                    "device_name": body.get("device_name", "?"),
                    "registered_at": now,
                    "last_seen": now
                }
            else:
                if body.get("member_name"):
                    members_db[device_id]["member_name"] = body["member_name"]
                if body.get("phone"):
                    members_db[device_id]["phone"] = body["phone"]
                if body.get("device_name"):
                    members_db[device_id]["device_name"] = body["device_name"]
                members_db[device_id]["last_seen"] = now
            save(MEMBERS_FILE, members_db)
        except: pass

        return jsonify({"ok": True, "ts": now_vn().isoformat()}), 200

    except Exception as e:
        return jsonify({"ok": False, "reason": str(e)}), 200

# ==============================================================================
# REGISTER MEMBER
# ==============================================================================
@app.route("/api/register_member", methods=["POST"])
def register_member():
    try:
        body = request.get_json(force=True)
        device_id = (body.get("device_id") or "").strip()
        if not device_id:
            return jsonify({"success": False, "message": "Thiếu device_id"}), 200

        members_db = load(MEMBERS_FILE, {})
        now = now_vn().isoformat()

        members_db[device_id] = {
            "device_id": device_id,
            "member_name": body.get("member_name", "?"),
            "phone": body.get("phone", "?"),
            "device_name": body.get("device_name", "?"),
            "registered_at": members_db.get(device_id, {}).get("registered_at", now),
            "last_seen": now
        }
        save(MEMBERS_FILE, members_db)

        return jsonify({"success": True, "device_id": device_id}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 200

# ==============================================================================
# ADMIN - LIST MEMBERS
# ==============================================================================
@app.route("/api/admin/list_members", methods=["POST"])
def admin_list_members():
    try:
        body = request.get_json(force=True)
        if body.get("admin_secret") != ADMIN_SECRET:
            return jsonify({"success": False, "message": "Sai admin_secret"}), 200

        members_db = load(MEMBERS_FILE, {})
        bl = load(BLACKLIST_FILE, {})

        members_list = []
        for device_id, info in members_db.items():
            members_list.append({
                "device_id": device_id,
                "member_name": info.get("member_name", "?"),
                "phone": info.get("phone", ""),
                "device_name": info.get("device_name", ""),
                "registered_at": info.get("registered_at", ""),
                "last_seen": info.get("last_seen", ""),
                "blacklisted": device_id in bl,
            })

        members_list.sort(key=lambda x: x.get("last_seen", ""), reverse=True)

        return jsonify({
            "success": True,
            "total": len(members_list),
            "members": members_list,
        }), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 200

# ==============================================================================
# ADMIN - REVOKE DEVICE
# ==============================================================================
@app.route("/api/admin/revoke_device", methods=["POST"])
def admin_revoke_device():
    try:
        body = request.get_json(force=True)
        if body.get("admin_secret") != ADMIN_SECRET:
            return jsonify({"success": False, "message": "Sai admin_secret"}), 200

        device_id = (body.get("device_id") or "").strip()
        if not device_id:
            return jsonify({"success": False, "message": "Thiếu device_id"}), 200

        bl = load(BLACKLIST_FILE, {})
        bl[device_id] = now_vn().isoformat()
        save(BLACKLIST_FILE, bl)

        return jsonify({"success": True, "revoked": device_id}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 200

# ==============================================================================
# ADMIN - UNREVOKE DEVICE
# ==============================================================================
@app.route("/api/admin/unrevoke_device", methods=["POST"])
def admin_unrevoke_device():
    try:
        body = request.get_json(force=True)
        if body.get("admin_secret") != ADMIN_SECRET:
            return jsonify({"success": False, "message": "Sai admin_secret"}), 200

        device_id = (body.get("device_id") or "").strip()
        bl = load(BLACKLIST_FILE, {})
        if device_id in bl:
            del bl[device_id]
            save(BLACKLIST_FILE, bl)

        return jsonify({"success": True, "unrevoked": device_id}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 200

# ==============================================================================
# ADMIN - CREATE VIP
# ==============================================================================
@app.route("/api/admin/create_vip", methods=["POST"])
def admin_create_vip():
    try:
        body = request.get_json(force=True)
        if body.get("admin_secret") != ADMIN_SECRET:
            return jsonify({"success": False, "message": "Sai admin_secret"}), 200

        duration_days = int(body.get("duration_days", 30))

        new_key = f"NTTOOL_VIP_{duration_days}D_{secrets.token_hex(4).upper()}"

        vip_db = load(VIP_KEYS_FILE, {})
        exp = now_vn() + timedelta(days=duration_days)
        vip_db[new_key] = {
            "key_type": "VIP",
            "duration_days": duration_days,
            "created_at": now_vn().isoformat(),
            "expires_at": exp.isoformat(),
            "used": False,
        }
        save(VIP_KEYS_FILE, vip_db)

        return jsonify({
            "success": True,
            "key": new_key,
            "expires_at": exp.isoformat(),
        }), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 200

# ==============================================================================
# ADMIN - STATUS
# ==============================================================================
@app.route("/api/admin/status", methods=["POST"])
def admin_status():
    try:
        body = request.get_json(force=True)
        if body.get("admin_secret") != ADMIN_SECRET:
            return jsonify({"success": False, "message": "Sai admin_secret"}), 200

        free_db = load(FREE_KEYS_FILE, {})
        today = today_str()
        bl = load(BLACKLIST_FILE, {})
        vip_db = load(VIP_KEYS_FILE, {})
        members_db = load(MEMBERS_FILE, {})

        return jsonify({
            "success": True,
            "today": today,
            "free_keys_today": len(free_db.get(today, {})),
            "total_days": len(free_db),
            "blacklisted_devices": len(bl),
            "vip_keys_total": len(vip_db),
            "members_total": len(members_db),
        }), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 200

# ==============================================================================
# RUN
# ==============================================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
