---
icon: server
---

# NetworkTables API

## About

{% hint style="warning" %}
Synapse interfaces with SynapseLib, our vendor dependency, using NetworkTables. If you are running Synapse on a robot (i.e with a RoboRIO), you should configure the runtime to connect correctly to the NetworkTables server hosted on the robot.
{% endhint %}

If you are working without a robot, (i.e running in `server` mode or in `sim` mode), you will not need to configure a NetworkTables server and Syanpse will automatically connect either to the self-hosted server or the Simulation NetworkTables server.&#x20;

## API

{% hint style="warning" %}
While using the NetworkTable's API alone is possible in order to get some basic stuff done, and will also support settings modification, not all the values inside it will be sent in a human-readable format (i.e as byte-encodded data), and won't be verified from Robot Code if modified directly from NetworkTables. We recommend using SynapseLib.
{% endhint %}

The tables below list each key name that Synapse sends over the network, along with a brief description. These entries can be found within a subtable named after your camera’s nickname (as shown in the Synapse UI), which is located under the main Synapse table (or the runtime nickname table).

<table data-full-width="true"><thead><tr><th>Key</th><th>Type</th><th>Description</th></tr></thead><tbody><tr><td>metrics</td><td><code>double[]</code> </td><td>Metrics array for hardware perofmance information [cpu temp, cpu usage, memory, uptime, gpu memory split, used ram, used disk pct, npu usgae]</td></tr><tr><td>&#x3C;cameraTable>/pipeline</td><td><code>int</code></td><td>Pipeline index for camera</td></tr><tr><td>&#x3C;cameraTable>/processLatency</td><td><code>double</code></td><td>Pipeline process latency</td></tr><tr><td>&#x3C;cameraTable>/captureLatency</td><td><code>double</code></td><td>Camera capture latency</td></tr><tr><td>&#x3C;cameraTable>/settings</td><td>Table</td><td>Holds all the settings for the current pipeline</td></tr><tr><td>&#x3C;cameraTable>/data</td><td>Table</td><td>Holds all the data results for the current pipeline</td></tr></tbody></table>
