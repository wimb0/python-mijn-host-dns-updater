# Python Mijn.host DDNS Updater

A simple, dependency-free Python script to keep your DNS records at [Mijn.host](https://mijn.host) updated with your dynamic public IP address.
The script is available as a multi-platform Docker container from `ghcr.io`.

[![CI for Python DDNS Updater](https://github.com/wimb0/python-mijn-host-dns-updater/actions/workflows/ci.yml/badge.svg)](https://github.com/wimb0/python-mijn-host-dns-updater/actions/workflows/ci.yml)

## Features

-   **IPv4 & IPv6 Support**: Updates both A and AAAA records.
-   **Multi-Record**: Updates multiple hostnames (e.g., `@`, `*`) in a single run.
-   **Create Records**: Can automatically create records if they don't exist (optional).
-   **Docker Ready**: Multi-platform image (`linux/amd64`, `linux/arm64`) available.
-   **Safe Testing**: A `--dry-run` flag shows what would change without executing.
-   **Debug Mode**: A `--debug` flag for verbose logging.

## Configuration

The script uses a `config.json` file for configuration.

**`config.json` example:**

```json
{
  "domain_name": "example.com",
  "api_key": "your-mijn-host-api-key",
  "record_names": [
    "@",
    "*"
  ],
  "default_ttl": 300,
  "create_records_if_missing": false
}
```
- domain_name: Your base domain name.
- api_key: Your Mijn.host API key.
- record_names: A list of DNS records to update ("@" for the root domain).
- default_ttl: The TTL to use when creating new records.
- create_records_if_missing: (Optional, default: false) Set to true to allow the script to create new DNS records.

## Usage
### Local Script Execution
```
# Basic usage
python mijn_host_ddns_updater.py --config /path/to/config.json

# Test with a dry run
python mijn_host_ddns_updater.py --config config.json --dry-run
```
### Docker Container
The container is available at `ghcr.io/wimb0/python-mijn-host-dns-updater`.

```
# Run the updater via Docker
docker run --rm \
  --name mijn-host-ddns \
  --volume ./config.json:/app/config.json:ro \
  ghcr.io/wimb0/python-mijn-host-dns-updater:latest --config config.json
```
 
## Credits
This project was inspired by the original Rust implementation by [ldobbelsteen](https://github.com/ldobbelsteen/mijn-host-ddns).
