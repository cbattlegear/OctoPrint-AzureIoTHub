$(function() {
    function IotHubViewModel(parameters) {
        var self = this;

        self.global_settings = parameters[0];
        self.iotHubStatus = ko.observable("");
        self.iotHubStatusClass = ko.observable("");

        self.onBeforeBinding = function () {
            self.settings = self.global_settings.settings.plugins.azureiothub;
            self.iotHubStatus("Waiting For Status");
            self.iotHubStatusClass("navbar_iothub_status_unconfigured");
        };

        self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin != "azureiothub") {
                return;
            }

            if (data.iot_hub_status) {
                if (data.iot_hub_status == "Connected") {
                    if(data.iot_hub_message_number) {
                        self.iotHubStatus("IoT Hub Connected - Message #" + data.iot_hub_message_number);
                        self.iotHubStatusClass("navbar_iothub_status_online");
                    } else {
                        self.iotHubStatus("IoT Hub Connected");
                        self.iotHubStatusClass("navbar_iothub_status_online");
                    }
                    
                } else if (data.iot_hub_status == "Disconnected") {
                    self.iotHubStatus("IoT Hub Disconnected - Error: " + data.iot_hub_error);
                    self.iotHubStatusClass("navbar_iothub_status_offline");
                } else if (data.iot_hub_status == "Unconfigured") {
                    self.iotHubStatus("Connection String Not Configured");
                    self.iotHubStatusClass("navbar_iothub_status_unconfigured");
                } else if (data.iot_hub_status == "Printer Disconnected") {
                    self.iotHubStatus("Printer Not Connected - No Telemetry Being Sent");
                    self.iotHubStatusClass("navbar_iothub_status_warning");
                }
                
            }
        };

    }

    OCTOPRINT_VIEWMODELS.push({
        construct: IotHubViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#navbar_plugin_azureiothub"]
    });
});