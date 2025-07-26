---
icon: gears
---

# Common Hardware Setups

## Coprocessors

* Orange Pi 5
  * 2x 2.0USB Ports, 1x 3.0USB port, Up to 2.4Ghz out of the box
  * Type-C power supply 5V @ 4A
  * Can be powered via the GPIO pins
  * 4GB/8GB/16GB of RAM
* Rasberry Pi 5&#x20;
  * 2x 2.0USB Ports, 2x 3.0USB ports, Up to 2.4Ghz out of the box
  * Type-C power supply 5V @ 5A
  * Can be powered via the GPIO pins
  * PoE+ support (requires separate PoE+ HAT)
  * Up to 16GB of RAM

{% hint style="info" %}
This project will work on any Linux-Compatible device as a coprocessor in order to have full advantage of all the capabilities of the system, but not all coprocessor options have been tested so far.

See [installing-software.md](../installing-software.md "mention") for manual installation steps
{% endhint %}

## SD Cards

* 8GB Or larger micro SD card&#x20;

Industrial grade SD cards from major manufacturers are recommended for robotics applications. For example: Sandisk SDSDQAF3-016G-I.

{% hint style="info" %}
Will mostly depend on the OS of your choosing, the provided images will require atleast 3GB of storage
{% endhint %}

## Cameras

* AprilTag Detection
  * OV9281&#x20;
    * Has a physical focus tuner
    * Monochromatic (Only Black and White)
* Color Detection
  * OV9728
    * Has a physical focus tuner

Feel free to get started with any color webcam you have sitting around.

{% hint style="info" %}
Any generic USB camera will be compatible with Synapse out of the box.
{% endhint %}

## Power

* Pololu S13V30F5 Regulator
* Redux Robotics Zinc-V Regulator
* Belkin Boost Charger
  * _Since its an external power supply, it is **less recommended** to be used and won't automatically power off with the robot, but it is **competition-legal** and the battery life can last a long while._



See [hardware-selection](../hardware-selection/ "mention") for info on why these are recommended

{% hint style="success" %}
This section was inspired by PhotonVision's guide for common hardware setups
{% endhint %}
