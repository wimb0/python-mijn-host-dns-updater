import argparse
import json
import logging
import sys
import time
import urllib.request
import urllib.error
from typing import Dict, List, Optional

# Constants
API_BASE_URL = "https://mijn.host/api/v2"
USER_AGENT = "Python-DDNS-Client/2.3" # Version updated

# Create a logger
logger = logging.getLogger(__name__)

def _perform_request(url: str, method: str = "GET", headers: Optional[Dict] = None, data: Optional[bytes] = None) -> bytes:
    """Performs an HTTP request and returns the raw bytes or raises an exception."""
    base_headers = {"User-Agent": USER_AGENT}
    if headers:
        base_headers.update(headers)
    
    req = urllib.request.Request(url, data=data, headers=base_headers, method=method)
    logger.debug(f"Executing request: {method} {url}")
    
    with urllib.request.urlopen(req, timeout=10) as response:
        if response.status >= 400:
            raise urllib.error.HTTPError(url, response.status, response.reason, response.headers, None)
        return response.read()

def get_public_ip(version: int) -> Optional[str]:
    """Fetches the public IPv4 or IPv6 address."""
    url = f"https://ipv{version}.icanhazip.com"
    try:
        ip_bytes = _perform_request(url)
        ip_address = ip_bytes.decode("utf-8").strip()
        logger.debug(f"Found public IPv{version} address: {ip_address}")
        return ip_address
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        logger.warning(f"Could not retrieve public IPv{version} address: {e}")
        return None

def get_records(api_key: str, domain_name: str) -> Optional[List[Dict]]:
    """Fetches the DNS records for a domain."""
    url = f"{API_BASE_URL}/domains/{domain_name}/dns"
    headers = {"API-Key": api_key, "Accept": "application/json"}
    try:
        response_bytes = _perform_request(url, headers=headers)
        data = json.loads(response_bytes)
        records = data.get("data", {}).get("records")
        if records is not None:
            logger.debug(f"Current DNS records for {domain_name}:\n{json.dumps(records, indent=2)}")
        return records
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        logger.error(f"Error fetching DNS records: {e}")
    except json.JSONDecodeError:
        logger.error("Error parsing the DNS records response.")
    return None

def put_records(api_key: str, domain_name: str, records: List[Dict]) -> bool:
    """Updates the DNS records for a domain."""
    url = f"{API_BASE_URL}/domains/{domain_name}/dns"
    headers = {"API-Key": api_key, "Content-Type": "application/json"}
    data = json.dumps({"records": records}).encode("utf-8")
    try:
        _perform_request(url, method="PUT", headers=headers, data=data)
        logger.info("DNS records updated successfully.")
        return True
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        logger.error(f"Error updating DNS records: {e}")
        return False

