# HuePlanner

> The most overengineered way to turn on your lightbulb

hueplanner is a simple, declarative system I built to make automating Philips Hue lights easier. Whether you want to set up schedules, respond to button presses, or trigger actions through HTTP requests, hueplanner helps you control your lights with just a .yaml config file.

You can use it for everything from syncing your lights with natural daylight cycles to creating custom automations based on events or webhooks. No need for heavy home automation setups—just write your rules and let hueplanner handle the rest. It's flexible, lightweight, and designed to fit around your life.

---

### Why choose hueplanner?

- **Focused Purpose**: When you don’t need a full-fledged home automation system and just want smart, feature-rich control over your lights, hueplanner is a great fit.
- **Easy Deployment**: Have a place to run a single Docker container? That’s all you need to get hueplanner up and running.
- **Declarative Configuration**: Enjoy the power and flexibility of config-based automations. Define your lighting plans using simple `.yaml` files.
- **Extensibility**: Hueplanner is designed to be extendable. Want to trigger your lights based on stock prices or other external data? With a bit of customization, it's possible!

### Why might hueplanner not be for you?

- **No Desktop or Mobile App**: Hueplanner doesn’t have a user-friendly UI. It’s designed to run on a server, preferably within your local network.
- **Declarative Approach**: If you’re not comfortable learning hueplanner’s domain-specific language (DSL) for configuring automations, this may not be the tool for you.
- **Not a Hue SDK**: Hueplanner is not a Hue SDK for Python. If you're looking for a dedicated SDK, this isn’t it, but feel free to borrow code from hueplanner’s implementation of Hue API libraries.
- **Early Development**: Hueplanner is a small hobby project with limited test coverage. It’s still evolving, so you may encounter bugs as it matures.
- **Limited Action Support**: Currently focused on circadian lighting automation, hueplanner may lack advanced actions for other areas of the Hue ecosystem. Contributions to expand its functionality are welcome!

---

## Dive in

Let's start with simple config file

```yaml
# hueplanner.yaml

settings:
  hue_bridge:
    addr: "192.168.0.123"
    username: "<your HUE bridge access token>"

plan:
  - trigger:
      type: Immediately  # Do something immediately
    action:
      type: StoreSceneByName  # We will store some scene in memory, so button press below will have scene to toggle.
      args:
          name: "Energize"
          store_as: "my_scene"

  - trigger:
      type: Once  # do something just once
      args:
        time: "12:00"
    action:
      type: StoreSceneByName  # We store another scene at 12:00
      args:
          name: "Concentrate"
          store_as: "my_scene"
          activate: True  # also activate this scene (if lights are on)

  - trigger:
      type: OnHueButtonEvent  # handling button press on the sensor
      args:
        action: "short_release"
        resource_id: "1e53050b-ca07-44f3-977f-ab0477e5e911"
    action:
      type: ToggleStoredScene  # toggle scene lights. Toggles scene, stored by some previous actions
      args:
        db_key: "my_scene"

  - trigger:
      type: Minutely  # do something every minute, starting from next one
    action:
      type: UpdateLightV2  # V2, because we are using v2 api and v2 identifiers
      args:
        id: "08d6350b-fb3f-4dc1-b6cc-62350d8f4f10"
        update: {"identify": {"action": "identify"}}  # let's just blink lightbulb on this trigger

```

Interested in something really functional, not just dummy example? Please check [examples](./examples) folder!

So, let's start application:

```bash
docker run --rm -v $(pwd)/config_ioc.yaml:/hueplanner/hueplanner.yaml:ro -e CONFIG_FILE='./hueplanner.yaml' ghcr.io/dokzlo13/hueplanner:latest
```

If you have repository cloned and all dependencies installed, you can simply run

```bash
python main.py --config ./hueplanner.yaml
```

---

## Motivation

A while ago, I purchased a Philips HUE hub along with some smart lamps to create ambient lighting for my room. My favorite feature was the "Natural Light" mode, which allows for circadian lighting—a great benefit when working long hours at a PC.

