import argparse
import json
import logging
import sys
import time
import urllib.request
import urllib.error
from typing import Dict, List, Optional

# Constanten
API_BASE_URL = "https://mijn.host/api/v2"
DEFAULT_TTL = 3600
USER_AGENT = "Python-DDNS-Client/1.0"

# Logging configureren
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)


def make_request(
    url: str,
    method: str = "GET",
    headers: Optional[Dict] = None,
    data: Optional[bytes] = None,
) -> Optional[Dict]:
    """Een generieke functie om HTTP-verzoeken te doen met urllib."""
    headers = headers or {}
    headers["User-Agent"] = USER_AGENT
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status >= 400:
                logging.error(f"Fout bij verzoek naar {url}: {response.status} {response.reason}")
                return None
            
            # Voor PUT requests is er geen body in de response
            if method.upper() == 'PUT':
                return {"success": True}

            response_body = response.read().decode("utf-8")
            return json.loads(response_body)

    except urllib.error.HTTPError as e:
        logging.error(f"HTTP Fout bij verzoek naar {url}: {e.code} {e.reason}")
        return None
    except urllib.error.URLError as e:
        logging.error(f"URL Fout bij verzoek naar {url}: {e.reason}")
        return None
    except json.JSONDecodeError:
        logging.error(f"Fout bij het parsen van JSON-respons van {url}")
        return None


def get_public_ip(version: int) -> Optional[str]:
    """Haalt het openbare IPv4- of IPv6-adres op."""
    url = f"https://ipv{version}.icanhazip.com"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode("utf-8").strip()
    except urllib.error.URLError as e:
        logging.warning(f"Kon geen openbaar IPv{version}-adres ophalen: {e.reason}")
        return None


def get_records(api_key: str, domain_name: str) -> Optional[List[Dict]]:
    """Haalt de DNS-records voor een domein op."""
    url = f"{API_BASE_URL}/domains/{domain_name}/dns"
    headers = {"API-Key": api_key, "Content-Type": "application/json"}
    response = make_request(url, method="GET", headers=headers)
    return response["data"]["records"] if response and "data" in response else None


def put_records(api_key: str, domain_name: str, records: List[Dict]) -> bool:
    """Werkt de DNS-records voor een domein bij."""
    url = f"{API_BASE_URL}/domains/{domain_name}/dns"
    headers = {"API-Key": api_key, "Content-Type": "application/json"}
    data = json.dumps({"records": records}).encode("utf-8")
    response = make_request(url, method="PUT", headers=headers, data=data)
    if response:
        logging.info("DNS-records succesvol bijgewerkt.")
        return True
    logging.error("Fout bij het bijwerken van DNS-records.")
    return False


def update_routine(config: Dict):
    """De hoofdroutine voor het bijwerken van de DDNS."""
    logging.info("Update-routine wordt uitgevoerd...")

    domain_name = config["domain_name"]
    api_key = config["api_key"]
    record_name = (
        f"{config['record_name']}.{domain_name}"
        if config["record_name"] != "@"
        else domain_name
    )
    manage_records = config.get("manage_records", False)

    existing_records = get_records(api_key, domain_name)
    if existing_records is None:
        return

    records = list(existing_records)
    action_taken = False

    public_ipv4 = get_public_ip(4)
    public_ipv6 = get_public_ip(6)

    # Verwerk A-record (IPv4)
    a_record = next((r for r in records if r["type"] == "A" and r["name"] == record_name), None)
    if a_record:
        if public_ipv4:
            if a_record["value"] != public_ipv4:
                a_record["value"] = public_ipv4
                logging.info(f"A-record IP bijgewerkt naar {public_ipv4}...")
                action_taken = True
        elif manage_records:
            records.remove(a_record)
            logging.info("A-record verwijderd omdat er geen openbaar IPv4-adres is gevonden.")
            action_taken = True
    elif public_ipv4 and manage_records:
        new_record = {
            "type": "A",
            "name": record_name,
            "value": public_ipv4,
            "ttl": DEFAULT_TTL,
        }
        records.append(new_record)
        logging.info(f"A-record aangemaakt met IP {public_ipv4}...")
        action_taken = True

    # Verwerk AAAA-record (IPv6)
    aaaa_record = next((r for r in records if r["type"] == "AAAA" and r["name"] == record_name), None)
    if aaaa_record:
        if public_ipv6:
            if aaaa_record["value"] != public_ipv6:
                aaaa_record["value"] = public_ipv6
                logging.info(f"AAAA-record IP bijgewerkt naar {public_ipv6}...")
                action_taken = True
        elif manage_records:
            records.remove(aaaa_record)
            logging.info("AAAA-record verwijderd omdat er geen openbaar IPv6-adres is gevonden.")
            action_taken = True
    elif public_ipv6 and manage_records:
        new_record = {
            "type": "AAAA",
            "name": record_name,
            "value": public_ipv6,
            "ttl": DEFAULT_TTL,
        }
        records.append(new_record)
        logging.info(f"AAAA-record aangemaakt met IP {public_ipv6}...")
        action_taken = True

    if action_taken:
        put_records(api_key, domain_name, records)
    else:
        logging.info("Geen actie vereist.")


def main():
    parser = argparse.ArgumentParser(description="mijn.host DDNS updater in Python (zonder externe dependencies).")
    parser.add_argument(
        "config",
        nargs="?",
        default="./config.json",
        help="Pad naar het JSON-configuratiebestand.",
    )
    args = parser.parse_args()

    try:
        with open(args.config, "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        logging.error(f"Configuratiebestand niet gevonden op: {args.config}")
        sys.exit(1)
    except json.JSONDecodeError:
        logging.error(f"Fout bij het parsen van het JSON-configuratiebestand: {args.config}")
        sys.exit(1)

    interval = config.get("interval", 0)
    if interval > 0:
        while True:
            update_routine(config)
            logging.info(f"Wachten voor {interval} seconden...")
            time.sleep(interval)
    else:
        update_routine(config)


if __name__ == "__main__":
    main()
