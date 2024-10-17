
### CUPS AirPrint in Docker soltuion (AMD64 / ARM64)
xirixiz/cups-airprint [docker-image](https://hub.docker.com/r/xirixiz/cups-airprint)

This Debian-based (bookwork-slim) Docker image runs a CUPS instance that is meant as an AirPrint relay for printers that are already on the network but not AirPrint capable or AirPrint doesn't work anymore on outdated printers. Also Synology has issues, so I decided to move to this solution.
* `Included drivers HP, Samsung, Canon, Xerox, etc.`

Many thanks and credits go out to:
* https://github.com/ziwork/synology-airprint
* https://github.com/schredder/cups-airprint

I used these projects as a source for this project. Differences are:
* Less complicated structure - switched from the double root/root folder to just one folder called app
* Less complicated structure - reduced to from 3 to 2 files
* Python code rewrite. Modernized and reduced code from 279 lines to 218 lines (~22%)

### Add and setup printer:
* CUPS will be configurable at https://<host ip>:631 using `admin/admin`as login credentials.
* Make sure you select `Share This Printer` when configuring the printer in CUPS.
* ***After configuring your printer, you need to close the web browser for at least 60 seconds. CUPS will not write the config files until it detects the connection is closed for as long as a minute.***


### Before you run this container on Synology DSM7.x, please run this commands from the ssh terminal of your Synology:
* `sudo synosystemctl stop cupsd`
* `sudo synosystemctl stop cups-lpd`
* `sudo synosystemctl stop cups-service-handler`
* `sudo synosystemctl disable cupsd`
* `sudo synosystemctl disable cups-lpd`
* `sudo synosystemctl disable cups-service-handler`


### If needed, you can always role back to the Synology defaults (make sure you first stop and removed the Docker container before doing this)
* `sudo synosystemctl start cupsd`
* `sudo synosystemctl start cups-lpd`
* `sudo synosystemctl start cups-service-handler`
* `sudo synosystemctl enable cupsd`
* `sudo synosystemctl enable cups-lpd`
* `sudo synosystemctl enable cups-service-handler`

## Manual Configuration

### Volumes:
* `/config`: where the persistent printer configs will be stored
* `/services`: where the Avahi service files will be generated

### Variables:
* `CUPSADMIN`: the CUPS admin user you want created - default is `admin` if unspecified
* `CUPSPASSWORD`: the password for the CUPS admin user - default is `admin` username if unspecified

### Ports/Network:
* **Must be run on host network. This is required to support multicasting which is needed for Airprint.**


### Example run env command.
* tested on Synology DSM 7.2.x. Paths may be different for the volumes in the example.
```
docker run -d \
  --name=cups-airprint \
  --network="host" \
  --restart=always \
  --device=/dev/bus/usb:/dev/bus/usb \
  -e CUPSADMIN="admin" \
  -e CUPSPASSWORD="admin" \
  -e TZ="Europe/Amsterdam" \
  -v <some path>/services:/services \
  -v <some path>/cups/config:/config \
  -v /var/run/dbus/system_bus_socket:/var/run/dbus/system_bus_socket \
  -v /etc/localtime:/etc/localtime:ro \
  --dns=<your internal dns server> \
  xirixiz/cups-airprint:latest
```
