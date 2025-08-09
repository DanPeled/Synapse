---
description: List of known issues and possible ways to avoid / fix them
icon: bug
---

# Known Issues

{% hint style="info" %}
Want to fix a issue that's bothering you? Seen a undocumented issue? Please open an issue on [GitHub](https://github.com/DanPeled/Synapse) or contribute with a PR fixing the issue.
{% endhint %}

* On windows, camera performance may be heavily damaged, but works fine on Linux
  * Currently, the reason for this issue remains unknown, our guess is that it may be something to do with the CSCore version that we're using but that theory wasn't proven yet
* UI Camera Stream doesn't load after restarting the runtime
  * This sometimes happens due to a incorrect use of the `useEffect` call inside React which we use in order to render the UI, a simple refresh usually fixes the issue.&#x20;
* Runtime Shutdown takes a long time even when pressing Ctrl + C
  * This happens on specific OS's but from testing shouldn't happen on a Robot Coprocessor, reason still unknown, likely something to do with the runtime cleanup sequence

