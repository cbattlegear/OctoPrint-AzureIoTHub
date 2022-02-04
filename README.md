# OctoPrint-AzureIoTHub

The Azure IoT Hub plugin allows for direct telemetry ingestion into Azure IoT Hub directly from OctoPrint. 

With Azure IoT Hub you can get time series data directly into the cloud, device data about your printer, messages back to OctoPrint, and Device Twinning to let you quickly see data about your printer. 

Turn your printer into a true IoT Device with the Azure IoT Hub plugin.

## Setup

Install Manually using this URL:

    https://github.com/cbattlegear/OctoPrint-AzureIoTHub/archive/main.zip

**Coming Soon:** Integrated Plugin Manager installation

## Configuration

All you need to get this working is an Azure IoT Hub device connection string. If you don't already have an Azure IoT Hub setup you can [follow the Microsoft Documentation to create one](https://docs.microsoft.com/en-us/azure/iot-hub/iot-hub-create-through-portal). 

Once that is created you can create your IoT Devices by [following these provided instructions](https://docs.microsoft.com/en-us/azure/iot-hub/iot-hub-create-through-portal#register-a-new-device-in-the-iot-hub)

Once you have your Device Connection string, copy it into the IoT Hub Connection String setting in the Azure IoT Hub Plugin settings area. Once saved, your device will begin sending telemetry!
