---
icon: down-to-line
---

# Installing Software

## Coprocessor Installation

### Imaging A Device

{% hint style="info" %}
Currently there are no images that come preinstalled with the Synapse runtime, but it is a feature that is planned to be added in the future! Feel free to contribute to Synapse and add this feature in yourself by creating a PR on [GitHub](https://github.com/DanPeled/Synapse)
{% endhint %}

#### Imaging Software

The recommended software in order to image a device's Operating system into a storage device is [Blena Etcher](https://etcher.balena.io/)

#### Suggested images:

* Orange Pi 5 - [Bookworm Armbian 25.5.1](https://distrohub.kyiv.ua/armbian-dl/orangepi5/archive/Armbian_25.5.1_Orangepi5_bookworm_vendor_6.1.115_minimal.img.xz)
* Rasberry Pi -[ Bookworm Armbian 25.5.1](https://www.armbian.com/rpi4b/) (Instructions included)

### Device Install

First, you will need to have a local project set-up, please read [#development-computer-installation](installing-software.md#development-computer-installation "mention") and [project-management](../usage/project-management/ "mention").

Now, you will need to have the coprocessor connected to the same internet access point (with internet access) as your development computer.

#### Getting Your IP Address

In order to get your device's IP address, you can run the following command in the coprocessors terminal

```bash
ip a
```

This will show you the device's IP address below the interface subsection.

Now, we need to configure our deployment device [#adding-processors](../usage/project-management/#adding-processors "mention").

Finally, we can call the installation command:

```bash
<pythonexec> -m synapse_installer install <coprocessor nickname>
```

This will install all the requirement's onto the coprocessor and deploy your local project onto it.

## Development Computer Installation

In order to install the python library on your development machine in order to create a project and configure deployment devices, run the following command:

{% code fullWidth="false" %}
```bash
pip install synapsefrc
```
{% endcode %}

This will be enough in order to be able to use the library on your local machine!\
In order to create a project, read [project-management](../usage/project-management/ "mention")
