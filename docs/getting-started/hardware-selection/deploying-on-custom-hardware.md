# Deploying on Custom Hardware

In order to deploy onto custom hardware, make sure the hardware you choose for your coprocessor supports the following features:

* _Some_ pakcage manager that has the ability to download `libopencv` onto the processor, this is required in order for the runtime to do any sort of image processing. Common ones include: apt, dpkg, dnf, yum, pacman and apk
* Python  >=3.9, <3.12 In order to be able to install all the python dependencies of Synapse
* Have a supported version of `robotpy` able to be installed onto it
* SSH capabilities, required in order to deploy code onto the coprocessor
* `netplan` in order to be able to set a [Static IP](#user-content-fn-1)[^1] on the device.

[^1]: a permanent, unchanging network address assigned to a device
