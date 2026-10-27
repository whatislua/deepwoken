"""Share your own HP % with friends who also run Elgansito Demolisher Macro.

Everyone in a party uses the same party code. Each app publishes its own
username + HP to a public MQTT relay (broker) and listens for the others.
Messages are encrypted with a key made from the party code, and the topic
name is a hash of it, so people without the code can't find or read them.
"""
import base64
import hashlib
import json
import secrets
import threading
import time
from collections import deque

import certifi
import paho.mqtt.client as mqtt
from cryptography.fernet import Fernet, InvalidToken

STALE_AFTER = 6.0   # seconds without an update before a friend shows as offline
SEND_EVERY = 0.4    # how often your HP is sent while it changes
HEARTBEAT = 3.0     # resend even if unchanged, so friends know you're online
CHAT_MAX = 200      # longest party message
CHAT_GAP = 0.6      # seconds between your messages, so nobody floods the party


def job_hash(job):
    return hashlib.sha256(job.encode()).hexdigest()[:12] if job else None


def new_code():
    return secrets.token_urlsafe(9)


def clean_text(text):
    """One line of plain text, no control characters, at most CHAT_MAX long."""
    text = "".join(ch if ch.isprintable() else " " for ch in str(text or ""))
    return " ".join(text.split())[:CHAT_MAX]


def _keys(code):
    # (Prefix kept from the app's old name so all versions can still talk to each other.)
    digest = hashlib.sha256(("screenmacro-party:" + code).encode()).digest()
    topic = "screenmacro/party/" + hashlib.sha256(digest).hexdigest()[:24]
    return topic, Fernet(base64.urlsafe_b64encode(digest))


class PartyLink:
    def __init__(self, log):
        self.log = log
        self.members = {}   # username -> {"hp": int|None, "t": time}
        self.status = "off"
        self.client = None
        self.settings = None
        self.lock = threading.Lock()
        self._last_sent = (None, 0.0)
        self.chat = deque(maxlen=60)   # (time, name, text, mine)
        self.on_chat = None            # called with (name, text) when a friend sends a message
        self._chat_sent = 0.0

    def configure(self, cfg):
        """(Re)connect when the party settings change; disconnect when turned off."""
        settings = (cfg.get("enabled"), cfg.get("code", ""), cfg.get("username", "").strip(),
                    cfg.get("broker", "broker.emqx.io"), int(cfg.get("port", 8883)))
        if settings == self.settings:
            return
        self.settings = settings
        self.stop()
        enabled, code, user, broker, port = settings
        if not enabled:
            self.status = "off"
            return
        if not code or not user:
            self.status = "needs your Roblox username and a party code"
            return
        self.topic, self.fernet = _keys(code)
        # Messages go on their own topic, so older versions (HP only) never see them.
        self.chat_topic = self.topic + "/chat"
        self.username = user
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"sm-{secrets.token_hex(6)}")
        if port == 8883:
            client.tls_set(ca_certs=certifi.where())
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        client.reconnect_delay_set(1, 30)
        self.client = client
        self.status = f"connecting to {broker}..."
        try:
            client.connect_async(broker, port, keepalive=30)
            client.loop_start()
        except Exception as e:
            self.status = f"can't connect: {e}"

    def stop(self):
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass
        self.client = None
        with self.lock:
            self.members.clear()

    def _on_connect(self, client, userdata, flags, rc, props=None):
        if rc == 0 or str(rc) == "Success":
            client.subscribe([(self.topic, 0), (self.chat_topic, 1)])
            self.status = "connected"
            self.log("party: connected")
        else:
            self.status = f"refused: {rc}"

    def _on_disconnect(self, client, userdata, flags, rc, props=None):
        if self.client is client:
            self.status = "reconnecting..."

    def _on_message(self, client, userdata, msg):
        try:
            data = json.loads(self.fernet.decrypt(msg.payload, ttl=60))
        except (InvalidToken, ValueError):
            return  # someone else's message, or tampered
        name = str(data.get("u", ""))[:40]
        if not name or name.lower() == self.username.lower():
            return
        if msg.topic == self.chat_topic:
            text = clean_text(data.get("m"))
            if text:
                self.chat.append((time.time(), name, text, False))
                if self.on_chat:
                    self.on_chat(name, text)
            return
        hp = data.get("hp")
        with self.lock:
            self.members[name] = {"hp": hp if isinstance(hp, int) and 0 <= hp <= 100 else None, "t": time.time(),
                                  "srv": str(data.get("srv") or "")[:40] or None, "job": data.get("job"),
                                  "reg": str(data.get("reg") or "")[:40] or None, "pvp": bool(data.get("pvp")),
                                  "cnt": data.get("cnt") if isinstance(data.get("cnt"), int) else None}

    def publish(self, hp, server=None, job=None, region=None, combat=False, count=None):
        """Send your HP (int 0-100, or None when it can't be read), plus which server you're in."""
        if not self.client or self.status != "connected":
            return
        now = time.time()
        last, last_t = self._last_sent
        state = (hp, server, job, region, combat, count)
        if (state == last and now - last_t < HEARTBEAT) or now - last_t < SEND_EVERY:
            return
        self._last_sent = (state, now)
        # The server id is hashed: friends can tell if you're in the same server without seeing it.
        token = self.fernet.encrypt(json.dumps({"u": self.username, "hp": hp, "srv": server, "job": job_hash(job),
                                                "reg": region, "pvp": combat, "cnt": count}).encode())
        self.client.publish(self.topic, token, qos=0)

    def send_chat(self, text):
        """Send a message to everyone with the party code. Returns None, or why it couldn't be sent."""
        text = clean_text(text)
        if not text:
            return "type a message first"
        if not self.client or self.status != "connected":
            return "not connected to the party - turn on Share with friends"
        now = time.time()
        if now - self._chat_sent < CHAT_GAP:
            return "slow down a little"
        self._chat_sent = now
        token = self.fernet.encrypt(json.dumps({"u": self.username, "m": text}).encode())
        self.client.publish(self.chat_topic, token, qos=1)
        self.chat.append((now, self.username, text, True))
        return None

    def snapshot(self, friends):
        """[{name, hp, online, server, job, region, combat, count}] for the friends list (or everyone)."""
        now = time.time()
        with self.lock:
            members = dict(self.members)
        wanted = [f.strip() for f in friends if f.strip()]
        names = wanted or sorted(members, key=str.lower)
        out = []
        for name in names:
            m = next((v for k, v in members.items() if k.lower() == name.lower()), None)
            online = bool(m) and now - m["t"] < STALE_AFTER
            shown = next((k for k in members if k.lower() == name.lower()), name)
            m = m if online else {}
            out.append({"name": shown, "hp": m.get("hp"), "online": online, "server": m.get("srv"),
                        "job": m.get("job"), "region": m.get("reg"), "combat": m.get("pvp", False),
                        "count": m.get("cnt")})
        return out
