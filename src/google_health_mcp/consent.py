from html import escape
from html.parser import HTMLParser


class _ConsentForm(HTMLParser):
    """Read the SDK's client label and issued form fields without changing OAuth state."""

    def __init__(self):
        super().__init__()
        self.client_name = ""
        self.fields: dict[str, str] = {}
        self.in_client_name = False
        self.in_form = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "strong" and not self.client_name:
            self.in_client_name = True
        if tag == "form" and attributes.get("id") == "consentForm":
            self.in_form = True
        if self.in_form and tag == "input" and attributes.get("type") == "hidden":
            name = attributes.get("name")
            if name:
                self.fields[name] = attributes.get("value") or ""

    def handle_endtag(self, tag):
        if tag == "strong":
            self.in_client_name = False
        if tag == "form":
            self.in_form = False

    def handle_data(self, data):
        if self.in_client_name:
            self.client_name += data


def simplify_consent_page(html: str, privacy_policy_url: str | None) -> str:
    form = _ConsentForm()
    form.feed(html)
    if not {"txn_id", "csrf_token"} <= form.fields.keys():
        return html
    fields = "".join(
        f'<input type="hidden" name="{escape(name, quote=True)}" value="{escape(value, quote=True)}">'
        for name, value in form.fields.items()
    )
    client = escape(form.client_name or "Your assistant")
    privacy = (
        f'<a href="{escape(privacy_policy_url, quote=True)}" target="_blank" rel="noopener noreferrer">Privacy policy</a>'
        if privacy_policy_url
        else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; font-src https://googlehealth.enesdemirag.com; base-uri 'none'">
<title>Connect Google Health</title>
<style>
@font-face {{ font-family: Manrope; src: url('https://googlehealth.enesdemirag.com/fonts/Manrope.ttf') format('truetype'); font-weight: 200 800; font-display: swap; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; min-height: 100svh; display: grid; place-items: center; background: #fff; color: #24262a; font: 15px/1.65 Manrope, sans-serif; }}
main {{ width: min(100%, 420px); padding: 32px 24px; }}
.brand {{ margin: 0 0 28px; color: #6f747a; font-size: 13px; }}
h1 {{ margin: 0 0 12px; font-size: 28px; line-height: 1.3; font-weight: 600; letter-spacing: -.6px; }}
.description {{ margin: 0 0 28px; color: #6f747a; overflow-wrap: anywhere; }}
strong {{ color: #24262a; font-weight: 600; }}
.actions {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
button {{ min-height: 50px; padding: 12px 16px; border: 1px solid #24262a; border-radius: 6px; font: inherit; font-weight: 600; cursor: pointer; }}
.allow {{ background: #24262a; color: #fff; }}
.deny {{ background: #fff; color: #24262a; border-color: #e4e6e8; }}
.allow:hover {{ background: #404247; }}
.deny:hover {{ background: #f6f7f8; }}
button:focus-visible, a:focus-visible {{ outline: 2px solid #8c343c; outline-offset: 4px; }}
footer {{ margin-top: 20px; text-align: center; font-size: 12px; }}
a {{ color: #6f747a; text-underline-offset: 3px; }}
</style>
</head>
<body>
<main>
<p class="brand">HealPot · Google Health MCP</p>
<h1>Allow access?</h1>
<p class="description"><strong>{client}</strong> can read your Google Health data and share it with its AI provider.</p>
<form id="consentForm" method="POST" action="">
{fields}
<div class="actions">
<button class="allow" type="submit" name="action" value="approve">Allow</button>
<button class="deny" type="submit" name="action" value="deny">Deny</button>
</div>
</form>
<footer>{privacy}</footer>
</main>
</body>
</html>"""
