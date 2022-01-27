# coding=utf-8
from __future__ import absolute_import
import asyncio

import json
import uuid

from azure.iot.device.aio import IoTHubDeviceClient
from azure.iot.device import Message

### (Don't forget to remove me)
# This is a basic skeleton for your plugin's __init__.py. You probably want to adjust the class name of your plugin
# as well as the plugin mixins it's subclassing from. This is really just a basic skeleton to get you started,
# defining your plugin as a template plugin, settings and asset plugin. Feel free to add or remove mixins
# as necessary.
#
# Take a look at the documentation on what other plugin mixins are available.

import octoprint.plugin
import octoprint.util

class AzureiothubPlugin(octoprint.plugin.SettingsPlugin,
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.ShutdownPlugin,
    octoprint.plugin.EventHandlerPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.printer.PrinterCallback
):

    def __init__(self):
        self._device_client = None
        self.iot_data = {}
        self._message_count = 0
        self._printer_connected = False

    def initialize(self):
        self._printer.register_callback(self)

    ##~~ SettingsPlugin mixin

    def get_settings_defaults(self):
        return dict(
            connection_string = "",
            send_interval = 10
            # put your plugin's default settings here
        )

    def on_settings_save(self, data):
        old_conn_string = self._settings.get(["connection_string"])
        old_int = self._settings.get_int(["send_interval"])

        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)

        new_conn_string = self._settings.get(["connection_string"])
        new_int = self._settings.get_int(["send_interval"])

        if old_conn_string != new_conn_string:
            if self._device_client:
                self._device_client.shutdown()
            if len(new_conn_string) > 0:
                self._device_client = IoTHubDeviceClient.create_from_connection_string(new_conn_string)
                loop = asyncio.get_event_loop()
                loop.run_until_complete(self._device_client.connect())
                self.start_iot_timer(new_int)

    def start_iot_timer(self, interval):
        self._iot_timer = octoprint.util.ResettableTimer(interval, self.periodic_data_wrapper)
        self._iot_timer.start()

    def periodic_data_wrapper(self):
        asyncio.run(self.send_periodic_telemetry_data())
        self.start_iot_timer(self._settings.get_int(["send_interval"]))

    
    async def send_periodic_telemetry_data(self):
        if self._printer_connected:
            self._message_count += 1
            iot_dict = self.iot_data_json_prep()
            msg = Message(json.dumps(iot_dict))
            msg.message_id = uuid.uuid4()
            msg.correlation_id = "correlation-" + str(self._message_count)
            msg.content_encoding = "utf-8"
            msg.content_type = "application/json"
            self._logger.info("IoT Hub Telemetry Message #%d" % self._message_count)
            await self._device_client.send_message(msg)
            if "temperature" in iot_dict:
                await self._device_client.patch_twin_reported_properties(iot_dict["temperature"])

    async def send_event_telemetry_data(self, message):
        self._message_count += 1
        msg = Message(message)
        msg.message_id = uuid.uuid4()
        msg.correlation_id = "correlation-" + str(self._message_count)
        msg.content_encoding = "utf-8"
        msg.content_type = "application/json"
        self._logger.info("IoT Hub Event Message #%d" % self._message_count)
        await self._device_client.send_message(msg)

    def iot_data_json_prep(self):
        thawed = octoprint.util.thaw_immutabledict(self.iot_data)
        thawed['state'] = self._printer.get_state_string()
        thawed['temperature'] = self._printer.get_current_temperatures()
        return thawed

    def on_event(self, event, payload):
        if event == 'Connected':
            self._printer_connected = True
        if event == 'Disconnected':
            self._printer_connected = False
        if event == 'PrintStarted' or event == 'PrintFailed' or event == 'PrintDone' or event == 'PrintCancelled':
            payload['print_event'] = event
            asyncio.run(self.send_event_telemetry_data(json.dumps(payload)))

    ##~~ AssetPlugin mixin

    #def get_assets(self):
        # Define your plugin's asset files to automatically include in the
        # core UI here.
    #    return {
    #        "js": ["js/azureiothub.js"],
    #        "css": ["css/azureiothub.css"],
    #        "less": ["less/azureiothub.less"]
    #    }
    
    def on_after_startup(self):
        conn_string = self._settings.get(["connection_string"])
        if len(conn_string) > 0:
            self._device_client = IoTHubDeviceClient.create_from_connection_string(conn_string)
            try:
                asyncio.run(self._device_client.connect())
            except Exception as e:
                self._logger.info(str(e))

            if self._device_client.connected:
                self._logger.info("Successfully Connected to IoT Hub")
            interval = self._settings.get_int(["send_interval"])
            self.start_iot_timer(interval)
            #self._device_client.on_twin_desired_properties_patch_received = twin_patch_handler
            #self._device_client.on_message_received = message_received_handler

    def on_printer_send_current_data(self, data):
        self.iot_data = data

    def get_template_configs(self):
        return [
            dict(type="settings", custom_bindings=False)
        ]

    ##~~ Softwareupdate hook

    def get_update_information(self):
        # Define the configuration for your plugin to use with the Software Update
        # Plugin here. See https://docs.octoprint.org/en/master/bundledplugins/softwareupdate.html
        # for details.
        return {
            "azureiothub": {
                "displayName": "Azureiothub Plugin",
                "displayVersion": self._plugin_version,

                # version check: github repository
                "type": "github_release",
                "user": "cbattlegear",
                "repo": "OctoPrint-AzureIoTHub",
                "current": self._plugin_version,

                # update method: pip
                "pip": "https://github.com/cbattlegear/OctoPrint-AzureIoTHub/archive/{target_version}.zip",
            }
        }


# If you want your plugin to be registered within OctoPrint under a different name than what you defined in setup.py
# ("OctoPrint-PluginSkeleton"), you may define that here. Same goes for the other metadata derived from setup.py that
# can be overwritten via __plugin_xyz__ control properties. See the documentation for that.
__plugin_name__ = "Azure IoT Hub Plugin"

# Starting with OctoPrint 1.4.0 OctoPrint will also support to run under Python 3 in addition to the deprecated
# Python 2. New plugins should make sure to run under both versions for now. Uncomment one of the following
# compatibility flags according to what Python versions your plugin supports!
#__plugin_pythoncompat__ = ">=2.7,<3" # only python 2
__plugin_pythoncompat__ = ">=3,<4" # only python 3
#__plugin_pythoncompat__ = ">=2.7,<4" # python 2 and 3

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = AzureiothubPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }
