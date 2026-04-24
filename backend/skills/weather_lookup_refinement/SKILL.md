---
name: weather_lookup_refinement
description: Fetch and present weather information in a short helpful format.
version: 0.1.0
tags:
  - generated
triggers:
  - weather
  - lookup
  - refinement
---

# Goal
Retrieve weather information and summarize it clearly for the user.

# Constraints & Style
- Keep the response short and practical.
- Include the requested city or location.
- Highlight the most useful weather signal first.

# Workflow
1. Resolve the requested city or location.
2. Retrieve the latest weather data.
3. Summarize the result in a short helpful format.
