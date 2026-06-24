import os

from flask import Flask, jsonify, render_template, request

from connectivity import check_local, check_remote

app = Flask(__name__)

INVENTORY_PATH = os.environ.get("INVENTORY_PATH", "inventory")


def parse_inventory(path):
    hosts = set()
    if not os.path.isfile(path):
        return []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("["):
                continue
            host = line.split()[0]
            if "=" not in host and ":" not in host:
                hosts.add(host)
    return sorted(hosts)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/hosts")
def api_hosts():
    path = request.args.get("inventory", INVENTORY_PATH)
    return jsonify(parse_inventory(path))


@app.route("/api/check", methods=["POST"])
def api_check():
    data = request.json or {}
    source = (data.get("source") or "localhost").strip()
    dest = (data.get("destination") or "").strip()
    port = (data.get("port") or "443").strip()

    if not dest:
        return jsonify({"success": False, "message": "Destination is required"}), 400
    if not port.isdigit() or not (1 <= int(port) <= 65535):
        return jsonify({"success": False, "message": "Port must be between 1 and 65535"}), 400

    if source in ("localhost", "127.0.0.1"):
        success, message = check_local(dest, port)
    else:
        success, message = check_remote(source, dest, port)

    return jsonify({"success": success, "message": message, "source": source, "dest": dest, "port": port})


@app.route("/api/check-all", methods=["POST"])
def api_check_all():
    data = request.json or {}
    dest = (data.get("destination") or "").strip()
    port = (data.get("port") or "443").strip()
    hosts = data.get("hosts", [])

    if not dest:
        return jsonify({"success": False, "message": "Destination is required"}), 400
    if not port.isdigit() or not (1 <= int(port) <= 65535):
        return jsonify({"success": False, "message": "Port must be between 1 and 65535"}), 400

    results = []
    for host in hosts:
        host = host.strip()
        if host in ("localhost", "127.0.0.1"):
            ok, msg = check_local(dest, port)
        else:
            ok, msg = check_remote(host, dest, port)
        results.append({"host": host, "success": ok, "message": msg})

    return jsonify(results)


if __name__ == "__main__":
    app.run(debug=True, port=5050)
