# Terraware device manager code

This code provides local on-site monitoring and control software for Terraformation hardware systems (seed banks, power generation, desalination, irrigation, etc.).

It runs as a service on the Terraware [Balena stack](https://github.com/terraware/balena/).

This version of the README is heavily about the state I (Brian Sharp) am leaving the code in as I leave TF, so it's pretty ephemeral but seemed like the right place to leave this documentation.

## Most Obvious Todos

*	The code hasn't actually been hooked up to use terraware-server and the auth stuff yet. I've only managed to test it in local sim mode for now. The API usage should be a drop-in replacement since local sim mode fully spoofs everything and it's a very small surface area. At this point I can probably get that code written, but testing it given I have 2 days left seems unrealistic since that means setting up the local terraware-server instance, populating the database with the config with SQL (which I don't really know very well) and so on.
*	The Chirpstack driver is currently disabled - to reenable it, search for "chirpstack" in device_manager.py to find two commented-out blocks (one at top and one at bottom) and then also add chirpstack_api back into requirements.txt. This is disabled because the chirpstack_api lib pulls in a ton of other stuff including grpcio, which takes a solid 45+ minutes to build on the Pi. The only use of the chirpstack_api stuff is for the protobuf-based message formats, but since you can configure LoRaWAN gateways to send JSON instead - and I believe the code as it stands is doing that - you can probably eliminate the chirpstack_api dependency entirely and just pull the payload out of the message json manually. I didn't do this because I don't have an active LoRaWAN gateway to test with, so I can't actually see what the incoming message format looks like.
* 	The Chirpstack driver relies on the balena supervisor access to get the host machine IP address on the Pi; in the balena app you'll need to add the `io.balena.features.supervisor-api: true` label to the devices service - see the `terrahass` service, it already has it.
*	The only hardware I actually physically have to test against here is the Tempest weather station. I just ported this driver over from homeassistant, and when I ran it I was having trouble getting UDP packets from my weather station. It's using the exact same library as the homeassistant integration and the weatherflow.py driver is all of 75 lines of code. I assume it's just network port mapping stuff - homeassistant was setup to explicitly forward ports from the host OS whereas the device manager service is running in network_mode:host - but I haven't yet had time to dig into it deeply.
*	The other driver code has been refactored since the last deployed incarnation of the device manager, and I've tested it all in local_sim mode, but I haven't actually tested it all against real hardware, since I don't have that hardware and the code isn't ready to deploy. Since it works in local_sim mode and the refactoring was largely about handing the dev_info structure all the way down into the device constructors rather than having device_manager pull individual arguments and pass them in manually, I expect that for the most part it will just work, as the hardware interface code didn't really get touched. But it's very likely I made a few typos or logic errors pulling arguments out of the dev_info structure. Those bugs should be very straightforward to find and fix.

## Configuration

To run in local sim mode, where the config is loaded from a JSON file and all devices generate spoofed data and don't try to talk to real hardware, set:

*	`LOCAL_SIM_CONFIG_FILE`: The filename, relative to the root of the project, to load. If you uncomment the line in the Dockerfile that copies sample-site.json over to the Pi, set this environment variable to `sample-site.json` - that file will be in the working directory for the devices service on the Pi.

The following envvars are relevant whether running in local sim mode or production mode:

*	`DIAGNOSTIC_MODE`: Set this to true to enable verbose diagnostic printing.

And these variables must be set to run with a connection to terraware-server for querying config data and for uploading timeseries data:

*   `OFFLINE_REFRESH_TOKEN`: The [Keycloak token used to request expiring API keys](https://terraformation.atlassian.net/wiki/spaces/FT/pages/330661907/API+keys+for+brains).
*   `ACCESS_TOKEN_REQUEST_URL`: The full URL (including server and rest query string) for requesting the expiring access token (see above link.)
*   `SERVER`: The server address (name or IP) for the terraware-server instance to load config from & push timeseries data to.
*   `FACILITIES`: The list of facility IDs this device manager instance represents. Should be formatted like a python list, e.g. `[1,3,18]`

## Device Configuration

Refer to `sample-site.json` for a full example of configuring every supported sensor (including the currently-disabled-in-code chirpstack sensors.) There aren't enough drivers in there yet to really have a canonical split between "required" and "optional" - it's still a bit case-by-case. But we do have a split between formal parameters and "additional settings". In the `sample-site.json` the distinction is just "is it in the top-level device config dictionary, or is it in the nested 'settings' dictionary?" But on the terraware-server side, the significance is that the top-level ones can be formalized in the database schema, and then the 'settings' dictionary is a single JSON-valued field in the schema. So, it's harder to validate, but useful for very device-specific settings.

As of this writing, here's an exhaustive list of the parameters and what they're used for:

*	`id (int)`: The globally-unique identifier for this device. Absolutely required, all drivers use this. It is half of the key for all timeseries data from the device.
*	`name (string)`: The human-readable name of the device. This is required for all devices, but is used *exclusively* for diagnostic display.
*	`type (string)`: One of 'ups', 'server', 'router', 'relay', 'sensor', 'hub'. As more drivers get added this list should probably be culled and formalized more, it's a little ad-hoc.
*	`make (string)` and `model (string)`: The make and model of the device. Required for all devices, on principle. In practice they're primarily used by DeviceManager::get_device_class_to_instantiate and also by modbus devices to compose the spec filename they load to get their register layout.
* 	`address (string)` and `port (int)`: Address is used variously to mean an IP address or, usually for child devices off hubs (omnisense temp & humidity sensors, LoRa soil moisture sensors) it's some hex string unique ID specific to the hardware used to interpret incoming data packets. Port is used by fewer drivers but still common enough to be a first-class parameter.
*	`parentId (int)`: The `id` of another device in the list (doesn't matter what order they appear in) that this device is chained off of. This is used for sensors that connect to 'hub' devices like the OmniSense gateway, LoRaWAN hubs, and so on. See below for more on that.
*	`pollingInterval (int)`: How frequently, in seconds, to poll this device for values. *If this value is omitted or set to 0, the device will never be polled.* See below section for more on this.

### Hubs, Child Devices, Polling Intervals

The `parentId` parameter in a device's configuration causes it to get bound to that device as a child (the hub device gets `add_device` called with the child device after the first construction pass.) Hubs then get a `notify_all_devices_added` when all their children are added to give them a chance to do stuff (ChirpStack and OmniSense wait for this to spawn their listening services so they don't throw away data for child sensors they haven't heard about yet.) Probably this is overkill since it's probably only a nanosecond between the hub's construction and when all its child devices are added, but that might change in the future if devices block on construction for some reason, so this seemed like the right move.

For hub/child relationships, right now the code is a little inconsistent: For OmniSense, the hub's `poll` returns all the timeseries values for all the child sensors, and so the hub device needs a valid `pollingInterval` value in its config, and the child sensors shouldn't be polled at all, but for ChirpStack, based on how the driver code was written (originally for homeassistant and I ported it over to the device manager) it was easier to have the child sensors return their data instead. There's no fundamental need to standardize one way or the other, but the inconsistency is bothersome. On the upside, it should be fine to just set all devices to be polled and some just never return any data.