$(function() {
    function IotHubViewModel(parameters) {
        var self = this;

        self.settings = parameters[0];
        self.iotHubStatus = ko.observable("");
        self.iotHubStatusClass = ko.observable("");
        self.showIotHubStatus = ko.observable();

        self.onBeforeBinding = function () {
            self.iotHubStatus("Waiting For Status");
            self.iotHubStatusClass("navbar_iothub_status_unconfigured");
            if(self.settings.settings.plugins.azureiothub.display_status_icon() == false) {
                self.showIotHubStatus(false);
            } else {
                self.showIotHubStatus(true);
            }
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
                    self.iotHubStatus("Check Configuration Settings");
                    self.iotHubStatusClass("navbar_iothub_status_unconfigured");
                } else if (data.iot_hub_status == "Printer Disconnected") {
                    self.iotHubStatus("Printer Not Connected - No Telemetry Being Sent");
                    self.iotHubStatusClass("navbar_iothub_status_warning");
                }
                
            }
        };

        self.onSettingsHidden = function () {
            if(self.settings.settings.plugins.azureiothub.display_status_icon() == false) {
                self.showIotHubStatus(false);
            } else {
                self.showIotHubStatus(true);
            }
        };

    }

    OCTOPRINT_VIEWMODELS.push({
        construct: IotHubViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#navbar_plugin_azureiothub"]
    });
});