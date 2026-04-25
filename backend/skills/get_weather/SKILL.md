---
name: get_weather
description: Retrieve a weather summary for a city from the web.
version: 0.1.1
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

# Constraints & Style
- Output must strictly adhere to four specific sections: Weather Overview, Clothing Advice, Travel Risk, and Suitable Photography Time.
- Do not deviate from the requested structure.

# Workflow
1. Read the requested city name from the user message.
2. Use a web source to retrieve weather data.
3. Summarize the result in a short and clear response.
4. Extract location and date from user query.
5. Fetch detailed weather data (temperature, precipitation, wind, UV index).
6. Generate 'Weather Overview' summarizing key metrics.
7. Analyze temperature to formulate 'Clothing Advice'.
8. Assess environmental factors to identify 'Travel Risks'.
9. Evaluate lighting conditions to suggest 'Suitable Photography Time'.
10. Format the final response using the four designated headers.

## Merged Draft Updates
### draft_20260425051504_6ab3cc
- Version: 0.1.0 -> 0.1.1
- Added Constraints:
  - Output must strictly adhere to four specific sections: Weather Overview, Clothing Advice, Travel Risk, and Suitable Photography Time.
  - Do not deviate from the requested structure.
- Added Workflow Steps:
  - Extract location and date from user query.
  - Fetch detailed weather data (temperature, precipitation, wind, UV index).
  - Generate 'Weather Overview' summarizing key metrics.
  - Analyze temperature to formulate 'Clothing Advice'.
  - Assess environmental factors to identify 'Travel Risks'.
  - Evaluate lighting conditions to suggest 'Suitable Photography Time'.
  - Format the final response using the four designated headers.
