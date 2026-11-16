# A service is slow (high latency)

Use when p95 latency is far above normal for recommendation, product pages or any other service.

1. Look at the slowest traces. Find which downstream call takes most of the time.
2. Check cache health. A cache that stopped working shows up as cache miss warnings and growing memory.
3. If a feature flag or experiment changed caching, switch it off.
4. If memory keeps growing after that, restart the service during a quiet minute.
5. After the fix, p95 latency should return under one second.
