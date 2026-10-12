import json
import os
import runpy

from private_data import migrate_private_data
migrate_private_data()
os.environ["DD_DATA_DIR"] = "/config"
os.environ["DD_TRANSPORT_FILE"] = "/config/transport.json"
os.environ["DD_SELECTION_FILE"] = "/config/shared_entities.json"
os.environ["DD_LINK_FILE"] = "/config/link.json"

with open("/data/options.json", encoding="utf-8") as file:
    options = json.load(file)
os.environ["DD_RELAY_URL"] = options.get("relay_url", "")
os.environ["DD_TRANSPORT"] = options.get("transport", "cloud")
os.environ["DD_LOCAL_CORE_URL"] = options.get("local_core_url", "")
os.environ["DD_LOCAL_CORE_SHA256"] = options.get("local_core_sha256", "")
os.environ["DD_SHARED_ENTITIES"] = options["shared_entities"]
os.environ["HA_URL"] = "http://supervisor/core"
runpy.run_path("/app/connector.py", run_name="__main__")
