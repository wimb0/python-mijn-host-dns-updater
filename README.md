## Python Mijn.host DNS updater
Simple Mijn.host DNS updater in Python.

# Config.json

- domain_name : your domain name, i.e. example.com
- api_key : your api key, see https://mijn.host/api/doc/doc-343216
- record_name : DNS record to update. @ is the base domain.

# Docker container
```
docker run -it --rm \
  --name mijn-host-ddns \
  --volume ./config.json:/app/config.json:ro \
  ghcr.io/wimb0/python-mijn-host-dns-updater:latest --config config.json
```
  
# Credits
Idea based on Rust implementation from https://github.com/ldobbelsteen/mijn-host-ddns
