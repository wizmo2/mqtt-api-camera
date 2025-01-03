# MQTT API Camera

Use the 'mqtt-api' HA custom camera component to provide instant-to-instant support for entity_pictures using mqtt statestream.  For example, live camera feeds or media player images

## Configuration

To enable this camera in your installation, add the following to your `configuration.yaml` file:

```yaml
# Example configuration.yaml entry
camera:
  - platform: mqtt-api
    host: http://192.168.1.1:8123
    state_topic: /topic/camera/entity_picture
```

{% configuration %}
name:
  description: This parameter allows you to override the name of your camera.
  required: false
  type: string
framerate:
  description: The number of frames-per-second (FPS) of the stream. Can cause heavy traffic on the network and/or heavy load on the camera.
  required: false
  type: integer

{% endconfiguration %}

## Examples

In this section, you find some real-life examples of how to use this camera platform.

### Sharing a camera feed from one Home Assistant instance to another

If you are running more than one Home Assistant instance (let's call them the 'host' and 'receiver' instances) you may wish to display the camera feed from the host instance on the receiver instance. You can use the [REST API](https://developers.home-assistant.io/docs/api/rest/#get-apicamera_proxycameraentity_id) to access the camera feed on the host (IP address 127.0.0.5; Port 8123) using [mqtt_statestream](https://www.home-assistant.io/integrations/mqtt_statestream/) and display it on the receiver instance by configuring the receiver with the following:

```yaml
mqtt_statestream:
  base_topic: topic
  include:
    domains:
      - camera
      - amcrest

camera:
  - platform: mqtt-api
    name: My Camera
    host: http://127.0.0.5:8123
    state_topic: /topic/camera/entity_picture
```
