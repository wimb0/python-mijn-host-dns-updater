import argparse
import json
import logging
import sys
import urllib.request
import urllib.error
from typing import Dict, List, Optional

# Constanten
API_BASE_URL = "https://mijn.host/api/v2"
USER_AGENT = "Python-DDNS-Client/1.2"

# Logging eenmalig instellen
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

def _perform_request(url: str, method: str = "GET", headers: Optional[Dict] = None, data: Optional[bytes] = None) -> bytes:
    """Voert een HTTP-verzoek uit en retourneert de onbewerkte bytes of gooit een exceptie."""
    base_headers = {"User-Agent": USER_AGENT}
    if headers:
        base_headers.update(headers)
    
    req = urllib.request.Request(url, data=data, headers=base_headers, method=method)
    
    with urllib.request.urlopen(req, timeout=10) as response:
        if response.status >= 400:
            raise urllib.error.HTTPError(url, response.status, response.reason, response.headers, None)
        return response.read()

def get_public_ip(version: int) -> Optional[str]:
    """Haalt het openbare IPv4- of IPv6-adres op."""
    url = f"https://ipv{version}.icanhazip.com"
    try:
        ip_bytes = _perform_request(url)
        return ip_bytes.decode("utf-8").strip()
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        logging.warning(f"Kon geen openbaar IPv{version}-adres ophalen: {e}")
        return None

def get_records(api_key: str, domain_name: str) -> Optional[List[Dict]]:
    """Haalt de DNS-records voor een domein op."""
    url = f"{API_BASE_URL}/domains/{domain_name}/dns"
    headers = {"API-Key": api_key, "Accept": "application/json"}
    try:
        response_bytes = _perform_request(url, headers=headers)
        data = json.loads(response_bytes)
        return data.get("data", {}).get("records")
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        logging.error(f"Fout bij het ophalen van DNS-records: {e}")
    except json.JSONDecodeError:
        logging.error("Fout bij het parsen van de DNS-records respons.")
    return None

def put_records(api_key: str, domain_name: str, records: List[Dict]) -> bool:
    """Werkt de DNS-records voor een domein bij."""
    url = f"{API_BASE_URL}/domains/{domain_name}/dns"
    headers = {"API-Key": api_key, "Content-Type": "application/json"}
    data = json.dumps({"records": records}).encode("utf-8")
    try:
        _perform_request(url, method="PUT", headers=headers, data=data)
        logging.info("DNS-records succesvol bijgewerkt.")
        return True
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        logging.error(f"Fout bij het bijwerken van DNS-records: {e}")
        return False

def update_ddns(config: Dict):
    """De hoofdroutine voor het bijwerken van de DDNS."""
    logging.info("Update-routine wordt uitgevoerd...")

    api_key = config["api_key"]
    domain_name = config["domain_name"]
    record_name = (f"{config['record_name']}.{domain_name}" if config["record_name"] != "@" else domain_name)

    all_records = get_records(api_key, domain_name)
    if all_records is None:
        return

    records_to_update = list(all_records)
    action_taken = False

    # --- Stap 1: Verwerk IPv4 (A record) ---
    public_ipv4 = get_public_ip(4)
    if public_ipv4:
        a_record = next((r for r in records_to_update if r["type"] == "A" and r["name"] == record_name), None)
        if a_record and a_record["value"] != public_ipv4:
            logging.info(f"A-record IP bijgewerkt naar {public_ipv4}...")
            a_record["value"] = public_ipv4
            action_taken = True
    else:
        logging.info("Geen openbaar IPv4-adres gevonden, A-record wordt overgeslagen.")

    # --- Stap 2: Verwerk IPv6 (AAAA record) ---
    public_ipv6 = get_public_ip(6)
    if public_ipv6:
        aaaa_record = next((r for r in records_to_update if r["type"] == "AAAA" and r["name"] == record_name), None)
        if aaaa_record and aaaa_record["value"] != public_ipv6:
            logging.info(f"AAAA-record IP bijgewerkt naar {public_ipv6}...")
            aaaa_record["value"] = public_ipv6
            action_taken = True
    else:
        logging.info("Geen openbaar IPv6-adres gevonden, AAAA-record wordt overgeslagen.")

    # --- Stap 3: Werk de records bij als er iets is veranderd ---
    if action_taken:
        put_records(api_key, domain_name, records_to_update)
    else:
        logging.info("Geen actie vereist. IP-adressen zijn al up-to-date.")

def main():
    """Script entrypoint: parseert argumenten en start de update."""
    parser = argparse.ArgumentParser(description="Eenmalige mijn.host DDNS updater in Python.")
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
    
    required_keys = ["api_key", "domain_name", "record_name"]
    if not all(key in config for key in required_keys):
        logging.error(f"Configuratiebestand mist een of meer verplichte sleutels: {required_keys}")
        sys.exit(1)

    update_ddns(config)

if __name__ == "__main__":
    main()
