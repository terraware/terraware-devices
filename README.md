# Terraware device manager code

This code provides local on-site monitoring and control software for Terraformation hardware systems (seed banks, power generation, desalination, irrigation, etc.).

It runs as a service on the Terraware [Balena stack](https://github.com/terraware/balena/).

## Local Testing under Balena

To generate random device data (rather than obtaining it from real hardware), set the Balena device environment variable `RHIZO_LOCAL_SIM` to `1`.