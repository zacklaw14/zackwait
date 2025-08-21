#!/usr/bin/env python3
"""
Send a WhatsApp message to an individual using the official WhatsApp Cloud API.

Usage (env vars):
  export WHATSAPP_ACCESS_TOKEN=EAA...  # Permanent system user token or app token
  export WHATSAPP_PHONE_NUMBER_ID=123456789012345
  python /workspace/whatsapp_send.py --to 15551234567 --text "Hello from API"

Usage (flags only):
  python /workspace/whatsapp_send.py \
    --token EAA... \
    --from-id 123456789012345 \
    --to 15551234567 \
    --text "Hello from API"

Notes:
- Phone numbers must be in E.164 format (e.g., 15551234567).
- Ensure your business phone number and recipient number are WhatsApp-enabled and comply with WhatsApp policies.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict
from dataclasses import dataclass
from urllib import request as urlrequest
from urllib import error as urlerror


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send a WhatsApp message to an individual using the Cloud API",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--token",
        default=os.getenv("WHATSAPP_ACCESS_TOKEN"),
        help="WhatsApp Cloud API access token (env: WHATSAPP_ACCESS_TOKEN)",
    )
    parser.add_argument(
        "--from-id",
        dest="from_id",
        default=os.getenv("WHATSAPP_PHONE_NUMBER_ID"),
        help="Business phone number ID (env: WHATSAPP_PHONE_NUMBER_ID)",
    )
    parser.add_argument(
        "--to",
        required=True,
        help="Recipient phone in E.164 format, e.g. 15551234567",
    )
    parser.add_argument(
        "--text",
        required=True,
        help="Text body to send",
    )
    parser.add_argument(
        "--api-version",
        default="v20.0",
        help="Facebook Graph API version to use",
    )
    return parser.parse_args()


def validate_required(value: str | None, name: str) -> str:
    if not value:
        print(
            f"Missing required {name}. Provide --{name.replace('_', '-')} or set the appropriate environment variable.",
            file=sys.stderr,
        )
        sys.exit(2)
    return value


def build_payload(recipient: str, text_body: str) -> Dict[str, Any]:
    return {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "text",
        "text": {"body": text_body},
    }


@dataclass
class SimpleResponse:
    status_code: int
    text: str
    headers: Dict[str, Any]

    def json(self) -> Dict[str, Any]:
        return json.loads(self.text)


def send_message(api_version: str, phone_number_id: str, token: str, payload: Dict[str, Any]) -> SimpleResponse:
    url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(url=url, data=data_bytes, headers=headers, method="POST")
    try:
        with urlrequest.urlopen(req, timeout=30) as resp:
            body_bytes = resp.read()
            body_text = body_bytes.decode("utf-8", errors="replace")
            return SimpleResponse(status_code=getattr(resp, "status", 200), text=body_text, headers=dict(resp.headers))
    except urlerror.HTTPError as http_err:
        error_text = (http_err.read() or b"").decode("utf-8", errors="replace")
        return SimpleResponse(status_code=http_err.code, text=error_text, headers=dict(http_err.headers or {}))
    except urlerror.URLError as net_err:
        raise net_err


def main() -> None:
    args = parse_args()
    access_token = validate_required(args.token, "token")
    from_id = validate_required(args.from_id, "from_id")
    recipient = validate_required(args.to, "to")
    text_body = validate_required(args.text, "text")

    payload = build_payload(recipient=recipient, text_body=text_body)
    try:
        response = send_message(
            api_version=args.api_version,
            phone_number_id=from_id,
            token=access_token,
            payload=payload,
        )
    except urlerror.URLError as request_error:
        print(f"Network error: {request_error}", file=sys.stderr)
        sys.exit(1)

    if 200 <= response.status_code < 300:
        try:
            body = response.json()
        except ValueError:
            print("Message sent (no JSON body returned).", file=sys.stderr)
            print(response.text)
            return
        message_ids = body.get("messages") or []
        if message_ids:
            print(f"Sent. Message ID: {message_ids[0].get('id')}")
        else:
            print("Sent.")
        return

    # Non-2xx: print a helpful error
    try:
        error_body = response.json()
    except ValueError:
        error_body = {"raw": response.text}
    print(
        "Failed to send WhatsApp message:",
        json.dumps({
            "status": response.status_code,
            "response": error_body,
        }, indent=2),
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()

