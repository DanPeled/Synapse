# Working without a robot

{% hint style="danger" %}
All of the options below require the working computer to have a project set-up on it and the commands should be called inside its root folder.\
\
These modes will use the cameras connected to the computer its ran on, and not simulate digital cameras. (Simulating cameras is a planned feature and will be added in the future)
{% endhint %}

In order to work without a robot, we can work in 1 of 2 modes, using CLI arguments:

## Coprocessor / Computer As Server

Will run the coprocessor as the NetworkTable's server, start the server by running the following command:

```bash
<pythonexec> main.py --server
```

## Simulation Mode

Will make the runtime connect to the locally hosted NetworkTables server (at 127.0.0.1), can be used together with the [WPILib Robot Simulation](https://docs.wpilib.org/en/stable/docs/software/wpilib-tools/robot-simulation/introduction.html). This can be done with running the following command:

```bash
<pythonexec> main.py --sim
```
