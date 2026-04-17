---
name: get_weather
description: Retrieve a weather summary for a city from the web.
tags:
  - utility
  - weather
triggers:
  - weather
  - forecast
  - city
---

# Goal
Find a concise weather summary for the user's requested city.

# Workflow
1. Read the requested city name from the user message.
2. Use a web source to retrieve weather data.
3. Summarize the result in a short and clear response.

