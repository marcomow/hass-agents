"""Patch nanobot WebUI files for Home Assistant ingress compatibility.

Home Assistant's ingress proxy serves add-on UIs at
``/api/hassio_ingress/<token>/``. The nanobot WebUI uses absolute paths
(``/assets/...``, ``/webui/bootstrap``, etc.) which resolve to the HA root
instead of going through the ingress proxy.  This script patches the
installed nanobot package to fix that.

Run once after ``pip install nanobot-ai``.
"""

import re
import sys
from pathlib import Path

NANOBOT_ROOT = None
for candidate in sys.path:
    p = Path(candidate) / "nanobot"
    if (p / "webui" / "ws_http.py").is_file():
        NANOBOT_ROOT = p
        break

if NANOBOT_ROOT is None:
    print("[ingress_fix] ERROR: could not locate nanobot package", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# 1. Patch index.html — convert absolute asset paths to relative and inject
#    an ingress-aware fetch/WebSocket wrapper.
# ---------------------------------------------------------------------------

INGRESS_SCRIPT = r"""<script>
(function(){
  var m=window.location.pathname.match(/^(\/api\/hassio_ingress\/[^\/]+)\//);
  if(!m)return;
  var b=m[1];
  var F=window.fetch;
  window.fetch=function(u,o){
    if(typeof u==="string"&&u.startsWith("/")&&!u.startsWith("//"))u=b+u;
    return F.call(this,u,o);
  };
  var W=window.WebSocket;
  function PatchedWS(u,p){
    if(typeof u==="string"){
      try{
        var parsed=new URL(u);
        if(parsed.pathname==="/"||parsed.pathname==="")parsed.pathname=b+"/";
        u=parsed.toString();
      }catch(e){}
    }
    if(p!==undefined)return new W(u,p);
    return new W(u);
  }
  PatchedWS.prototype=W.prototype;
  PatchedWS.CONNECTING=W.CONNECTING;
  PatchedWS.OPEN=W.OPEN;
  PatchedWS.CLOSING=W.CLOSING;
  PatchedWS.CLOSED=W.CLOSED;
  window.WebSocket=PatchedWS;
})();
</script>"""

index_path = NANOBOT_ROOT / "web" / "dist" / "index.html"

if not index_path.is_file():
    print(f"[ingress_fix] WARNING: {index_path} not found, skipping HTML patch",
          file=sys.stderr)
else:
    html = index_path.read_text(encoding="utf-8")

    # Convert absolute asset/brand paths to relative.
    html = html.replace('href="/brand/', 'href="brand/')
    html = html.replace('href="/assets/', 'href="assets/')
    html = html.replace('src="/assets/', 'src="assets/')

    # Inject the ingress wrapper right before </head> so it runs before
    # the main app script.
    if "hassio_ingress" not in html:
        html = html.replace("</head>", INGRESS_SCRIPT + "\n</head>")

    index_path.write_text(html, encoding="utf-8")
    print(f"[ingress_fix] Patched {index_path}")


# ---------------------------------------------------------------------------
# 2. Patch ws_http.py — make _bootstrap_ws_url include X-Ingress-Path.
# ---------------------------------------------------------------------------

ws_http_path = NANOBOT_ROOT / "webui" / "ws_http.py"

if not ws_http_path.is_file():
    print(f"[ingress_fix] WARNING: {ws_http_path} not found, skipping WS patch",
          file=sys.stderr)
else:
    src = ws_http_path.read_text(encoding="utf-8")

    # The original method builds ``f"{scheme}://{host}{expected_path}"``.
    # We insert two lines before the return to check X-Ingress-Path and
    # prepend it to expected_path.
    OLD_RETURN = (
        '        return f"{scheme}://{host}{expected_path}"'
    )
    NEW_RETURN = (
        '        ingress_path = _case_insensitive_header(headers, "X-Ingress-Path")\n'
        '        if ingress_path:\n'
        '            expected_path = ingress_path.rstrip("/") + expected_path\n'
        '        return f"{scheme}://{host}{expected_path}"'
    )

    if "X-Ingress-Path" not in src and OLD_RETURN in src:
        src = src.replace(OLD_RETURN, NEW_RETURN, 1)
        ws_http_path.write_text(src, encoding="utf-8")
        print(f"[ingress_fix] Patched {ws_http_path}")
    elif "X-Ingress-Path" in src:
        print(f"[ingress_fix] {ws_http_path} already patched")
    else:
        print(f"[ingress_fix] WARNING: could not find patch target in {ws_http_path}",
              file=sys.stderr)
