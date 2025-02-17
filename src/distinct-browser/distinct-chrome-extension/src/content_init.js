/**
 * This content script contains the code that is executed first on the website.
 * It is executed before any other extension code and before the website's code.
 * It creates useful helper functions that are used by other content scripts.
 * Also, it saves the "original" APIs that are overwritten in other content scripts.
 */

let content_init = async (configURL) => {

    /* Parse and return URL query parameters */
    function query_params() {
        let params = {};
        location.search.substr(1).split("&").forEach((keyval) => {
            if (keyval == "") return;
            let keyvalsplitted = keyval.split("=");
            let key = decodeURIComponent(keyvalsplitted[0]);
            let val = decodeURIComponent(keyvalsplitted[1]);
            params[key] = val;
        });
        return params;
    }

    /* Parse and return URL hash parameters */
    function hash_params() {
        let params = {};
        location.hash.substr(1).split("&").forEach((keyval) => {
            if (keyval == "") return;
            let keyvalsplitted = keyval.split("=");
            let key = decodeURIComponent(keyvalsplitted[0]);
            let val = decodeURIComponent(keyvalsplitted[1]);
            params[key] = val;
        });
        return params;
    }

    /* Get the HTML markup of the current window */
    function html() {
        let docelement = document.documentElement.cloneNode(true);

        // Remove all inline scripts of chrome extension
        let extensionscripts = docelement.getElementsByClassName("chromeextension");
        while (extensionscripts[0]) {
            extensionscripts[0].parentNode.removeChild(extensionscripts[0]);
        }

        // Remove all inline CSS stylesheets
        let stylesheets = docelement.getElementsByTagName("style");
        while(stylesheets[0]) {
            stylesheets[0].parentNode.removeChild(stylesheets[0]);
        }

        return docelement.outerHTML;
    }

    /* Creates a json object including fields in the form */
    function form2json(form) {
        const data = new FormData(form);
        return Array.from(data.keys()).reduce((result, key) => {
            if (result[key]) {
                result[key] = data.getAll(key);
                return result;
            }
            result[key] = data.get(key);
            return result;
        }, {});
    };

    /**
     * Algorithm 1: Determine window hierarchy
     * Idea: Determine the relation of the frame to the primary window.
     * Example: "top.popups[0].frames[0]" represents the first iframe embedded on the first popup
     * that is opened by the primary window.
     */
    function hierarchy(target) {
		var path = "";
        function go_up(current) {
			if (current.parent !== current) {
                // Parent is set -> I am an iframe.
                // Which child iframe am I?
				for (let i = 0; i < current.parent.frames.length; i++) {
					if (current.parent.frames[i] === current) {
						path = `frames[${i}]` + (path.length ? "." : "") + path;
					}
				}
				go_up(current.parent, path);
			} else if (current.opener) {
				// Opener is set -> I am a popup.
                // Which child popup am I?
                for (let i = 0; i < current.opener._sso._popups.length; i++) {
                    if (current.opener._sso._popups[i] === current) {
                        path = `popups[${i}]` + (path.length ? "." : "") + path;
                    }
                }
                go_up(current.opener, path);
			} else {
                // We reached the top -> we are the primary window.
                path = "top" + (path.length ? "." : "") + path;
            }
		}
		go_up(target);
		return path;
	}

    /* Send a postMessage to all frames in current execution context */
    function postMessageAll(message) {
		function go_down(current) {
			for (let i = 0; i < current.frames.length; i++) {
				// Child
				current.frames[i].postMessage(message, "*");
				go_down(current.frames[i]);
			}
			for (let i = 0; i < current._sso._popups.length, current._sso._popups[i].closed === false; i++) {
				// Popup
				current._sso._popups[i].postMessage(message, "*");
				go_down(current._sso._popups[i]);
			}
		}
		function go_up(current) {
			if (current.parent !== current) {
				// Parent
				current.parent.postMessage(message, "*");
				// Enumerate Popups
				for (let i = 0; i < current.parent._sso._popups.length, current.parent._sso._popups[i].closed === false; i++) {
					current.parent._sso._popups[i].postMessage(message, "*");
					go_down(current.parent._sso._popups[i]);
				}
				// Enumerate Frames
				for (let i = 0; i < current.parent.frames.length; i++) {
					if (current.parent.frames[i] !== current) {
						// Sibling Frame
						current.parent.frames[i].postMessage(message, "*");
						go_down(current.parent.frames[i]);
					}
				}
				go_up(current.parent);
			} else {
				// We reached the top
				if (current.opener) {
					// Opener
					current.opener.postMessage(message, "*");
                    // Enumerate Popups
					for (let i = 0; i < current.opener._sso._popups.length, current.opener._sso._popups[i].closed === false; i++) {
						if (current.opener._sso._popups[i] !== current) {
                            // Sibling Popup
                            current.opener._sso._popups[i].postMessage(message, "*");
						    go_down(current.opener._sso._popups[i]);
                        }
					}
                    // Enumerate Frames
                    for (let i = 0; i < current.opener.frames.length; i++) {
                        current.opener.frames[i].postMessage(message, "*");
                        go_down(current.opener.frames[i]);
                    }
					go_up(current.opener);
				}
			}
		}
		window.postMessage(message, "*");
		go_down(window);
		go_up(window);
	}

    /* Send in-browser events to python backend */
    async function event(key, val) {
        // Where did this event trigger?
        val["timestamp"] = Date.now();
        val["hierarchy"] = _sso._hierarchy(self);
        val["href"] = location.href;
        val["hrefparts"] = {
            "protocol": location.protocol,
            "hostname": location.hostname,
            "port": location.port,
            "pathname": location.pathname,
            "query": _sso._qparams,
            "hash": _sso._hparams,
            "origin": location.origin
        }

        // Load config if not loaded previously
        if (!_sso._config) {
            let config = await fetch(window._sso._configURL);
            window._sso._config = await config.json();
        }

        // We are working with a promise
        // This allows us to either send event and don't care of whether it was
        // received by the event server or we can send the event and wait for it
        // to be acknowledged by the event server
        return new Promise((resolve, reject) => {

            try {
                var body = JSON.stringify({"report": {"key": key, "val": val}}, (key, val) => {
                    return typeof val === "undefined" ? null : val;
                });
            } catch {
                console.info(
                    `%c[distinct]%c\nkey=${key}\nval=${val}`,
                    "color:red;", ""
                );
                reject("Failed to stringify event into json");
                return;
            }

            // Send request to event server and check response
            // Event format: {"event": {"key": "...", "val": {...}}}
            fetch(`${_sso._config["core_endpoint"]}/api/handlers/${_sso._config["handler_uuid"]}/dispatch`, {
                method: "POST",
                mode: "cors",
                headers: {
                    "Content-Type": "application/json"
                },
                body: body
            }).then(r => r.json()).then(r => {

                // Resolve if event was successfully received by event server
                // and reject if event server failed to receive event
                if (r.success) {
                    console.info(
                        `%c[distinct]%c\nkey=${key}\nval=${JSON.stringify(val)}`,
                        "color:green;", ""
                    );
                    resolve();
                } else {
                    console.info(
                        `%c[distinct]%c\nkey=${key}\nval=${JSON.stringify(val)}`,
                        "color:red;", ""
                    );
                    reject("Event server failed to receive event");
                }

            }).catch(e => {
                console.info(
                    `%c[distinct]%c\nkey=${key}\nval=${JSON.stringify(val)}`,
                    "color:red;", ""
                );
                reject(e);
            });

        });

    }

    /* Global access */

    window._sso = {};

    /* Helper functions */

    window._sso._qparams = query_params();
    window._sso._hparams = hash_params();
    window._sso._html = html;
    window._sso._form2json = form2json;
    window._sso._hierarchy = hierarchy;
    window._sso._postMessageAll = postMessageAll;
    window._sso._event = event;

    window._sso._configURL = configURL;

    /* Function Wrappers */

    window._sso._postMessage = window.postMessage.bind(window);
    window._sso._addEventListener = window.addEventListener.bind(window);
    window._sso._removeEventListener = window.removeEventListener.bind(window);
    window._sso._onmessage = window.onmessage;
    window._sso._CustomEvent = window.CustomEvent;
    window._sso._dispatchEvent = window.dispatchEvent.bind(window);
    window._sso._MessageChannel = window.MessageChannel;
    window._sso._BroadcastChannel = window.BroadcastChannel;

    window._sso._open = window.open.bind(window);
    window._sso._close = window.close.bind(window);
    window._sso._closed_get = Object.getOwnPropertyDescriptor(window, "closed").get.bind(window);

    window._sso._xmlhttprequest_open = window.XMLHttpRequest.prototype.open;

    console.info("content_init.js initialized");
}

let configURL = chrome.runtime.getURL("config/config.json");
let content_init_script = document.createElement("script");
content_init_script.classList.add("chromeextension");
content_init_script.textContent = `(` + content_init.toString() + `)(${JSON.stringify(configURL)})`;
document.documentElement.prepend(content_init_script);
