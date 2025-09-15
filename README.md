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
-   "interval": 1800

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
  "create_records_if_missing": false,
  "interval": 1800
}
```
- `domain_name`: Your base domain name.
- `api_key`: Your Mijn.host API key.
- `record_names`: A list of DNS records to update ("@" for the root domain).
- `default_ttl`: The TTL to use when creating new records.
- `create_records_if_missing`: (Optional, default: false) Set to true to allow the script to create new DNS records.
- `interval`: (Optional, default: 0) The number of seconds to wait between updates. If set to 0, the script will run once and exit.
  
## Usage
### Local Script Execution
```
# Basic usage
python mijn_host_ddns_updater.py --config /path/to/config.json

# Test with a dry run
python mijn_host_ddns_updater.py --config config.json --dry-run

```
### Docker Usage

The container is available at `ghcr.io/wimb0/python-mijn-host-dns-updater`.

#### With Docker Compose (Recommended)

Using `docker-compose` is the easiest way to manage the container as a service.

1.  Create a `docker-compose.yml` file with the content below.
2.  Make sure your `config.json` is in the same directory.
3.  Run `docker-compose up -d` to start the service in the background.

**`docker-compose.yml` file:**
```yaml
services:
  mijn-host-ddns-updater:
    image: ghcr.io/wimb0/python-mijn-host-dns-updater:latest
    restart: unless-stopped
    volumes:
      - ./config.json:/app/config.json:ro
    command: --config config.json
    restart: on-failure
```

### With docker run
You can also use the docker run command directly.
```
docker run --rm \
  --name mijn-host-ddns \
  --volume ./config.json:/app/config.json:ro \
  ghcr.io/wimb0/python-mijn-host-dns-updater:latest --config config.json
```
 
## Credits
This project was inspired by the original Rust implementation by [ldobbelsteen](https://github.com/ldobbelsteen/mijn-host-ddns).
