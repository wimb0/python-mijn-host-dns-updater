import argparse
import asyncio
import logging
import os
from dataclasses import dataclass
from typing import List, Optional
import json
import aiohttp
import ipaddress

API_BASE_URL = "https://mijn.host/api/v2"
DEFAULT_TTL = 300

@dataclass
class Config:
    domain_name: str
    api_key: str
    record_name: str
    interval: int
    manage_records: bool

@dataclass
class Record:
    type: str
    name: str
    value: str
    ttl: int

def load_config(path: str) -> Config:
    """Load and validate configuration from a JSON file."""
    logging.debug("Loading config...")
    with open(path, 'r') as f:
        data = json.load(f)
    required_fields = ['domain_name', 'api_key', 'record_name', 'interval', 'manage_records']
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing required config field: {field}")
    return Config(
        domain_name=data['domain_name'],
        api_key=data['api_key'],
        record_name=data['record_name'],
        interval=data['interval'],
        manage_records=data['manage_records'],
    )

async def get_records(session: aiohttp.ClientSession, api_key: str, domain_name: str) -> List[Record]:
    """Fetch DNS records from the mijn.host API."""
    url = f"{API_BASE_URL}/domains/{domain_name}/dns"
    headers = {"API-Key": api_key}
    for attempt in range(3):
        try:
            async with session.get(url, headers=headers) as resp:
                resp.raise_for_status()
                data = await resp.json()
                records_data = data["data"]["records"]
                return [Record(**rec) for rec in records_data]
        except Exception as e:
            if attempt == 2:
                raise
            logging.warning(f"get_records attempt {attempt+1} failed: {e}")
    return []

async def put_records(session: aiohttp.ClientSession, api_key: str, domain_name: str, records: List[Record]) -> None:
    """Update DNS records on the mijn.host API."""
    url = f"{API_BASE_URL}/domains/{domain_name}/dns"
    headers = {"API-Key": api_key}
    records_payload = [record.__dict__ for record in records]
    payload = {"records": records_payload}
    for attempt in range(3):
        try:
            async with session.put(url, headers=headers, json=payload) as resp:
                resp.raise_for_status()
                return
        except Exception as e:
            if attempt == 2:
                raise
            logging.warning(f"put_records attempt {attempt+1} failed: {e}")

async def get_public_ip(session: aiohttp.ClientSession, url: str, version: int, retries: int = 3) -> Optional[ipaddress._BaseAddress]:
    """Fetch the public IP (v4 or v6) from a specified service."""
    for attempt in range(retries):
        try:
            async with session.get(url) as resp:
                text = await resp.text()
                if version == 4:
                    return ipaddress.IPv4Address(text.strip())
                else:
                    return ipaddress.IPv6Address(text.strip())
        except aiohttp.ClientConnectorError:
            return None
        except Exception as e:
            if attempt == retries - 1:
                raise
            await asyncio.sleep(1)
    return None

async def routine(config: Config, session: aiohttp.ClientSession) -> None:
    logging.info("Running update routine...")
    existing_records = await get_records(session, config.api_key, config.domain_name)
    action_taken = await update_record_list(existing_records, config, session)
    if action_taken:
        logging.debug("Updating records via the API...")
        await put_records(session, config.api_key, config.domain_name, existing_records)
    else:
        logging.info("No action required.")

async def update_record_list(records: List[Record], config: Config, session: aiohttp.ClientSession) -> bool:
    """Update the DNS record list based on current public IPs and config."""
    a_idx = next((i for i, r in enumerate(records) if r.type == "A" and r.name == config.record_name), None)
    aaaa_idx = next((i for i, r in enumerate(records) if r.type == "AAAA" and r.name == config.record_name), None)

    action_taken = False
    remove_a_rec = False
    remove_aaaa_rec = False

    # Handle A record
    if a_idx is not None:
        a_rec = records[a_idx]
        ipv4 = await get_public_ip(session, "https://ipv4.icanhazip.com", 4)
        if ipv4 is not None:
            if str(ipaddress.IPv4Address(a_rec.value)) == str(ipv4):
                logging.debug(f"public ipv4 found ({ipv4}) matches the A record.")
            else:
                a_rec.value = str(ipv4)
                logging.info(f"A record IP updated to {ipv4}.")
                action_taken = True
        elif config.manage_records:
            remove_a_rec = True
        else:
            logging.warning(
                f"public ipv4 not found but an A record ({a_rec.value}) exists, consider enabling record management"
            )
    else:
        ipv4 = await get_public_ip(session, "https://ipv4.icanhazip.com", 4)
        if ipv4 is not None:
            if config.manage_records:
                ttl = records[aaaa_idx].ttl if aaaa_idx is not None else DEFAULT_TTL
                new_record = Record(type="A", name=config.record_name, value=str(ipv4), ttl=ttl)
                logging.info(f"A record created with IP {new_record.value} and TTL {new_record.ttl} seconds.")
                records.append(new_record)
                action_taken = True
            else:
                logging.warning(
                    f"public ipv4 found ({ipv4}) but no A record exists, consider enabling record management"
                )
        else:
            logging.debug("public ipv4 not found, matching the absence of an A record.")

    # Handle AAAA record
    if aaaa_idx is not None:
        aaaa_rec = records[aaaa_idx]
        ipv6 = await get_public_ip(session, "https://ipv6.icanhazip.com", 6)
        if ipv6 is not None:
            if str(ipaddress.IPv6Address(aaaa_rec.value)) == str(ipv6):
                logging.debug(f"public ipv6 found ({ipv6}) matches the AAAA record.")
            else:
                aaaa_rec.value = str(ipv6)
                logging.info(f"AAAA record IP updated to {ipv6}.")
                action_taken = True
        elif config.manage_records:
            remove_aaaa_rec = True
        else:
            logging.warning(
                f"public ipv6 not found but an AAAA record ({aaaa_rec.value}) exists, consider enabling record management"
            )
    else:
        ipv6 = await get_public_ip(session, "https://ipv6.icanhazip.com", 6)
        if ipv6 is not None:
            if config.manage_records:
                ttl = records[a_idx].ttl if a_idx is not None else DEFAULT_TTL
                new_record = Record(type="AAAA", name=config.record_name, value=str(ipv6), ttl=ttl)
                logging.info(f"AAAA record created with IP {new_record.value} and TTL {new_record.ttl} seconds.")
                records.append(new_record)
                action_taken = True
            else:
                logging.warning(
                    f"public ipv6 found ({ipv6}) but no AAAA record exists, consider enabling record management"
                )
        else:
            logging.debug("public ipv6 not found, matching the absence of an AAAA record.")

    # Remove records if needed
    if remove_a_rec:
        records[:] = [r for r in records if not (r.type == "A" and r.name == config.record_name)]
        logging.info("A record has been deleted.")
        action_taken = True

    if remove_aaaa_rec:
        records[:] = [r for r in records if not (r.type == "AAAA" and r.name == config.record_name)]
        logging.info("AAAA record has been deleted.")
        action_taken = True

    return action_taken

async def main() -> None:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser()
    parser.add_argument('config', nargs='?', default='./config.json')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s')

    config = load_config(args.config)

    if config.record_name == "@":
        config.record_name = f"{config.domain_name}."
    else:
        config.record_name = f"{config.record_name}.{config.domain_name}"

    async with aiohttp.ClientSession() as session:
        if config.interval == 0:
            await routine(config, session)
        else:
            while True:
                await asyncio.sleep(config.interval)
                await routine(config, session)

if __name__ == "__main__":
    asyncio.run(main())
