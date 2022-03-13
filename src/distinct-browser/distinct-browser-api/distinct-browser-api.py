#!/usr/bin/env python3

import logging
import sys
import subprocess
import os
import shutil
import json
import base64
from threading import Thread
from functools import wraps
from socket import socket
from flask import Flask
from flask_cors import CORS

logger = logging.getLogger(__name__)

class BrowserAPI(Thread):

    def __init__(self):
        logger.info("Initializing browser api thread")
        super(BrowserAPI, self).__init__()
        self.daemon = True

        self.app = Flask(__name__)
        self.app.url_map.strict_slashes = False # allow trailing slashes
        CORS(self.app, resources={r"/api/*": {"origins": "*"}}) # enable CORS
        self.register_routes()

        self.browsers_by_handler = {} # {handler_uuid: [Pprocess, ...]}
        self.proxies_by_handler = {} # {handler_uuid: Pprocess, ...}

    def run(self):
        logger.info("Starting browser api thread")

        listen_host = "0.0.0.0"
        listen_port = 80

        logger.info(f"Starting webserver on {listen_host}:{listen_port}")
        self.app.run(host=listen_host, port=listen_port)

    def register_routes(self):
        logger.info("Registering routes for the browser api's webserver")

        self.app.add_url_rule(
            "/api/browsers", view_func=self.api_browsers, methods=["GET"]
        )
        self.app.add_url_rule(
            "/api/browsers/<handler_uuid>", view_func=self.api_browsers_handler, methods=["GET"]
        )
        self.app.add_url_rule(
            "/api/browsers/<handler_uuid>/start", view_func=self.api_browsers_start, methods=["POST"]
        )
        self.app.add_url_rule(
            "/api/browsers/<handler_uuid>/stop", view_func=self.api_browsers_stop, methods=["POST"]
        )
        self.app.add_url_rule(
            "/api/browsers/<handler_uuid>/profile", view_func=self.api_browsers_profile, methods=["GET"]
        )

    """ Routines """

    @staticmethod
    def get_free_port():
        with socket() as s:
            s.bind(("", 0))
            return s.getsockname()[1]

    def setup_chrome_extensions(self, handler_uuid, ace_ext_config=None):
        """ Setup chrome extensions for handler """
        distinct_ext_for_handler = f"/app/data/chrome-extensions/distinct-chrome-extension_{handler_uuid}"
        ace_ext_for_handler = f"/app/data/chrome-extensions/ace-chrome-extension_{handler_uuid}"
        if os.path.exists(distinct_ext_for_handler):
            shutil.rmtree(distinct_ext_for_handler)
        shutil.copytree("/app/distinct-chrome-extension", distinct_ext_for_handler)
        if os.path.exists(ace_ext_for_handler):
            shutil.rmtree(ace_ext_for_handler)
        shutil.copytree("/app/ace-chrome-extension", ace_ext_for_handler)

        # Configure distinct chrome extension
        with open(f"{distinct_ext_for_handler}/config/config.json", "w") as f:
            f.write(json.dumps({
                "core_endpoint": "http://distinct-core",
                "handler_uuid": handler_uuid
            }))

        # TODO: Configure ace chrome extension

        return (
            distinct_ext_for_handler,
            ace_ext_for_handler
        )

    def start_proxy(self, handler_uuid):
        logger.info(f"Starting proxy with handler uuid {handler_uuid}")
        # stdout = f"/app/data/chrome-proxy/proxy-stdout_{handler_uuid}.log"
        # stderr = f"/app/data/chrome-proxy/proxy-stderr_{handler_uuid}.log"
        stream_path = f"/app/data/chrome-proxy/proxy-stream_{handler_uuid}.dump"
        hardump_path = f"/app/data/chrome-proxy/proxy-hardump_{handler_uuid}.har"

        listen_host = "127.0.0.1"
        listen_port = self.get_free_port()

        p = subprocess.Popen([
            "mitmdump",
            "--listen-host", listen_host,
            "--listen-port", str(listen_port),
            "--save-stream-file", stream_path,
            "--quiet",
            "--scripts", "/app/mitmproxy/har.py",
            "--scripts", "/app/mitmproxy/redirects.py",
            "--set", f"hardump={hardump_path}"
        ])
        self.proxies_by_handler[handler_uuid] = p

        logger.info(f"Started proxy on {listen_host}:{listen_port}")
        return (
            listen_host,
            listen_port,
            p
        )

    def stop_proxy(self, handler_uuid):
        logger.info(f"Stopping proxy with handler uuid {handler_uuid}")
        self.proxies_by_handler[handler_uuid].terminate()
        del self.proxies_by_handler[handler_uuid]

    def start_browser(self, handler_uuid, start_url=None):
        """ Start new browser process for handler uuid """
        logger.info(f"Starting browser with handler uuid {handler_uuid}")

        # Setup chrome extensions
        exts = self.setup_chrome_extensions(handler_uuid)

        # Start proxy
        proxy_host, proxy_port, proxy = self.start_proxy(handler_uuid)

        # Start browser process
        gui_env = os.environ.copy()
        gui_env["DISPLAY"] = ":0.0"
        p = subprocess.Popen([
            "/chromium/latest/chrome",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-web-security",
            "--ignore-certificate-errors",
            "--allow-running-insecure-content",
            "--disable-site-isolation-trials",
            "--disable-http2",
            f"--proxy-server={proxy_host}:{proxy_port}",
            f"--proxy-bypass-list=distinct-core",
            f"--load-extension={','.join(exts)}",
            f"--user-data-dir=/app/data/chrome-profiles/chrome-profile_{handler_uuid}",
            start_url if start_url else "about:blank"
        ], env=gui_env)

        # Save browser process in list of browsers
        if handler_uuid not in self.browsers_by_handler:
            self.browsers_by_handler[handler_uuid] = [p]
        else:
            self.browsers_by_handler[handler_uuid].append(p)

    def stop_browser(self, handler_uuid):
        """ Stop browser process for handler uuid """
        logger.info(f"Stopping browser with handler uuid {handler_uuid}")
        self.browsers_by_handler[handler_uuid][-1].terminate()

        # Cleanup chrome extensions for handler
        distinct_ext_for_handler = f"/app/chrome-extensions/distinct-chrome-extension-{handler_uuid}"
        ace_ext_for_handler = f"/app/chrome-extensions/ace-chrome-extension-{handler_uuid}"
        if os.path.exists(distinct_ext_for_handler):
            shutil.rmtree(distinct_ext_for_handler)
        if os.path.exists(ace_ext_for_handler):
            shutil.rmtree(ace_ext_for_handler)

        # Stop proxy
        self.stop_proxy(handler_uuid)

    """ Wrappers """

    def check_browser_existence(func):
        """ Error when there is not a single browser for handler uuid """
        @wraps(func)
        def wrapper(*args, **kwargs):
            browserapi = args[0]
            handler_uuid = kwargs["handler_uuid"]
            if handler_uuid in browserapi.browsers_by_handler:
                return func(*args, **kwargs)
            else:
                logger.error(f"Browser with handler uuid {handler_uuid} does not exist")
                body = {"success": False, "error": f"Browser with handler uuid {handler_uuid} does not exist", "data": None}
                return body
        return wrapper

    def check_browser_running(func):
        """ Error when there is no browser running for handler uuid """
        @wraps(func)
        def wrapper(*args, **kwargs):
            browserapi = args[0]
            handler_uuid = kwargs["handler_uuid"]
            if (
                handler_uuid in browserapi.browsers_by_handler
                and browserapi.browsers_by_handler[handler_uuid][-1]
                and browserapi.browsers_by_handler[handler_uuid][-1].poll() is None
            ):
                return func(*args, **kwargs)
            else:
                logger.error(f"Browser with handler uuid {handler_uuid} is not running")
                body = {"success": False, "error": f"Browser with handler uuid {handler_uuid} is not running", "data": None}
                return body
        return wrapper

    def check_browser_not_running(func):
        """ Error when there is a browser running for handler uuid """
        @wraps(func)
        def wrapper(*args, **kwargs):
            browserapi = args[0]
            handler_uuid = kwargs["handler_uuid"]
            if (
                (
                    # There is no browser for handler uuid
                    handler_uuid not in browserapi.browsers_by_handler
                ) or (
                    # There is a browser for handler uuid but it is not running
                    handler_uuid in browserapi.browsers_by_handler
                    and browserapi.browsers_by_handler[handler_uuid][-1]
                    and browserapi.browsers_by_handler[handler_uuid][-1].poll() is not None
                )
            ):
                return func(*args, **kwargs)
            else:
                logger.error(f"Browser with handler uuid {handler_uuid} is already running")
                body = {"success": False, "error": f"Browser with handler uuid {handler_uuid} is already running", "data": None}
                return body
        return wrapper

    """ Webserver API Routes """

    # GET /api/browsers/
    def api_browsers(self):
        body = {"success": True, "error": None, "data": []}
        for uuid, processes in self.browsers_by_handler.items():
            data = {"uuid": uuid, "browsers": []}
            for process in processes:
                data["browsers"].append({
                    "pid": process.pid,
                    "returncode": process.poll(),
                    "args": process.args
                })
            body["data"].append(data)
        return body

    # GET /api/browsers/<handler_uuid>/
    def api_browsers_handler(self, handler_uuid):
        body = {
            "success": True,
            "error": None,
            "data": {
                "uuid": handler_uuid,
                "browsers": []
            }
        }
        if handler_uuid in self.browsers_by_handler:
            for process in self.browsers_by_handler[handler_uuid]:
                body["data"]["browsers"].append({
                    "pid": process.pid,
                    "returncode": process.poll(),
                    "args": process.args
                })
        return body

    # POST /api/browsers/<handler_uuid>/start
    @check_browser_not_running
    def api_browsers_start(self, handler_uuid):
        self.start_browser(handler_uuid)
        body = {"success": True, "error": None, "data": None}
        return body

    # POST /api/browsers/<handler_uuid>/stop
    @check_browser_existence
    @check_browser_running
    def api_browsers_stop(self, handler_uuid):
        self.stop_browser(handler_uuid)
        body = {"success": True, "error": None, "data": None}
        return body

    # GET /api/browsers/<handler_uuid>/profile
    @check_browser_existence
    def api_browsers_profile(self, handler_uuid):
        profile_path = f"/app/data/chrome-profiles/chrome-profile_{handler_uuid}"
        profile_zip_path = f"/app/data/chrome-profiles/chrome-profile_{handler_uuid}.zip"

        if os.path.isfile(profile_zip_path):
            os.remove(profile_zip_path)

        if os.path.exists(profile_path):
            shutil.make_archive(profile_path, "zip", profile_path)
            with open(profile_zip_path, "rb") as f:
                profile_zip_bytes = f.read()
                profile_zip_b64 = base64.b64encode(profile_zip_bytes).decode("utf8")
                body = {"success": True, "error": None, "data": profile_zip_b64}
                return body
        else:
            body = {"success": False, "error": f"Profile for handler uuid {handler_uuid} does not exist", "data": None}
            return body

def main():
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    browser_api = BrowserAPI()
    browser_api.start()
    browser_api.join()


if __name__ == "__main__":
    main()