def update_ddns(config: Dict, dry_run: bool = False):
    """The main routine for updating DDNS for multiple records."""
    if dry_run:
        logger.info("Starting update routine in DRY-RUN mode. No changes will be made.")
    else:
        logger.info("Starting update routine...")

    api_key = config["api_key"]
    domain_name = config["domain_name"]
    record_names_to_update = config["record_names"]
    create_records = config.get("create_records_if_missing", False)

    all_records = get_records(api_key, domain_name)
    if all_records is None:
        return

    records_to_update = list(all_records)
    changes_found = []

    public_ipv4 = get_public_ip(4)
    public_ipv6 = get_public_ip(6)
    
    if not public_ipv4:
        logger.info("No public IPv4 address found, skipping A records.")
    if not public_ipv6:
        logger.info("No public IPv6 address found, skipping AAAA records.")

    def normalize_record_name(name: str) -> str:
        return name.rstrip('.')

    for record_name_from_config in record_names_to_update:
        full_target_name = (f"{record_name_from_config}.{domain_name}" if record_name_from_config != "@" else domain_name).rstrip('.')
        
        logger.info(f"--- Processing record: {full_target_name} ---")

        # Process IPv4 (A record)
        if public_ipv4:
            a_record = next((r for r in records_to_update if r["type"] == "A" and normalize_record_name(r["name"]) == full_target_name), None)
            if a_record:
                if a_record["value"] != public_ipv4:
                    change_summary = f"Update A record for '{full_target_name}' from '{a_record['value']}' to '{public_ipv4}'"
                    logger.info(f"CHANGE DETECTED: {change_summary}")
                    changes_found.append(change_summary)
                    a_record["value"] = public_ipv4
                else:
                    logger.debug(f"A record for '{full_target_name}' is already up-to-date.")
            elif create_records:
                new_record_ttl = config["default_ttl"]
                change_summary = f"Create A record for '{full_target_name}' with IP '{public_ipv4}' and TTL {new_record_ttl}"
                logger.info(f"CHANGE DETECTED: {change_summary}")
                changes_found.append(change_summary)
                new_record = { "type": "A", "name": record_name_from_config, "value": public_ipv4, "ttl": new_record_ttl }
                records_to_update.append(new_record)

        # Process IPv6 (AAAA record)
        if public_ipv6:
            aaaa_record = next((r for r in records_to_update if r["type"] == "AAAA" and normalize_record_name(r["name"]) == full_target_name), None)
            if aaaa_record:
                if aaaa_record["value"] != public_ipv6:
                    change_summary = f"Update AAAA record for '{full_target_name}' from '{aaaa_record['value']}' to '{public_ipv6}'"
                    logger.info(f"CHANGE DETECTED: {change_summary}")
                    changes_found.append(change_summary)
                    aaaa_record["value"] = public_ipv6
                else:
                    logger.debug(f"AAAA record for '{full_target_name}' is already up-to-date.")
            elif create_records:
                new_record_ttl = config["default_ttl"]
                change_summary = f"Create AAAA record for '{full_target_name}' with IP '{public_ipv6}' and TTL {new_record_ttl}"
                logger.info(f"CHANGE DETECTED: {change_summary}")
                changes_found.append(change_summary)
                new_record = { "type": "AAAA", "name": record_name_from_config, "value": public_ipv6, "ttl": new_record_ttl }
                records_to_update.append(new_record)

    if changes_found:
        if dry_run:
            logger.info("DRY-RUN SUMMARY: The following changes would be made:")
            for change in changes_found:
                print(f"  - {change}")
        else:
            logger.info("Pushing updates to the API...")
            put_records(api_key, domain_name, records_to_update)
    else:
        logger.info("No action required. All checked records are already up-to-date.")

def main():
    """Script entrypoint: parses arguments and starts the update."""
    parser = argparse.ArgumentParser(description="Mijn.host DDNS updater with built-in scheduler.")
    
    parser.add_argument("-c", "--config", default="./config.json", help="Path to the JSON configuration file (default: ./config.json).")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable detailed debug logging.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without executing the update.")
    args = parser.parse_args()
    
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s - %(levelname)s - %(message)s", stream=sys.stdout)

    config_path = args.config
    logger.debug(f"Using configuration file: {config_path}")

    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        logger.error(f"Configuration file not found at: {config_path}")
        sys.exit(1)
    except IsADirectoryError:
        logger.error(f"Error: The configuration path '{config_path}' is a directory, but it should be a file.")
        logger.error("Please ensure that your config.json file exists and the volume mount is correct.")
        sys.exit(1)
    except json.JSONDecodeError:
        logger.error(f"Error parsing the JSON configuration file: {config_path}")
        sys.exit(1)
    
    required_keys = ["api_key", "domain_name", "record_names", "default_ttl"]
    if not all(key in config for key in required_keys):
        logger.error(f"Configuration file is missing one or more required keys: {required_keys}")
        sys.exit(1)

    interval = config.get("interval", 0)

    while True:
        try:
            update_ddns(config, dry_run=args.dry_run)
        except Exception as e:
            logger.error(f"An unexpected error occurred during the update routine: {e}")

        if interval <= 0:
            logger.info("Interval is 0, script will now exit.")
            break
        
        logger.info(f"Waiting for {interval} seconds before next run...")
        time.sleep(interval)

if __name__ == "__main__":
    main()
