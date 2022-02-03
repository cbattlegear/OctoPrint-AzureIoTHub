$(function() {
    function IotHubViewModel(parameters) {
        var self = this;

        self.global_settings = parameters[0];
        self.iotHubStatus = ko.observable("");

        self.onBeforeBinding = function () {
            self.settings = self.global_settings.settings.plugins.navbartemp;
        };

        self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin != "azureiothub") {
                return;
            }

            if (data.iot_hub_status) {
                if (data.iot_hub_status == "Connected") {
                    if(data.iot_hub_message_number) {
                        self.iotHubStatus("IoT Hub Connected - Message #" + data.iot_hub_message_number);
                    } else {
                        self.iotHubStatus("IoT Hub Connected");
                    }
                    
                } else if (data.iot_hub_status == "Disconnected") {
                    self.iotHubStatus("IoT Hub Disconnected - Error: " + data.iot_hub_error);
                } else if (data.iot_hub_status == "Unconfigured") {
                    self.iotHubStatus("Connection String Not Configured")
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