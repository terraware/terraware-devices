# Terraware device manager code

This code provides local on-site monitoring and control software for Terraformation hardware systems (seed banks, power generation, desalination, irrigation, etc.).

It runs as a service on the Terraware [Balena stack](https://github.com/terraware/balena/).

## Configuration

If you are running the code under Balena, you may need to set these service variables:

*   `RHIZO_SECRET_KEY`: the secret key required by the web server
*   `RHIZO_ROUTER_PASSWORD`: the admin password for the 4G router (only needed if monitoring router state)

Other values in the `config.yaml` file can be modified with similar `RHIZO_` variables.

## Local Testing under Balena

To generate random device data (rather than obtaining it from real hardware), set the Balena service variable `RHIZO_LOCAL_SIM` to `1`.

## Local Testing outside Balena

Copy `sample_local.yaml` to `local.yaml` (in the same directory) and make changes to it as needed, then run `main.py` from the same directory. 

If you specify a `local_device_file_name` it should point to a JSON file in the same format as provided by the server.
