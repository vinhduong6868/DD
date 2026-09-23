import json
import os
import runpy

with open("/data/options.json", encoding="utf-8") as file:
    options = json.load(file)
os.environ["DD_RELAY_URL"] = options["relay_url"]
os.environ["DD_SHARED_ENTITIES"] = options["shared_entities"]
os.environ["HA_URL"] = "http://supervisor/core"
runpy.run_path("/app/connector.py", run_name="__main__")
