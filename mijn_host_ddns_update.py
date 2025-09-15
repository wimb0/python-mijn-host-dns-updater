import argparse
import json
import logging
import sys
import urllib.request
import urllib.error
from typing import Dict, List, Optional

# Constanten
API_BASE_URL = "https://mijn.host/api/v2"
USER_AGENT = "Python-DDNS-Client/1.3"

# Maak een logger aan in plaats van de root logger te configureren
logger = logging.getLogger(__name__)

def _perform_request(url: str, method: str = "GET", headers: Optional[Dict] = None, data: Optional[bytes] = None) -> bytes:
    """Voert een HTTP-verzoek uit en retourneert de onbewerkte bytes of gooit een exceptie."""
    base_headers = {"User-Agent": USER_AGENT}
    if headers:
        base_headers.update(headers)
    
    req = urllib.request.Request(url, data=data, headers=base_headers, method=method)
    logger.debug(f"Verzoek wordt uitgevoerd: {method} {url}")
    
    with urllib.request.urlopen(req, timeout=10) as response:
        if response.status >= 400:
            raise urllib.error.HTTPError(url, response.status, response.reason, response.headers, None)
        return response.read()

def get_public_ip(version: int) -> Optional[str]:
    """Haalt het openbare IPv4- of IPv6-adres op."""
    url = f"https://ipv{version}.icanhazip.com"
    try:
        ip_bytes = _perform_request(url)
        ip_address = ip_bytes.decode("utf-8").strip()
        logger.debug(f"Openbaar IPv{version}-adres gevonden: {ip_address}")
        return ip_address
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        logger.warning(f"Kon geen openbaar IPv{version}-adres ophalen: {e}")
        return None

def get_records(api_key: str, domain_name: str) -> Optional[List[Dict]]:
    """Haalt de DNS-records voor een domein op."""
    url = f"{API_BASE_URL}/domains/{domain_name}/dns"
    headers = {"API-Key": api_key, "Accept": "application/json"}
    try:
        response_bytes = _perform_request(url, headers=headers)
        data = json.loads(response_bytes)
        records = data.get("data", {}).get("records")
        if records is not None:
             # Gebruik json.dumps voor een mooie, ingesprongen weergave van de records in de debug log
            logger.debug(f"Huidige DNS-records voor {domain_name}:\n{json.dumps(records, indent=2)}")
        return records
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        logger.error(f"Fout bij het ophalen van DNS-records: {e}")
    except json.JSONDecodeError:
        logger.error("Fout bij het parsen van de DNS-records respons.")
    return None

def put_records(api_key: str, domain_name: str, records: List[Dict]) -> bool:
    """Werkt de DNS-records voor een domein bij."""
    url = f"{API_BASE_URL}/domains/{domain_name}/dns"
    headers = {"API-Key": api_key, "Content-Type": "application/json"}
    data = json.dumps({"records": records}).encode("utf-8")
    try:
        _perform_request(url, method="PUT", headers=headers, data=data)
        logger.info("DNS-records succesvol bijgewerkt.")
        return True
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        logger.error(f"Fout bij het bijwerken van DNS-records: {e}")
        return False

def update_ddns(config: Dict):
    """De hoofdroutine voor het bijwerken van de DDNS."""
    logger.info("Update-routine wordt uitgevoerd...")

    api_key = config["api_key"]
    domain_name = config["domain_name"]
    record_name = (f"{config['record_name']}.{domain_name}" if config["record_name"] != "@" else domain_name)
    logger.debug(f"Doelrecord naam: {record_name}")

    all_records = get_records(api_key, domain_name)
    if all_records is None:
        return

    records_to_update = list(all_records)
    action_taken = False

    # --- Stap 1: Verwerk IPv4 (A record) ---
    public_ipv4 = get_public_ip(4)
    if public_ipv4:
        a_record = next((r for r in records_to_update if r["type"] == "A" and r["name"] == record_name), None)
        if a_record:
            logger.debug(f"Gevonden A-record: {a_record}")
            if a_record["value"] != public_ipv4:
                logger.info(f"A-record IP ({a_record['value']}) komt niet overeen met openbaar IP ({public_ipv4}). Wordt bijgewerkt...")
                a_record["value"] = public_ipv4
                action_taken = True
            else:
                logger.debug("A-record IP is al up-to-date.")
        else:
            logger.warning(f"Geen A-record gevonden met de naam '{record_name}'.")
    else:
        logger.info("Geen openbaar IPv4-adres gevonden, A-record wordt overgeslagen.")

    # --- Stap 2: Verwerk IPv6 (AAAA record) ---
    public_ipv6 = get_public_ip(6)
    if public_ipv6:
        aaaa_record = next((r for r in records_to_update if r["type"] == "AAAA" and r["name"] == record_name), None)
        if aaaa_record:
            logger.debug(f"Gevonden AAAA-record: {aaaa_record}")
            if aaaa_record["value"] != public_ipv6:
                logger.info(f"AAAA-record IP ({aaaa_record['value']}) komt niet overeen met openbaar IP ({public_ipv6}). Wordt bijgewerkt...")
                aaaa_record["value"] = public_ipv6
                action_taken = True
            else:
                logger.debug("AAAA-record IP is al up-to-date.")
        else:
            logger.warning(f"Geen AAAA-record gevonden met de naam '{record_name}'.")
    else:
        logger.info("Geen openbaar IPv6-adres gevonden, AAAA-record wordt overgeslagen.")

    # --- Stap 3: Werk de records bij als er iets is veranderd ---
    if action_taken:
        put_records(api_key, domain_name, records_to_update)
    else:
        logger.info("Geen actie vereist. IP-adressen zijn al up-to-date.")

def main():
    """Script entrypoint: parseert argumenten en start de update."""
    parser = argparse.ArgumentParser(description="Eenmalige mijn.host DDNS updater in Python.")
    parser.add_argument(
        "config",
        nargs="?",
        default="./config.json",
        help="Pad naar het JSON-configuratiebestand.",
    )
    parser.add_argument(
        "-d", "--debug",
        action="store_true",
        help="Schakel gedetailleerde debug logging in."
    )
    args = parser.parse_args()

    # Stel het logging niveau in op basis van de --debug vlag
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )

    try:
        with open(args.config, "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        logger.error(f"Configuratiebestand niet gevonden op: {args.config}")
        sys.exit(1)
    except json.JSONDecodeError:
        logger.error(f"Fout bij het parsen van het JSON-configuratiebestand: {args.config}")
        sys.exit(1)
    
    required_keys = ["api_key", "domain_name", "record_name"]
    if not all(key in config for key in required_keys):
        logger.error(f"Configuratiebestand mist een of meer verplichte sleutels: {required_keys}")
        sys.exit(1)

    update_ddns(config)

if __name__ == "__main__":
    main()