However, I soon encountered an issue. When using one of the [Philips Hue Dimmer Switches](https://www.philips-hue.com/en-gb/p/hue-dimmer-switch/8719514274617), turning the lights off would not save the current "Natural Light" scene. For example, if I turned the lights off while in "Night Light" mode before going to bed, the next morning, turning the lights back on would leave them stuck in "Night Light" mode instead of switching to the "Energize" scene.

I wanted a solution where the lights would automatically revert to the "Natural Light" scene based on the time of day whenever they were turned on.

Although there are comprehensive home automation solutions available, such as [Home Assistant](https://www.home-assistant.io/), I found them too complex for my specific needs. My goal was simple: improved automation logic for my remote and lamps. Configuring Home Assistant just to set up [flux](https://www.home-assistant.io/integrations/flux/) felt like overkill.

This led me to spend hundreds of hours designing and developing my own automation system.

I initially created a basic Python script that would adjust the lighting scene based on astronomical events for my location, thanks to the [Astral](https://github.com/sffjunkie/astral) library. It also responded to button presses to toggle the lights. I deployed it as a Docker container on my NAS, and everything worked fine—until winter arrived.

Living in the far north, our winters are long and dark. I noticed that the lights would dim too early in the day, and I wanted to extend the daylight hours by applying an offset to the dimming schedule. But as summer approached, I realized I'd need to revert all these changes, which felt cumbersome.

That’s when I decided to go declarative.

I began developing **hueplanner**, a more advanced system that could be easily configured using a declarative approach. This is how **hueplanner** was born.

### Hueplanner declarative approach

**hueplanner** is a declarative automation system designed specifically for Philips Hue. It operates by reading `.yaml` configuration files that define a "plan" using a domain-specific language (DSL). The system works based on the following key principles:

- A "plan" consists of a list of **PlanEntries**.
- Each **PlanEntry** defines:
  - One trigger: an event such as a scheduled time or an event from the Hue hub.
  - One or more actions: operations like toggling lights, changing scenes, etc.
- When a trigger is activated, the corresponding action(s) are executed.

In short, **hueplanner** allows you to automate your Philips Hue lights using a simple, flexible configuration.

---

## Deployment


### Settings

Hueplanner connects to one HUE bridge, this is required dependency.

Here is minimal required config:

```yaml
settings:
  hue_bridge:
    addr: "<HUE bridge IP>"
    username: "<your HUE bridge access token>"
```

Here is list of all available settings:

```yaml
settings:
  tz: Europe/Berlin  # timezone
  hue_bridge:
    addr: "<HUE bridge IP>"
    username: "<your HUE bridge access token>"
  log:
    level: info  # log level: critical, error, warning, info, debug
    colors: true # you may disable log coloring for log-collection systems
  database:
   # path to sqlite database. If not provided, app will run in memory-only mode.
    path: ./hueplanner.sqlite
  # Exposes http://0.0.0.0:9090/healt/live and http://0.0.0.0:9090/healt/ready for health probes
  healthcheck:   # If this section not provided, healthcheck will be disabled
    host: 0.0.0.0
    port: 9090
```

### Environment variables substitution

To prevent storing secrets within config file, hueplanner resolves the environment variables you provide:

```yaml
settings:
  hue_bridge:
    addr: "192.168.0.123"
    # You can use environment substitution anywhere in the config.
    username: ${HUE_ACCESS_TOKEN}
  log:
    # If no env variable provided, fallback value "debug" will be used
    level: ${LOG_LEVEL:debug}
  database:
    path: ${DB_PATH}  # path to sqlite database. If not provided, app will run in memory-only mode.

plan:
  - trigger:
      type: OnHueButtonEvent
      args:
        action: "initial_press"
        resource_id: ${MY_BUTTON_ID}  # You can substitute values in plan too!
    action: ...
```


### Docker-compose deployment

Here is example of docker-compose file, used for synology NAS "Container Manager":

```yaml
version: '3'

services:
  hueplanner:
    image: ghcr.io/dokzlo13/hueplanner
    container_name: hueplanner
    restart: unless-stopped
    user: 1028:65536
    network_mode: host
    environment:
      - TZ=Europe/Berlin
      - LOG_LEVEL=info
      - LOG_COLORS=false
      - HUE_BRIDGE_ADDR=192.168.10.12
      - HUE_BRIDGE_USERNAME=...
      - DATABASE_PATH=/app/data/hueplanner.sqlite
      - CONFIG_FILE=/app/data/hueplanner.yaml
      - PYTHONUNBUFFERED=1
    logging:
      options:
        max-size: "100m"
        max-file: "1"
    volumes:
      - /volume0/docker/volumes/hueplanner:/app/data/
```

And here is config file head:

```yaml
settings:
  tz: ${TZ}
  log:
    level: ${LOG_LEVEL:info}
    colors: ${LOG_COLORS:false}
  database:
    path: ${DATABASE_PATH}
  hue_bridge:
    addr: ${HUE_BRIDGE_ADDR}
    username: ${HUE_BRIDGE_USERNAME}
plan: ...
```

---

> ⚠️**README IS UNDER CONSTRUCTION!** ⚠️
