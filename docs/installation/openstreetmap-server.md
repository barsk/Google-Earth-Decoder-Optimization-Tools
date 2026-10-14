# Local OpenStreetMap server (recommended)

Steps 3 to 5 and the landmarks tool query OpenStreetMap through an **Overpass** server. The public servers work for a
small scenery, but a whole city sends many large queries, and the public servers then throttle them or block the IP
address for a while: the steps fail half way. A local Overpass server, running in Docker with an extract of your
country, removes that problem: no limits, faster answers, and the same data at every run.

It is optional, but recommended for anything bigger than a few tiles.

## What you need

* **[Docker Desktop](https://www.docker.com/products/docker-desktop/)** for Windows (WSL 2 backend). It must be running
  whenever steps 3 to 5 or the landmarks tool run.
* **An OpenStreetMap extract** of the region of your sceneries, as a `.osm.pbf` file, e.g. from
  [Geofabrik](https://download.geofabrik.de/) (`https://download.geofabrik.de/europe/sweden-latest.osm.pbf`).
* **Disk space** for the database: about 9 GB for Sweden. Most of it is index tables sized by the worldwide
  OpenStreetMap ids, so a small country isn't much smaller.

## Create the server

The [`wiktorn/overpass-api`](https://hub.docker.com/r/wiktorn/overpass-api) image downloads the extract and builds the
database on its first start. In PowerShell:

```
docker run -d --name overpass --restart unless-stopped -p 12345:80 `
  -v overpass-db:/db `
  -e OVERPASS_MODE=init `
  -e OVERPASS_PLANET_URL=https://download.geofabrik.de/europe/sweden-latest.osm.pbf `
  -e OVERPASS_META=no `
  -e OVERPASS_COMPRESSION=lz4 `
  -e OVERPASS_USE_AREAS=false `
  -e OVERPASS_FASTCGI_PROCESSES=16 `
  -e OVERPASS_RATE_LIMIT=64 `
  -e OVERPASS_MAX_TIMEOUT=1800 `
  -e OVERPASS_STOP_AFTER_INIT=false `
  wiktorn/overpass-api
```

* `OVERPASS_META=no`, `OVERPASS_USE_AREAS=false`: GEDOT needs neither the metadata (authors, versions) nor the area
  index (it queries by bounding box and polygon), and both make the database much bigger and slower to build.
* `OVERPASS_FASTCGI_PROCESSES`, `OVERPASS_RATE_LIMIT`: room for GEDOT's parallel tasks.
* `--restart unless-stopped`: the server starts with Docker Desktop.

The first start takes a while (download and import). Follow it with `docker logs -f overpass`, until the server
answers:

```
curl http://localhost:12345/api/status
```

## Use it in GEDOT

Set *Uri of the Overpass API* in the addon preferences (or `overpass_api` in `GEDOT.ini`) to:

```
http://localhost:12345/api
```

The OpenStreetMap API (the outlines of the landmarks), Nominatim (the geocode tools and the airport city) and Wikidata
(the notability of the landmarks) are still used online. They see little traffic and don't need a local copy.

## Pitfalls

* **"Permission denied" on `/db/db//osm3s_osm_base`:** the volume's root folder came up readable by its owner only.
  Fix it once:

  ```
  docker exec -u root overpass chmod 755 /db
  ```

* **The same query repeated within a few minutes** gets an HTML error page instead of data (the server's duplicate
  query check). GEDOT retries such queries by itself, after a pause.
* **A scenery outside the extract** gets no data. Import a larger region, or run a second server with another extract
  on another port.
* **Nothing happens in steps 3 to 5:** check that Docker Desktop is running (`docker ps`) and that the status URL above
  answers.

## Updates

The server above doesn't update itself. The Google Earth 3D data is years old anyway, so the extract's date rarely
matters. To bring the database up to date, apply Geofabrik's daily changes (here for Sweden):

```
docker exec -u overpass -e OVERPASS_DIFF_URL=https://download.geofabrik.de/europe/sweden-updates/ overpass /app/bin/update_overpass.sh
```

"Error while downloading diffs" means that there is nothing new. To update automatically instead, add
`-e OVERPASS_DIFF_URL=<the updates URL of your extract>` when creating the container.
