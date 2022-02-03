# coding=utf-8
from __future__ import absolute_import
import asyncio

import json
import re
import uuid

from azure.iot.device.aio import IoTHubDeviceClient
from azure.iot.device import Message

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

    # Create our IoT Device client, data holder, and message counter 
    # I may have to worry if it runs a REALLY long time that I overflow the count
    # Even if it's every second though that would be 68 years...so only those Unix
    # timestamp people need to worry about that
    def __init__(self):
        self._device_client = None
        self.iot_data = {}
        self._message_count = 0
        self._iot_hub_error_message = ""
        self._iot_hub_status = "Disconnected"

    # Tell Octoprint we will are using callbacks
    def initialize(self):
        self._printer.register_callback(self)

    ##~~ SettingsPlugin mixin
    # Set the defaults for your Octoprint settings
    def get_settings_defaults(self):
        return dict(
            connection_string = "",
            send_interval = 10
            # put your plugin's default settings here
        )

    # IoT Hub Status Tracking
    def iot_hub_status(self):
        if self._settings.get(["connection_string"]) == "":
            self._plugin_manager.send_plugin_message(self._identifier,
                dict(iot_hub_status="Unconfigured"))
            self._iot_hub_status = "Unconfigured"
            return
        if self._iot_hub_status == "Disconnected":
            self._plugin_manager.send_plugin_message(self._identifier,
                dict(iot_hub_status=self._iot_hub_status, iot_hub_error=self._iot_hub_error_message))
            return
        if self._iot_hub_status == "Connected" and self._printer.get_current_connection()[0] == "Closed":
            self._plugin_manager.send_plugin_message(self._identifier,
                dict(iot_hub_status="Printer Disconnected", iot_hub_error="No telemetry being sent"))
            return
        if self._iot_hub_status == "Connected":
            self._plugin_manager.send_plugin_message(self._identifier,
                dict(iot_hub_status=self._iot_hub_status, iot_hub_message_number=self._message_count))
            return

    # Status push timer
    def iot_hub_status_timer(self):
        self._iot_status_timer = octoprint.util.RepeatedTimer(10, self.iot_hub_status)
        self._iot_status_timer.start()

    # When we save the settings, if we have a new connection string, kill and restart
    # the connection to IoT Hub
    def on_settings_save(self, data):
        # This tripped me up you have to get your settings which gets the old settings
        # then run the on settings save again which then gets the new settings
        # I don't even pretend to understand it.
        old_conn_string = self._settings.get(["connection_string"])
        old_int = self._settings.get_int(["send_interval"])

        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)

        new_conn_string = self._settings.get(["connection_string"])
        new_int = self._settings.get_int(["send_interval"])

        if old_conn_string != new_conn_string:
            if len(new_conn_string) > 0:
                self.connect_to_iot_hub_asyncio()

    # Our timer to push telemetry on schedule
    def start_iot_timer(self, interval):
        self._iot_timer = octoprint.util.ResettableTimer(interval, self.periodic_data_wrapper)
        self._iot_timer.start()

    # Wrapper to handle async threads because the Timer function cannot run coroutines
    def periodic_data_wrapper(self):
        asyncio.run(self.send_periodic_telemetry_data())
        self.start_iot_timer(self._settings.get_int(["send_interval"]))

    # This does the actual sending (finally)
    # This fires based on your interval setting and grabs the current state of the printer
    async def send_periodic_telemetry_data(self):
        if self._printer.get_current_connection()[0] != "Closed" and self._device_client.connected:
            self._message_count += 1
            iot_dict = self.iot_data_json_prep()
            msg = Message(json.dumps(iot_dict))
            msg.message_id = uuid.uuid4()
            msg.correlation_id = "correlation-" + str(self._message_count)
            msg.content_encoding = "utf-8"
            msg.content_type = "application/json"
            self._logger.info("IoT Hub Telemetry Message #%d" % self._message_count)
            # Because we are good people we use a try/except here to prevent crashing Octoprint
            try:
                # This sends the actual telemetry message to IoT Hub
                await self._device_client.send_message(msg)
                self._iot_hub_status = "Connected"
            except Exception as e:
                error_msg = "Could not send IoT Telemetry Message"
                self._logger.error(error_msg)
                self._logger.error(str(e))
                self._iot_hub_status = "Disconnected"
                self._iot_hub_error_message = error_msg
            if "temperature" in iot_dict:
                try:
                    # This sets the digital twin current state, just doing temperatures currently
                    # TODO: Make this customizable information
                    await self._device_client.patch_twin_reported_properties(iot_dict["temperature"])
                except Exception as e:
                    error_msg = "Could not send Device twin update"
                    self._logger.error(error_msg)
                    self._logger.error(str(e))
                    self._iot_hub_status = "Disconnected"                    
                    self._iot_hub_error_message = error_msg

    # This sends events (such as printing starting) to IoT Hub
    # TODO: Allow event selection
    async def send_event_telemetry_data(self, message):
        if self._device_client.connected:
            self._message_count += 1
            msg = Message(message)
            msg.message_id = uuid.uuid4()
            msg.correlation_id = "correlation-" + str(self._message_count)
            msg.content_encoding = "utf-8"
            msg.content_type = "application/json"
            self._logger.info("IoT Hub Event Message #%d" % self._message_count)
            try:
                await self._device_client.send_message(msg)
                self._iot_hub_status = "Connected"
            except Exception as e:
                error_msg = "Could not send IoT Event Message"
                self._logger.error(error_msg)
                self._logger.error(str(e))
                self._iot_hub_status = "Disconnected"                    
                self._iot_hub_error_message = error_msg

    # The data provided in the callback is an immutabledict json doesn't like that
    # It also doesn't have the temperature data, so I don't like that
    # I unimmutabl...ize? the immutabledict, change the state section to be more succinct
    # and add the temperature data
    def iot_data_json_prep(self):
        thawed = octoprint.util.thaw_immutabledict(self.iot_data)
        thawed['state'] = self._printer.get_state_string()
        thawed['temperature'] = self._printer.get_current_temperatures()
        return thawed

    # If we catch one of the events listed below, throw it up to IoT Hub
    def on_event(self, event, payload):
        if event == 'PrintStarted' or event == 'PrintFailed' or event == 'PrintDone' or event == 'PrintCancelled':
            payload['print_event'] = event
            asyncio.run(self.send_event_telemetry_data(json.dumps(payload)))
    
    # If we are starting up, we should probably try to connect to IoT hub and start sending data
    def on_after_startup(self):
        self.connect_to_iot_hub_asyncio()
        self.iot_hub_status_timer()

    def connect_to_iot_hub_asyncio(self):
        # Added loop check for Async calls to resolve Issue #1
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            conn_task = asyncio.ensure_future(self.connect_to_iot_hub())
            conn_task.add_done_callback(self.check_iot_connection)
        else:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            conn_task = asyncio.ensure_future(self.connect_to_iot_hub())
            conn_task.add_done_callback(self.check_iot_connection)
            loop.run_until_complete(conn_task)
            loop.close()

    def check_iot_connection(self, result):
        if result.result():
            interval = self._settings.get_int(["send_interval"])
            self.start_iot_timer(interval)
            #self._device_client.on_twin_desired_properties_patch_received = twin_patch_handler
            #self._device_client.on_message_received = message_received_handler

    # Primary connection process for IoT Hub
    # If the connection string isn't set in settings, return false, don't retry
    # If connection string is set, attempt to connect, if it succeeds return True
    # if it fails, retry in a minute, return False
    async def connect_to_iot_hub(self):
        conn_string = self._settings.get(["connection_string"])
        if len(conn_string) > 0:
            if self._device_client and self._device_client.connected:
                await self._device_client.disconnect()
            try:
                if len(conn_string) > 0:
                    self._device_client = IoTHubDeviceClient.create_from_connection_string(conn_string)
                    await self._device_client.connect()
                    self._iot_hub_status = "Connected"
                    return True
            except Exception as e:
                error_msg = "Could not connect to Azure IoT Hub with given connection string"
                self._logger.error(error_msg)
                self._logger.error(str(e))
                self.start_connection_retry_timer(60)
                self._iot_hub_status = "Disconnected"                    
                self._iot_hub_error_message = error_msg
                return False
        else:
            return False

    # Retrying in Azure is important, so this is the timer to make sure we try again
    def start_connection_retry_timer(self, interval):
        self._connection_retry_timer = octoprint.util.ResettableTimer(interval, self.connect_to_iot_hub_asyncio)
        self._connection_retry_timer.start()

    # Remember that callback being enabled 180 lines ago? This is where we fire it
    # It is grabbing the data sent from the printer and saving it in the iot_data variable
    def on_printer_send_current_data(self, data):
        self.iot_data = data

    # I assume I will need to use this soon because I want to add a small toolbar indicator of status
    # TODO: Add IoT Hub status icon/toolbar to UI
    ##~~ AssetPlugin mixin

    def get_assets(self):
        # Define your plugin's asset files to automatically include in the
        # core UI here.
        return {
            "js": ["js/azureiothub.js"],
            "css": ["css/azureiothub.css"]
        }

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
